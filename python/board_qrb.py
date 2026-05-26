import logging
from typing import Any

from board import Board

log = logging.getLogger(__name__)


class BoardQRB(Board):
    """Concrete implementation for Qualcomm QRB2210 on Arduino UNO Q.

    Modulino I/O → Arduino Bridge RPC
    """

    def __init__(self):
        self._bridge = self._init_bridge()

    def _init_bridge(self):
        try:
            from arduino.app_utils import Bridge
            log.info("Arduino Bridge API available")
            return Bridge
        except Exception as e:
            log.info("Arduino Bridge API unavailable: %s", e)
            return None

    @property
    def bridge_available(self) -> bool:
        return self._bridge is not None

    # ------------------------------------------------------------------
    # Arduino Bridge RPC
    # ------------------------------------------------------------------

    def bridge_notify(self, method: str, *args: Any) -> bool:
        if self._bridge is None:
            return False
        try:
            self._bridge.call(method, *args)
            return True
        except ValueError as e:
            log.error("Bridge message too large for %s: %s", method, e)
            return False
        except Exception as e:
            log.debug("Bridge call failed for %s: %s", method, e)
            return False

    def bridge_call(self, method: str, *args: Any) -> Any:
        if self._bridge is None:
            raise RuntimeError("Arduino Bridge API is not available")
        return self._bridge.call(method, *args)

    def bridge_provide(self, method: str, callback: Any) -> bool:
        if self._bridge is None:
            return False
        try:
            self._bridge.provide(method, callback)
            return True
        except Exception as e:
            log.debug("Bridge provide failed for %s: %s", method, e)
            return False

    def close(self) -> None:
        pass
