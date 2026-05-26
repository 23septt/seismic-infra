import logging
import threading
import time
from typing import Optional

from .. import config
from ..hal.board import Board

log = logging.getLogger(__name__)


class PixelController:
    """Drives Modulino Pixels LED ring over I2C (addr 0x6C)."""

    def __init__(self, board: Board):
        self._board   = board
        self._thread: Optional[threading.Thread] = None
        self._stop    = threading.Event()
        self._current_class = 0

    def apply(self, alert_class: int) -> None:
        self._current_class = alert_class
        if self._thread and self._thread.is_alive():
            self._stop.set()
            self._thread.join(timeout=0.5)
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _set_all(self, r: int, g: int, b: int, brightness: int = config.PIXEL_BRIGHTNESS) -> None:
        if self._board.bridge_notify(
            "pixels_set_all", r, g, b, brightness, config.PIXEL_COUNT
        ):
            return
        try:
            payload = bytes([r, g, b, brightness] * config.PIXEL_COUNT)
            self._board.i2c_write_bytes(config.PIXELS_ADDR, 0x00, payload)
        except Exception as e:
            log.debug("Pixel write error: %s", e)

    def _all_off(self) -> None:
        self._set_all(0, 0, 0, 0)

    def _run(self) -> None:
        cls = self._current_class
        r, g, b = config.PIXEL_COLOR[cls]
        try:
            if cls == 0:
                self._set_all(r, g, b)
                self._stop.wait()
            elif cls == 1:
                # 1 Hz pulse
                while not self._stop.is_set():
                    self._set_all(r, g, b)
                    self._stop.wait(0.5)
                    self._all_off()
                    self._stop.wait(0.5)
            elif cls == 2:
                # 2 Hz pulse
                while not self._stop.is_set():
                    self._set_all(r, g, b)
                    self._stop.wait(0.25)
                    self._all_off()
                    self._stop.wait(0.25)
            else:
                # 5 Hz strobe
                while not self._stop.is_set():
                    self._set_all(r, g, b)
                    self._stop.wait(0.1)
                    self._all_off()
                    self._stop.wait(0.1)
        finally:
            self._all_off()


class BuzzerController:
    """Drives Modulino Buzzer over I2C (addr 0x3C).

    Packet format: [freq_hi, freq_lo, dur_hi, dur_lo]
    """

    def __init__(self, board: Board):
        self._board   = board
        self._thread: Optional[threading.Thread] = None
        self._stop    = threading.Event()

    def _send(self, freq_hz: int, duration_ms: int) -> None:
        if self._board.bridge_notify("buzzer_tone", freq_hz, duration_ms):
            return
        try:
            data = bytes([
                (freq_hz >> 8) & 0xFF, freq_hz & 0xFF,
                (duration_ms >> 8) & 0xFF, duration_ms & 0xFF,
            ])
            self._board.i2c_write_bytes(config.BUZZER_ADDR, 0x00, data)
        except Exception as e:
            log.debug("Buzzer write error: %s", e)

    def _silence(self) -> None:
        self._send(0, 0)

    def apply(self, alert_class: int) -> None:
        if self._thread and self._thread.is_alive():
            self._stop.set()
            self._thread.join(timeout=0.5)
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, args=(alert_class,), daemon=True)
        self._thread.start()

    def _run(self, cls: int) -> None:
        try:
            if cls == 0:
                self._silence()
            elif cls == 1:
                for _ in range(3):
                    if self._stop.is_set():
                        break
                    self._send(1000, 200)
                    self._stop.wait(0.4)
            else:
                # Continuous: repeat beep until stopped
                while not self._stop.is_set():
                    self._send(1500, 100)
                    self._stop.wait(0.15)
        finally:
            self._silence()


class ServoController:
    """Two SG90 servos driven via board PWM."""

    def __init__(self, board: Board):
        self._board = board

    def _set(self, chip: int, channel: int, duty_us: float) -> None:
        try:
            self._board.set_pwm(chip, channel, duty_us)
        except Exception as e:
            log.error("Servo PWM error chip=%d ch=%d: %s", chip, channel, e)

    def apply(self, alert_class: int) -> None:
        if alert_class < 2:
            self._set(config.SERVO1_PWM_CHIP, config.SERVO1_PWM_CH, config.SERVO_NEUTRAL_US)
            self._set(config.SERVO2_PWM_CHIP, config.SERVO2_PWM_CH, config.SERVO_NEUTRAL_US)
        elif alert_class == 2:
            self._set(config.SERVO1_PWM_CHIP, config.SERVO1_PWM_CH, config.SERVO_CLOSE_US)
            self._set(config.SERVO2_PWM_CHIP, config.SERVO2_PWM_CH, config.SERVO_NEUTRAL_US)
        else:
            self._set(config.SERVO1_PWM_CHIP, config.SERVO1_PWM_CH, config.SERVO_CLOSE_US)
            self._set(config.SERVO2_PWM_CHIP, config.SERVO2_PWM_CH, config.SERVO_DEPLOY_US)


class ActuatorController:
    """Facade that coordinates all actuators for a given alert class."""

    def __init__(self, board: Board):
        self._pixels  = PixelController(board)
        self._buzzer  = BuzzerController(board)
        self._servos  = ServoController(board)

    def apply(self, alert_class: int) -> None:
        log.info("Actuators → class %d", alert_class)
        self._pixels.apply(alert_class)
        self._buzzer.apply(alert_class)
        self._servos.apply(alert_class)
