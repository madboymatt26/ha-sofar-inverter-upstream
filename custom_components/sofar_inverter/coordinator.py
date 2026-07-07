"""Modbus TCP polling/control coordinator for Sofar inverters.

Ported from the Sofar2mqtt ESP firmware. Two control protocols are supported:

  * ME3000 / HYD-ES : the proprietary Sofar "passive mode" function code 0x42.
    This is NOT a standard Modbus function, so it is implemented with a custom
    pymodbus PDU (SofarPassiveModeRequest / Response).

  * HYD-EP/KTL      : a standard write-multiple-registers (FC 0x10) to the
    passive control register 0x1187, writing a 6x16-bit payload.

All coordinators that share the same host:port (i.e. the same Modbus TCP /
RS485 gateway) share a single pymodbus client and a single asyncio.Lock, so
polls, commands and the heartbeat from different slave IDs are serialised onto
the one RS485 bus behind the gateway. This avoids transaction-id collisions
where one coordinator reads back another coordinator's response. The shared
client and the single per-gateway heartbeat are reference-counted and torn down
when the last coordinator for that gateway unloads.
"""
from __future__ import annotations

import asyncio
import logging
import struct
from datetime import timedelta

from pymodbus.pdu import ModbusPDU

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    MODEL_CONFIG,
    MODEL_HYD_ES,
    MODEL_HYD_EP_KTL,
    MODEL_ME3000,
    MODE_AUTO,
    MODE_BATTERY_SAVE,
    MODE_CHARGE,
    MODE_DISCHARGE,
    MODE_NONE,
    MODE_STANDBY,
    PROTO_PASSIVE_FN42,
    PROTO_PASSIVE_REG,
    SENSORS_HYD_EP_KTL_BATTERY2,
    SOFAR2_REG_PASSIVECONTROL,
    SOFAR_FN_AUTO,
    SOFAR_FN_CHARGE,
    SOFAR_FN_DISCHARGE,
    SOFAR_FN_STANDBY,
    SOFAR_PARAM_STANDBY,
)

_LOGGER = logging.getLogger(__name__)

# Sofar proprietary passive-mode function code (not standard Modbus).
SOFAR_FN_PASSIVEMODE = 0x42

# Sofar passive-mode heartbeat (FC 0x49). ME3000 / HYD-ES require this every 9s
# to stay responsive in passive mode; the firmware skips it for HYDV2.
SOFAR_FN_HEARTBEAT = 0x49
HEARTBEAT_INTERVAL = 9  # seconds, fixed (not user-configurable)


class SofarPassiveModeResponse(ModbusPDU):
    """Response PDU for the Sofar proprietary passive-mode command (0x42).

    The inverter echoes back a 2-byte data payload. We capture the raw
    registers so the caller can confirm a successful round-trip.
    """

    function_code = SOFAR_FN_PASSIVEMODE
    rtu_byte_count_pos = 2

    def __init__(self, values=None, slave=1, transaction=0):
        super().__init__(dev_id=slave, transaction_id=transaction)
        self.values = values or []

    def encode(self) -> bytes:
        res = struct.pack(">B", len(self.values) * 2)
        for register in self.values:
            res += struct.pack(">H", register)
        return res

    def decode(self, data: bytes) -> None:
        byte_count = int(data[0])
        self.values = []
        for i in range(1, byte_count + 1, 2):
            self.values.append(struct.unpack(">H", data[i : i + 2])[0])


class SofarPassiveModeRequest(ModbusPDU):
    """Request PDU for the Sofar proprietary passive-mode command (0x42).

    Frame body is: <function code 0x42><cmd:16><param:16> exactly as the
    firmware's sendPassiveCmd() constructs it.
    """

    function_code = SOFAR_FN_PASSIVEMODE
    rtu_frame_size = 8

    def __init__(self, cmd: int = 0, param: int = 0, slave: int = 1, transaction: int = 0):
        super().__init__(dev_id=slave, transaction_id=transaction)
        self.cmd = cmd
        self.param = param

    def encode(self) -> bytes:
        return struct.pack(">HH", self.cmd, self.param & 0xFFFF)

    def decode(self, data: bytes) -> None:
        self.cmd, self.param = struct.unpack(">HH", data)

    def get_response_pdu_size(self) -> int:
        # 1 byte count + 2 data bytes
        return 1 + 1 + 2


class SofarHeartbeatRequest(ModbusPDU):
    """Request PDU for the Sofar passive-mode heartbeat (FC 0x49).

    Mirrors the firmware frame {id, 0x49, 0x22, 0x01, 0x22, 0x02, 0x00, 0x00}.
    Sent fire-and-forget; the inverter's reply is not needed.
    """

    function_code = SOFAR_FN_HEARTBEAT
    rtu_frame_size = 10  # id + fc + 6 data + 2 crc

    def __init__(self, slave: int = 1, transaction: int = 0):
        super().__init__(dev_id=slave, transaction_id=transaction)

    def encode(self) -> bytes:
        return bytes([0x22, 0x01, 0x22, 0x02, 0x00, 0x00])

    def decode(self, data: bytes) -> None:
        pass

    def get_response_pdu_size(self) -> int:
        return 0


class _GatewayConnection:
    """Shared pymodbus client + lock + heartbeat for one gateway (host:port).

    A single RS485 bus sits behind the Modbus TCP gateway, so every coordinator
    that targets this gateway (regardless of slave ID) must serialise its bus
    access through one lock and one client. Reference-counted by config-entry
    id: the client and heartbeat are created on first use and closed when the
    last coordinator for this gateway unloads.
    """

    def __init__(self, hass: HomeAssistant, host: str, port: int) -> None:
        self.hass = hass
        self.host = host
        self.port = port
        self.lock = asyncio.Lock()
        self._users: set[str] = set()
        self._client = None
        self._heartbeat_task = None
        self._heartbeat_wanted = False
        self._heartbeat_slave = 1

    # -- reference counting --------------------------------------------------
    def acquire(self, user_id: str) -> None:
        """Register a coordinator (by entry id) as a user of this gateway."""
        self._users.add(user_id)

    def release(self, user_id: str) -> bool:
        """Drop a user; return True when no users remain (safe to close)."""
        self._users.discard(user_id)
        return not self._users

    # -- shared client -------------------------------------------------------
    def _build_client(self):
        from pymodbus.client import AsyncModbusTcpClient  # noqa: PLC0415

        return AsyncModbusTcpClient(host=self.host, port=self.port, timeout=5)

    @staticmethod
    def _register_pdu(client) -> None:
        """Register the proprietary 0x42 response decoder on the client."""
        try:
            client.register(SofarPassiveModeResponse)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.debug("Could not register custom PDU: %s", exc)

    async def async_get_client(self):
        """Return a connected shared client. Must be called holding self.lock."""
        if self._client is None:
            self._client = self._build_client()
        if not self._client.connected:
            if not await self._client.connect():
                raise ConnectionError(f"Cannot connect to {self.host}:{self.port}")
            # Re-register the 0x42 decoder on every (re)connect. A dropped and
            # rebuilt connection can reset the framer/decoder, which would
            # otherwise silently break ME3000/HYD-ES commands after a reconnect.
            self._register_pdu(self._client)
        return self._client

    # -- heartbeat (one per gateway) ----------------------------------------
    def want_heartbeat(self, slave: int) -> None:
        """Mark that this gateway needs the passive-mode heartbeat."""
        if not self._heartbeat_wanted:
            self._heartbeat_slave = slave
        self._heartbeat_wanted = True

    def ensure_heartbeat(self) -> None:
        """Start the single per-gateway heartbeat task once."""
        if self._heartbeat_wanted and self._heartbeat_task is None:
            self._heartbeat_task = self.hass.async_create_background_task(
                self._heartbeat_loop(),
                name=f"{DOMAIN}_heartbeat_{self.host}_{self.port}",
            )

    async def _heartbeat_loop(self) -> None:
        """Send the FC 0x49 heartbeat every 9s on the shared bus.

        Only one heartbeat is needed per RS485 bus regardless of how many slave
        IDs are in use, so this lives on the gateway, not the coordinator.
        """
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            try:
                async with self.lock:
                    client = await self.async_get_client()
                    # Fire-and-forget: the inverter's reply is not needed.
                    await client.execute(
                        True, SofarHeartbeatRequest(slave=self._heartbeat_slave)
                    )
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                _LOGGER.warning(
                    "Heartbeat send failed for %s:%s: %s", self.host, self.port, exc
                )

    async def async_close(self) -> None:
        """Cancel the heartbeat and close the shared client (last user gone)."""
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
        if self._client is not None:
            self._client.close()
            self._client = None


def _get_gateway(hass: HomeAssistant, host: str, port: int) -> _GatewayConnection:
    """Return the shared gateway connection for host:port, creating if needed."""
    registry = hass.data.setdefault(DOMAIN, {}).setdefault("_gateways", {})
    key = (host, port)
    gateway = registry.get(key)
    if gateway is None:
        gateway = _GatewayConnection(hass, host, port)
        registry[key] = gateway
    return gateway


class SofarCoordinator(DataUpdateCoordinator):
    """Polls a Sofar inverter over Modbus TCP and issues control commands."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        slave: int,
        model: str,
        max_power: int,
        update_interval: timedelta,
    ) -> None:
        self.host = host
        self.port = port
        self.slave = slave
        self.model = model
        self.max_power = max_power
        self._send_heartbeat = model in (MODEL_ME3000, MODEL_HYD_ES)

        # Share one client + lock + heartbeat per gateway (host:port).
        self._gateway = _get_gateway(hass, host, port)
        self._lock = self._gateway.lock
        if self._send_heartbeat:
            self._gateway.want_heartbeat(slave)

        model_cfg = MODEL_CONFIG[model]
        self.sensors = list(model_cfg["sensors"])
        self.protocol = model_cfg["protocol"]
        self.runstate_map = model_cfg["runstate"]
        self._battery2_checked = False

        # Active control state. Re-applied on each poll so passive-mode
        # setpoints stay latched (matching the firmware's periodic re-send).
        self.active_mode: str = MODE_NONE
        self.active_power: int = 0

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{host}_{slave}",
            update_interval=update_interval,
        )

        # Register this entry as a user of the shared gateway. Keyed by entry
        # id so it is idempotent across ConfigEntryNotReady retries (which
        # rebuild the coordinator but reuse the same entry id).
        entry = getattr(self, "config_entry", None)
        self._gateway_user = entry.entry_id if entry is not None else f"obj-{id(self)}"
        self._gateway.acquire(self._gateway_user)

    # ----------------------------------------------------------- lifecycle
    async def async_shutdown(self) -> None:
        """Release this coordinator's hold on the shared gateway connection."""
        if self._gateway.release(self._gateway_user):
            await self._gateway.async_close()
            self.hass.data.get(DOMAIN, {}).get("_gateways", {}).pop(
                (self.host, self.port), None
            )
        await super().async_shutdown()

    # --------------------------------------------------------------- decoding
    @staticmethod
    def _decode(registers: list[int], count: int, signed: bool) -> int:
        """Decode 1 or 2 big-endian holding registers into an int."""
        if count == 2:
            raw = (registers[0] << 16) | registers[1]
            if signed and raw >= 0x80000000:
                raw -= 0x100000000
            return raw
        raw = registers[0] & 0xFFFF
        if signed and raw >= 0x8000:
            raw -= 0x10000
        return raw

    # ------------------------------------------------------------------ poll
    async def _async_update_data(self) -> dict[str, object]:
        self._gateway.ensure_heartbeat()
        async with self._lock:
            try:
                client = await self._gateway.async_get_client()
            except Exception as exc:  # noqa: BLE001
                raise UpdateFailed(
                    f"Cannot connect to {self.host}:{self.port}: {exc}"
                ) from exc
            try:
                if self.model == MODEL_HYD_EP_KTL and not self._battery2_checked:
                    await self._maybe_add_battery2(client)

                results = await self._read_all(client)
                if not results:
                    raise UpdateFailed("No registers could be read from the inverter")

                # Re-apply / evaluate the active control mode on the same shared
                # connection (we already hold the gateway lock here).
                await self._apply_active_mode(client, results)

                return results
            except UpdateFailed:
                raise
            except Exception as exc:  # noqa: BLE001
                raise UpdateFailed(f"Error polling {self.host}:{self.port}: {exc}") from exc

    async def _read_all(self, client) -> dict[str, object]:
        """Read every configured sensor register."""
        results: dict[str, object] = {}
        for sensor in self.sensors:
            try:
                resp = await client.read_holding_registers(
                    address=sensor.register, count=sensor.count, device_id=self.slave
                )
                if not hasattr(resp, "registers") or resp.registers is None:
                    _LOGGER.debug(
                        "Read error for %s (reg 0x%04X): %s",
                        sensor.key, sensor.register, resp,
                    )
                    continue
                if len(resp.registers) < sensor.count:
                    continue

                raw = self._decode(resp.registers, sensor.count, sensor.signed)

                if sensor.is_state:
                    results[sensor.key] = self.runstate_map.get(raw, f"Unknown ({raw})")
                    results[f"{sensor.key}_raw"] = raw
                else:
                    results[sensor.key] = round(raw * sensor.scale, 3)
            except Exception as exc:  # noqa: BLE001
                _LOGGER.debug("Error reading %s: %s", sensor.key, exc)
                continue
        return results

    async def _maybe_add_battery2(self, client) -> None:
        """Add second-battery sensors if the inverter reports a 2nd battery."""
        try:
            resp = await client.read_holding_registers(
                address=SENSORS_HYD_EP_KTL_BATTERY2[0].register,
                count=1,
                device_id=self.slave,
            )
            if hasattr(resp, "registers") and resp.registers and resp.registers[0] > 0:
                existing = {s.key for s in self.sensors}
                for s in SENSORS_HYD_EP_KTL_BATTERY2:
                    if s.key not in existing:
                        self.sensors.append(s)
                _LOGGER.info("Second battery detected on %s", self.host)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.debug("Battery2 detection failed: %s", exc)
        finally:
            self._battery2_checked = True

    # --------------------------------------------------------------- control
    def set_active_mode(self, mode: str, power: int | None = None) -> None:
        """Store the desired control mode; applied on the next poll/refresh."""
        self.active_mode = mode
        if power is not None:
            self.active_power = max(0, min(power, self.max_power))

    async def async_set_mode(self, mode: str, power: int | None = None) -> bool:
        """Set the control mode and apply it immediately."""
        self.set_active_mode(mode, power)
        if mode == MODE_NONE:
            return True
        async with self._lock:
            try:
                client = await self._gateway.async_get_client()
            except Exception as exc:  # noqa: BLE001
                _LOGGER.error(
                    "Cannot connect to %s:%s to send command: %s",
                    self.host, self.port, exc,
                )
                return False
            ok = await self._dispatch(client, mode, self.active_power, grid_power=None)
        # Refresh so entities reflect the new state quickly.
        await self.async_request_refresh()
        return ok

    async def _apply_active_mode(self, client, results: dict) -> None:
        """Re-apply the active mode during a poll (lock already held)."""
        if self.active_mode == MODE_NONE:
            return
        grid_power = results.get("grid_power")
        try:
            await self._dispatch(client, self.active_mode, self.active_power, grid_power)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.debug("Re-applying active mode failed: %s", exc)

    async def _dispatch(self, client, mode: str, power: int, grid_power) -> bool:
        """Route a control request to the right protocol handler."""
        if mode == MODE_BATTERY_SAVE:
            # Hybrid auto: charge from excess solar but never discharge.
            # Exporting (grid_power >= ~0) -> auto, otherwise force standby.
            effective = MODE_AUTO if (grid_power is None or grid_power >= -100) else MODE_STANDBY
            mode = effective

        if self.protocol == PROTO_PASSIVE_FN42:
            return await self._do_passive_fn42(client, mode, power)
        if self.protocol == PROTO_PASSIVE_REG:
            return await self._do_passive_reg(client, mode, power)
        return False

    async def _do_passive_fn42(self, client, mode: str, power: int) -> bool:
        """ME3000 / HYD-ES passive-mode command via function code 0x42."""
        if mode == MODE_STANDBY:
            fn_code, param = SOFAR_FN_STANDBY, SOFAR_PARAM_STANDBY
        elif mode == MODE_AUTO:
            fn_code, param = SOFAR_FN_AUTO, 0
        elif mode == MODE_CHARGE:
            fn_code, param = SOFAR_FN_CHARGE, max(0, min(power, self.max_power))
        elif mode == MODE_DISCHARGE:
            fn_code, param = SOFAR_FN_DISCHARGE, max(0, min(power, self.max_power))
        else:
            return False

        try:
            request = SofarPassiveModeRequest(cmd=fn_code, param=param, slave=self.slave)
            resp = await client.execute(False, request)
            if resp is None or (hasattr(resp, "isError") and resp.isError()):
                _LOGGER.error("Passive-mode command failed (mode=%s): %s", mode, resp)
                return False
            _LOGGER.debug("Passive-mode command ok (mode=%s, param=%s)", mode, param)
            return True
        except Exception as exc:  # noqa: BLE001
            _LOGGER.error("Error sending passive-mode command: %s", exc)
            return False

    async def _do_passive_reg(self, client, mode: str, power: int) -> bool:
        """HYD-EP/KTL passive control via write-multiple-registers (0x1187)."""
        if mode == MODE_STANDBY:
            min_power = max_power = 0
        elif mode == MODE_AUTO:
            if power > 0:
                min_power, max_power = -power, power
            else:
                min_power, max_power = -16384, 16383
        elif mode == MODE_CHARGE:
            min_power = max_power = max(0, min(power, self.max_power))
        elif mode == MODE_DISCHARGE:
            min_power = max_power = -max(0, min(power, self.max_power))
        else:
            return False

        def _split(value: int) -> tuple[int, int]:
            raw = value & 0xFFFFFFFF
            return (raw >> 16) & 0xFFFF, raw & 0xFFFF

        min_hi, min_lo = _split(min_power)
        max_hi, max_lo = _split(max_power)
        # 6x 16-bit regs = desired32 (forced to 0), min32, max32 — matching the
        # firmware's sendPassiveCmdV2 frame (two leading zero bytes per word).
        payload = [0x0000, 0x0000, min_hi, min_lo, max_hi, max_lo]

        try:
            resp = await client.write_registers(
                address=SOFAR2_REG_PASSIVECONTROL, values=payload, device_id=self.slave
            )
            if resp is None or (hasattr(resp, "isError") and resp.isError()):
                _LOGGER.error("Passive control write failed (mode=%s): %s", mode, resp)
                return False
            _LOGGER.debug(
                "Passive control ok (mode=%s, min=%s, max=%s)", mode, min_power, max_power
            )
            return True
        except Exception as exc:  # noqa: BLE001
            _LOGGER.error("Error writing passive control: %s", exc)
            return False
