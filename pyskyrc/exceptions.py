"""Исключения библиотеки pyskyrc."""


class SkyRCError(Exception):
    """Базовое исключение всех ошибок pyskyrc."""


class DeviceNotFoundError(SkyRCError):
    """HID-устройство или BLE-устройство не найдено."""


class DeviceIOError(SkyRCError):
    """Ошибка чтения/записи."""


class ProtocolError(SkyRCError):
    """Нарушение протокола обмена."""


class InvalidParameterError(SkyRCError):
    """Неверный параметр (порт, химия, режим, ток...)."""


class NoAckError(SkyRCError):
    """Устройство не подтвердило команду за отведённое время."""


class ChecksumError(SkyRCError):
    """Неверная контрольная сумма пакета."""
