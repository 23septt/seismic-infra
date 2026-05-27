from typing import Any


class Board:
    """Hardware abstraction layer — one concrete impl per platform."""

    def bridge_notify(self, method: str, *args: Any) -> bool:
        """Invoke an Arduino Bridge RPC method without using its return value."""
        return False

    def bridge_call(self, method: str, *args: Any) -> Any:
        """Call an Arduino Bridge RPC method if available."""
        raise NotImplementedError("Arduino Bridge is not available on this board")

    def bridge_provide(self, method: str, callback: Any) -> bool:
        """Expose a Linux callback to the MCU through Arduino Bridge if available."""
        return False

    @property
    def bridge_available(self) -> bool:
        return False

    def close(self) -> None:
        pass
