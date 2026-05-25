from abc import ABC, abstractmethod


class Board(ABC):
    """Hardware abstraction layer — one concrete impl per platform."""

    @abstractmethod
    def i2c_read_bytes(self, addr: int, register: int, length: int) -> bytes:
        ...

    @abstractmethod
    def i2c_write_bytes(self, addr: int, register: int, data: bytes) -> None:
        ...

    @abstractmethod
    def i2c_read_byte(self, addr: int) -> int:
        """Probe read — returns single byte, raises OSError if device absent."""
        ...

    @abstractmethod
    def i2c_write_raw(self, addr: int, data: bytes) -> None:
        """Write raw bytes to address with no register prefix (e.g. HS3003 trigger)."""
        ...

    @abstractmethod
    def read_analog(self, channel: int) -> int:
        """Returns 12-bit ADC value (0–4095)."""
        ...

    @abstractmethod
    def set_pwm(self, chip: int, channel: int, duty_us: float) -> None:
        """Set servo pulse width in microseconds."""
        ...

    @abstractmethod
    def close(self) -> None:
        ...
