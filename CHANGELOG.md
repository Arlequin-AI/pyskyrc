# Changelog

All notable changes to `pyskyrc` are documented here.

## [0.2.0] — 2026-10-05

### Added
- Full USB HID protocol support (fixed-length 64-byte frames).
- Full BLE protocol support via `bleak` (variable-length `0f LEN payload CHK` frames).
- Unified API: `SkyRCCharger(transport="usb"|"ble")`.
- Per-port live telemetry of all 4 ports (A/B/C/D).
- All 7 chemistries: LiPo, LiIo, LiFe, LiHV, NiMH, NiCd, Pb.
- All modes per chemistry.
- START / STOP charge control from Python or CLI.
- Device info handshake: serial number, firmware version.
- BLE auto-discovery by service UUID (works with renamed chargers).
- MAC cache for fast reconnect.
- Interactive shell mode (`pyskyrc shell`).
- CLI: `info`, `status`, `monitor`, `start`, `stop`, `scan`, `shell`.

### Fixed
- Checksum formula for port A (`(sum(b3..b22) + 5) & 0xff`).
- `build_stop_packet` for ports C and D (unique templates per port).

### Known issues
- BLE requires `bleak` (`pip install pyskyrc[ble]`).
- BLE pairing is not supported — use GATT without bonding.

## [0.1.0] — 2026-10-01 (unreleased)

- Initial reverse-engineering of USB HID protocol.
