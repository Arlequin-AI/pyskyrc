# Changelog

All notable changes to `pyskyrc` are documented here.


## [0.3.1] — 2026-10-07

### Fixed
 - cli.py: `--hid` default is now empty; USB uses hidapi auto-detect
   on all platforms. `/dev/hidraw*` still supported when explicitly passed.

## [0.3.0] — 2026-10-07

### Added
- Cross-platform USB HID transport via `hid` (apmorton/hidapi).
  Now works on Linux, macOS, and Windows.
- New optional dependency group: `pyskyrc[usb]`.
- New combined extra: `pyskyrc[all]` (USB + BLE).

### Changed
- USB transport defaults to HIDAPI when no explicit `/dev/hidraw*` path is given.
- Legacy `/dev/hidraw*` path still supported for Linux backward compatibility.

## [0.2.3] — 2026-10-05

### Fixed
- README: badge link points to absolute GitHub URL.

## [0.2.2] — 2026-10-05

### Fixed
- pyproject.toml: use PEP 639 SPDX license expression (`license = "MIT"`, `license-files = ["LICENSE"]`).
- README: absolute GitHub URL for full license text (relative links don't work on PyPI).

## [0.2.1] — 2026-10-05

### Changed
- README: mention copyright and clickable license link.

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
