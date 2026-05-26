import logging
from typing import Any

import config
from board import Board

log = logging.getLogger(__name__)


class BoardQRB(Board):
    """Concrete implementation for Qualcomm QRB2210 on Arduino UNO Q.

    Modulino I/O → Arduino Bridge RPC
    PWM  → /sys/class/pwm sysfs via python-periphery
    """

    def __init__(self):
        self._bridge = self._init_bridge()
        self._pwm_handles: dict[tuple[int, int], object] = {}

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

    def set_pwm(self, chip: int, channel: int, duty_us: float) -> None:
        key = (chip, channel)
        try:
            from periphery import PWM
            if key not in self._pwm_handles:
                pwm = PWM(chip, channel)
                pwm.frequency = config.SERVO_FREQ_HZ
                pwm.enable()
                self._pwm_handles[key] = pwm
            period_us = 1_000_000 / config.SERVO_FREQ_HZ
            self._pwm_handles[key].duty_cycle = duty_us / period_us
        except Exception as e:
            log.error("PWM set failed chip=%d ch=%d duty_us=%.1f: %s", chip, channel, duty_us, e)

    # ------------------------------------------------------------------

    def close(self) -> None:
        for pwm in self._pwm_handles.values():
            try:
                pwm.disable()
                pwm.close()
            except Exception:
                pass
