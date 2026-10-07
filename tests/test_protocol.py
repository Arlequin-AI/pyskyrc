"""Protocol builder tests."""

from pyskyrc import protocol
from pyskyrc.enums import (
    Chemistry,
    CycleDirection,
    LiMode,
    NiMode,
    Port,
)


def test_start_basic():
    pkt = protocol.build_start_packet(
        port=Port.B,
        chemistry=Chemistry.LiPo,
        cells=6,
        mode=LiMode.BALANCE_CHARGE,
        charge_current_a=1.0,
        discharge_current_a=0.5,
        charge_cutoff_mv=4200,
        discharge_cutoff_mv=3000,
    )
    assert pkt[:4] == bytes([0x0F, 0x16, 0x05, 0x02])
    assert pkt[4] == 0x00
    assert pkt[5] == 6
    assert pkt[6] == 0x00
    assert pkt[7] == 0x0A
    assert pkt[8] == 0x05
    assert pkt[9:13] == bytes([0x0B, 0xB8, 0x10, 0x68])
    assert pkt[15:17] == protocol.DEFAULT_TRICKLE_MA.to_bytes(2, "big")
    assert pkt[23] == protocol.checksum(pkt)


def test_start_port_a():
    pkt = protocol.build_start_packet(
        port=Port.A,
        chemistry=Chemistry.LiPo,
        cells=2,
        mode=LiMode.BALANCE_CHARGE,
        charge_current_a=1.0,
        charge_cutoff_mv=4200,
        discharge_cutoff_mv=3000,
    )
    assert pkt[3] == 0x01
    assert pkt[23] == protocol.checksum(pkt)


def test_start_port_d():
    pkt = protocol.build_start_packet(
        port=Port.D,
        chemistry=Chemistry.LiPo,
        cells=6,
        mode=LiMode.BALANCE_CHARGE,
        charge_current_a=1.0,
        charge_cutoff_mv=4200,
        discharge_cutoff_mv=3000,
    )
    assert pkt[3] == 0x08
    assert pkt[23] == protocol.checksum(pkt)


def test_start_nimh_cycle():
    pkt = protocol.build_start_packet(
        port=Port.B,
        chemistry=Chemistry.NiMH,
        cells=4,
        mode=NiMode.CYCLE,
        charge_current_a=1.0,
        discharge_current_a=0.5,
        charge_cutoff_mv=6,
        discharge_cutoff_mv=900,
        cycle_direction=CycleDirection.DISCHARGE_CHARGE,
    )
    assert pkt[6] == int(NiMode.CYCLE)
    assert pkt[13] == int(CycleDirection.DISCHARGE_CHARGE)


def test_start_nimh_repeak():
    pkt = protocol.build_start_packet(
        port=Port.B,
        chemistry=Chemistry.NiMH,
        cells=4,
        mode=NiMode.RE_PEAK,
        charge_current_a=1.0,
        discharge_current_a=0.5,
        charge_cutoff_mv=6,
        discharge_cutoff_mv=900,
        repeat_count=3,
    )
    assert pkt[13] == 3


def test_stop_all_ports():
    for port in Port:
        pkt = protocol.build_stop_packet(port)
        assert len(pkt) == 64
        assert pkt[0:3] == bytes([0x0F, 0x03, 0xFE])
        assert pkt[3] == int(port)


def test_frame_per_port():
    for port in Port:
        f = protocol.frame_per_port(int(port))
        assert f[0:3] == bytes([0x0F, 0x03, 0x55])
        assert f[3] == int(port)
        assert f[23] == 0xB5


def test_frame_query_serial():
    f = protocol.frame_query_serial(1)
    assert f[0:3] == bytes([0x0F, 0x03, 0x57])
    assert f[3] == 1
    assert f[4] == 0x58


def test_ble_frame_per_port():
    f = protocol.frame_per_port_ble(0x02)
    assert f == bytes([0x0F, 0x03, 0x55, 0x02, 0x57])


def test_ble_start():
    f = protocol.build_start_packet_ble(
        port=Port.B,
        chemistry=Chemistry.LiPo,
        cells=6,
        mode=LiMode.BALANCE_CHARGE,
        charge_current_a=1.0,
        discharge_current_a=0.5,
        charge_cutoff_mv=4200,
        discharge_cutoff_mv=3000,
    )
    assert f[0] == 0x0F
    assert f[1] == len(f) - 2  # LEN = payload + CHK
    assert f[-1] == (sum(f[2:-1]) & 0xFF)


def test_ble_stop():
    f = protocol.build_stop_packet_ble(Port.B)
    assert f == bytes([0x0F, 0x03, 0xFE, 0x02, 0x00])


def test_parse_device_info():
    pkt = bytes.fromhex("0f14570100313030313937030000000003390100")
    pkt = pkt + b"\x00" * (64 - len(pkt))
    info = protocol.parse_device_info(pkt)
    assert info is not None
    assert info.serial == "100197"
    assert info.version == "3.57.1.0"


def test_parse_device_info_bad():
    assert protocol.parse_device_info(b"\x00" * 64) is None
