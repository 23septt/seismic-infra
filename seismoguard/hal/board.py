from abc import ABC, abstractmethod
from typing import Any


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

    def bridge_notify(self, method: str, *args: Any) -> bool:
        """Send a fire-and-forget Arduino Bridge RPC message if available."""
        return False

    def bridge_call(self, method: str, *args: Any) -> Any:
        """Call an Arduino Bridge RPC method if available."""
        raise NotImplementedError("Arduino Bridge is not available on this board")

    def bridge_provide(self, method: str, callback: Any) -> bool:
        """Expose a Linux callback to the MCU through Arduino Bridge if available."""
        return False

    @abstractmethod
    def set_pwm(self, chip: int, channel: int, duty_us: float) -> None:
        """Set servo pulse width in microseconds."""
        ...

    @abstractmethod
    def close(self) -> None:
        ...
