import logging
import threading
from typing import Optional

import config
from board import Board
from decision import HazardAssessment

log = logging.getLogger(__name__)


class PixelController:
    """Drives Modulino Pixels through Arduino Bridge RPC."""

    def __init__(self, board: Board):
        self._board = board
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._alert_class = 0
        self._alert_kind = "all_clear"

    def apply(self, assessment: HazardAssessment) -> None:
        self._alert_class = assessment.final_class
        self._alert_kind = assessment.alert_kind
        if self._thread and self._thread.is_alive():
            self._stop.set()
            self._thread.join(timeout=0.5)
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _set_all(self, r: int, g: int, b: int,
                 brightness: int = config.PIXEL_BRIGHTNESS) -> None:
        ok = self._board.bridge_notify(
            "pixels_set_all", r, g, b, brightness, config.PIXEL_COUNT
        )
        if not ok:
            log.debug("Pixel Bridge notify failed")

    def _all_off(self) -> None:
        self._set_all(0, 0, 0, 0)

    def _color(self) -> tuple[int, int, int]:
        if self._alert_kind == "fire":
            return (255, 48, 0)
        if self._alert_kind == "earthquake":
            return (0, 80, 255)
        if self._alert_kind == "combined":
            return (255, 0, 255)
        return config.PIXEL_COLOR.get(self._alert_class, (255, 0, 0))

    def _run(self) -> None:
        cls = self._alert_class
        r, g, b = self._color()
        try:
            if cls == 0:
                self._set_all(r, g, b)
                self._stop.wait()
            elif cls == 1:
                while not self._stop.is_set():
                    self._set_all(r, g, b)
                    self._stop.wait(0.5)
                    self._all_off()
                    self._stop.wait(0.5)
            elif cls == 2:
                while not self._stop.is_set():
                    self._set_all(r, g, b)
                    self._stop.wait(0.25)
                    self._all_off()
                    self._stop.wait(0.25)
            else:
                while not self._stop.is_set():
                    self._set_all(r, g, b, 255)
                    self._stop.wait(0.1)
                    self._all_off()
                    self._stop.wait(0.1)
        finally:
            self._all_off()


class BuzzerController:
    """Drives Modulino Buzzer through Arduino Bridge RPC."""

    def __init__(self, board: Board):
        self._board = board
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def _send(self, freq_hz: int, duration_ms: int) -> None:
        if not self._board.bridge_notify("buzzer_tone", freq_hz, duration_ms):
            log.debug("Buzzer Bridge notify failed")

    def _silence(self) -> None:
        self._send(0, 0)

    def apply(self, assessment: HazardAssessment) -> None:
        if self._thread and self._thread.is_alive():
            self._stop.set()
            self._thread.join(timeout=0.5)
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, args=(assessment,), daemon=True)
        self._thread.start()

    def _run(self, assessment: HazardAssessment) -> None:
        try:
            if assessment.final_class == 0:
                self._silence()
            elif assessment.alert_kind == "fire":
                self._fire_alarm()
            elif assessment.alert_kind == "earthquake":
                self._earthquake_alarm()
            elif assessment.alert_kind == "combined":
                self._combined_alarm()
            else:
                self._caution_alarm()
        finally:
            self._silence()

    def _caution_alarm(self) -> None:
        for _ in range(3):
            if self._stop.is_set():
                break
            self._send(1800, 220)
            self._stop.wait(0.45)

    def _fire_alarm(self) -> None:
        while not self._stop.is_set():
            self._send(3300, 220)
            self._stop.wait(0.22)
            self._send(2200, 220)
            self._stop.wait(0.22)

    def _earthquake_alarm(self) -> None:
        while not self._stop.is_set():
            for _ in range(3):
                if self._stop.is_set():
                    break
                self._send(1200, 120)
                self._stop.wait(0.16)
            self._stop.wait(0.55)

    def _combined_alarm(self) -> None:
        while not self._stop.is_set():
            self._fire_alarm_step()
            if self._stop.wait(0.12):
                break
            self._send(1200, 140)
            self._stop.wait(0.18)

    def _fire_alarm_step(self) -> None:
        self._send(3300, 180)
        self._stop.wait(0.18)
        self._send(2200, 180)
        self._stop.wait(0.18)


class ActuatorController:
    """Coordinates pixels and buzzer for a given alert."""

    def __init__(self, board: Board):
        self._pixels = PixelController(board)
        self._buzzer = BuzzerController(board)

    def apply(self, assessment: HazardAssessment) -> None:
        log.info("Actuators -> class %d (%s)",
                 assessment.final_class, assessment.alert_kind)
        self._pixels.apply(assessment)
        self._buzzer.apply(assessment)
