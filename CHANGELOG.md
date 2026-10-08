# Changelog

All notable changes to `pyskyrc` are documented here.
## [0.3.4] — 2026-10-08

### Fixed
- **Windows USB transport now works out of the box.**
  `transport_hid.py` auto-detects which `hid` backend is installed:
  `pyhidapi` (`hid.Device`) or `cython-hidapi` (`hid.device().open_path`).
  Previously hard-coded `hid.Device` raised `AttributeError` on Windows.
- `pyproject.toml`: extras `usb` / `all` no longer pull the nonexistent
  `pyhidapi>=0.11`; now depend on `hidapi>=0.14` (cython-hidapi / trezor).
- `read()` normalizes `list[int]` → `bytes` for cython-hidapi.
- `write()` handles `-1` / `None` return values from cython-hidapi.

### Verified
- USB HID on Windows 11 (Python 3.14, hidapi 0.15.0) — SkyRC T1000 Maestro.
- BLE on Windows 11 (bleak 3.0.2, WinRT backend) — same device.

## [0.3.3] — 2026-10-07

### Fixed
- **USB transport now works out of the box on Windows, Linux, and macOS.**
  `HIDAPIDevice` detects which `hid` backend is installed at runtime and
  adapts accordingly, supporting all three PyPI variants of the module:
  - `pyhidapi` (apmorton) — `hid.Device(path=...)`
  - `hidapi` (trezor, cython-hidapi) — `hid.device().open_path(...)`
  - `hid` (bishop) — `hid.device().open(vid, pid)`
  Previously the code hard-coded `hid.Device(...)`, which raised
  `AttributeError: module 'hid' has no attribute 'Device'` on
  `cython-hidapi` and bishop's `hid`.
- `read()` now passes the timeout positionally and normalizes the return
  value to `bytes`, so `cython-hidapi`'s `list[int]` output no longer
  breaks downstream parsing.
- `write()` no longer crashes when the backend returns `None` from
  `write()`; the byte count is derived from the input packet length.
- `HIDAPIDevice.__init__` no longer imports the wrong annotation
  `hid.Device | None`, which prevented instantiation on non-pyhidapi
  installs.

### Changed
- **`pyproject.toml` extras:**
  - `usb` now depends on `hidapi>=0.14` (cython-hidapi, wheels for all
    major platforms) instead of the unrelated `hid>=1.0` package.
  - `all` updated to `["hidapi>=0.14", "bleak>=0.20"]`.
- Improved `ImportError` message when no supported `hid` backend is
  found: `pip install pyhidapi` or `pip install hidapi`.

### Notes
- Bumped version to `0.3.3` to follow the existing `v0.3.2` tag on
  GitHub. `0.3.0` in the earlier plan would have shadowed the already
  published tag.

## [0.3.2] — 2026-10-07

### Fixed
- CLI: `--hid` defaults to empty string instead of `/dev/hidraw4`,
  so USB transport uses cross-platform HIDAPI on Windows/macOS by default.
- Charger: fall back to HIDAPI if `/dev/hidraw*` path doesn't exist
  (fixes `AttributeError: module 'os' has no attribute 'O_NONBLOCK'` on Windows).

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
