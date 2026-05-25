from .board import Board


class BoardMock(Board):
    """No-op implementation for unit tests on Windows."""

    def i2c_read_bytes(self, addr: int, register: int, length: int) -> bytes:
        return bytes(length)

    def i2c_write_bytes(self, addr: int, register: int, data: bytes) -> None:
        pass

    def i2c_read_byte(self, addr: int) -> int:
        return 0

    def i2c_write_raw(self, addr: int, data: bytes) -> None:
        pass

    def read_analog(self, channel: int) -> int:
        return 0

    def set_pwm(self, chip: int, channel: int, duty_us: float) -> None:
        pass

    def close(self) -> None:
        pass
