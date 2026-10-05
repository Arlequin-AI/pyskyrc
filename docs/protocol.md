# SkyRC Q200neo / T1000 — HID / BLE protocol

Reverse-engineered from Charge Master 1.55.E207 on Linux via `usbmon`
and Android HCI snoop log. Tested against firmware **3.57.1.0**.

The charger exposes two transports with the same command set:

- **USB HID** — fixed-length frames (64 bytes)
- **BLE** — variable-length frames (0f LEN payload CHK)

## USB HID frame layout

Every report is exactly 64 bytes.

### Host -> Device

| Prefix     | Meaning                                       |
|------------|-----------------------------------------------|
| `0f 03 5a` | bank polling A (slow telemetry)               |
| `0f 03 5f` | bank polling B (secondary)                    |
| `0f 03 55` | per-port polling — real-time cells / temp     |
| `0f 03 57` | query device info (serial number)             |
| `0f 03 66` | query firmware                                |
| `0f 16 05` | START charge                                  |
| `0f 03 fe` | STOP charge                                   |

### Device -> Host

| Prefix     | Meaning                                       |
|------------|-----------------------------------------------|
| `0f 25 5a` | bank-level telemetry                          |
| `0f 0c 5f` | bank-level telemetry (secondary)              |
| `0f 22 55` | per-port live telemetry                       |
| `0f 04 05` | ACK on START                                  |
| `0f 04 fe` | ACK on STOP                                   |
| `0f 14 57` | device info reply                             |
| `0f 05 66` | firmware reply                                |

## START packet (USB)

    0f 16 05 SS | b4 | b5 | b6 | b7 | b8 | b9-b10 | b11-b12 | b13 | b14 | b15-b16 | ...

| Offset | Field                                                       |
|--------|-------------------------------------------------------------|
| 0-2    | 0f 16 05                                                    |
| 3      | port selector: 01=A, 02=B, 04=C, 08=D                       |
| 4      | chemistry (see enum)                                        |
| 5      | cell count                                                  |
| 6      | mode (see enum by chemistry)                                |
| 7      | charge current x100 mA                                      |
| 8      | discharge current x100 mA                                   |
| 9-10   | discharge cutoff, mV (BE)                                   |
| 11-12  | charge cutoff, mV (BE)                                      |
| 13     | RE-PEAK: repeat count (0..3); CYCLE: direction (0=C-D, 1=D-C)|
| 14     | cycle count (0..3)                                          |
| 15-16  | trickle current, mA (BE), default 0x0031 = 49               |
| 17-22  | reserved, zero                                              |
| 23     | checksum                                                    |

### USB checksum

    checksum = (sum(b3..b22) + 5) & 0xff

Port selector (b3) is included in the sum — unified formula for all 4 ports.

Verified on 60+ real payloads.

### STOP packet (USB)

Each port has a unique STOP template (echo of Charge Master):

| Port | b4   | b5   | b16  | checksum |
|------|------|------|------|----------|
| A    | 0xFF | 0x02 | 0x00 | 0x7F     |
| B    | 0x00 | 0x06 | 0x31 | 0xB5     |
| C    | 0x02 | 0x06 | 0x31 | 0xB7     |
| D    | 0x06 | 0x06 | 0x31 | 0xBB     |

Device responds with `0f 04 fe SS ...` (ACK).

## Per-port live telemetry (0f 22 55 SS)

| Offset | Field                         |
|--------|-------------------------------|
| 0-2    | 0f 22 55                      |
| 3      | port selector                 |
| 4      | state (see below)             |
| 5-7    | counter                       |
| 8      | counter                       |
| 9-13   | unknown                       |
| 14     | temperature, C                |
| 15-16  | zero                          |
| 17-28  | 6 x uint16 BE, cell mV        |
| 29-34  | unknown                       |
| 35-36  | unknown                       |

### State enum (byte 4)

| Value | Meaning                                       |
|-------|-----------------------------------------------|
| 0x00  | off                                           |
| 0x01  | charging                                      |
| 0x02  | idle (ready to start)                         |
| 0x03  | unknown                                       |
| 0x04  | starting (START received, no battery detected)|

### Cell validation

Real battery: all 6 cells in 2500..4500 mV, spread <= 200 mV.
Otherwise dummy values (7, 9, 11, 12 mV) on empty ADC input.

## Chemistry enum (b4)

| Value | Chemistry |
|-------|-----------|
| 0x00  | LiPo      |
| 0x01  | LiIo      |
| 0x02  | LiFe      |
| 0x03  | LiHV      |
| 0x04  | NiMH      |
| 0x05  | NiCd      |
| 0x06  | Pb        |

## Mode enum (b6)

### LiPo / LiIo / LiFe / LiHV

| Value | Mode      |
|-------|-----------|
| 0x00  | BAL.CHG   |
| 0x01  | CHARGE    |
| 0x02  | DISCHARGE |
| 0x03  | STORAGE   |

### NiMH / NiCd

| Value | Mode      |
|-------|-----------|
| 0x00  | CHARGE    |
| 0x02  | DISCHARGE |
| 0x03  | RE-PEAK   |
| 0x04  | CYCLE (C-D or D-C, see b13) |

### Pb

| Value | Mode          |
|-------|---------------|
| 0x00  | NORMAL        |
| 0x01  | DISCHARGE     |
| 0x02  | AGM           |
| 0x03  | COLD CHARGE   |

## Device info (USB)

Host sends `0f 03 57 01 58 ...`
Device replies:

    0f 14 57 01 | 00 | 31 30 30 31 39 37 | 03 00 00 00 | 00 | 03 39 01 00 | ...

| Offset | Field                              |
|--------|------------------------------------|
| 5-10   | serial number ASCII, 6 bytes       |
| 16-19  | firmware version bytes             |

Example: serial "100197", version bytes 03 39 01 00 -> "3.57.1.0".

## BLE transport

Service: 0000ffe0-0000-1000-8000-00805f9b34fb
Characteristic: 0000ffe1-0000-1000-8000-00805f9b34fb
Properties: read, write-without-response, notify

### BLE frame layout

    [0f] [LEN] [payload...] [CHK]

- LEN = len(payload) + 1
- CHK = sum(payload) & 0xff

Payload starts with the same command byte as USB:
- 0x05 START
- 0xFE STOP
- 0x55 per-port poll
- 0x5a bank poll A
- 0x5f bank poll B
- 0x57 query serial
- 0x66 query firmware

### BLE examples

Per-port poll on port B:

    0f 03 55 02 57

LEN = 3, payload = 55 02, CHK = 55 + 02 = 0x57.

START (LiPo 6S BAL.CHG 1.0A, port B):

    0f 12 05 02 00 06 00 0a 05 0b b8 10 68 00 00 00 00 00 00 57

LEN = 0x12 = 18, payload = 05 02 00 06 00 0a 05 0b b8 10 68 00 00 00 00 00 00,
CHK = 0x57.

### BLE device discovery

Advertisement from the charger does not always include the service
UUID. Reliable strategy: scan, then attempt GATT connection and
check for service 0xffe0. Cache the MAC after first success.

MTU: 223 bytes. Our frames fit in one write.
Pairing is not required — GATT access works without bonding.

## USB-HID requirements

Linux: device appears as /dev/hidrawX (usually hidraw4). Needs read+write
access: `sudo chmod 666 /dev/hidraw4` or a udev rule.

The device has VID:PID and is accessed via HID class, not libusb.

## Timing

- USB polling cycle: ~4 Hz per port.
- USB ACK on START/STOP: ~1.6 s after command.
- BLE ACK on START/STOP: ~30 ms after write.
- BLE advertisement interval: 15-20 s (must account for this in
  auto-discovery timeouts).

