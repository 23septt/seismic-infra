import logging
import math
import threading
import time
from typing import Optional

import config
from board import Board
from bridge import call_floats
from readings import SpatialReading

log = logging.getLogger(__name__)


class SpatialSensor:
    def __init__(self, board: Board, shared_state: dict, lock: threading.Lock,
                 stop_event: threading.Event):
        self._board = board
        self._state = shared_state
        self._lock = lock
        self._stop = stop_event
        self._last_roll: Optional[float] = None
        self._last_pitch: Optional[float] = None
        self._last_yaw: Optional[float] = None

    def _read_distance_mm(self) -> Optional[float]:
        try:
            return call_floats(self._board, "sensor_distance", 1)[0]
        except Exception as e:
            log.debug("Bridge sensor_distance read error: %s", e)
            return None

    def _read_motion_magnitude(self, interval: float) -> float:
        try:
            _, _, _, roll, pitch, yaw = call_floats(self._board, "sensor_accel", 6)
        except Exception as e:
            log.debug("Bridge sensor_accel spatial read error: %s", e)
            return 0.0

        if self._last_roll is None:
            self._last_roll = roll
            self._last_pitch = pitch
            self._last_yaw = yaw
            return 0.0

        mag = math.sqrt(
            (roll - self._last_roll) ** 2
            + (pitch - self._last_pitch) ** 2
            + (yaw - self._last_yaw) ** 2
        ) / max(interval, 1e-6)
        self._last_roll = roll
        self._last_pitch = pitch
        self._last_yaw = yaw
        return mag

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                self._loop()
            except Exception:
                log.exception("SpatialSensor crashed — restarting in 1s")
                time.sleep(1)

    def _loop(self) -> None:
        if not self._board.bridge_available:
            log.error("Spatial sensor unavailable: Arduino Bridge API is required")
            self._stop.wait(5)
            return

        interval = 1.0 / config.SPATIAL_HZ

        while not self._stop.is_set():
            gyro_mag = self._read_motion_magnitude(interval)
            reading = SpatialReading(
                timestamp=time.time(),
                distance_mm=self._read_distance_mm(),
                motion_detected=gyro_mag > config.MOTION_THRESHOLD,
                gyro_magnitude=gyro_mag,
            )
            with self._lock:
                self._state['spatial'] = reading

            time.sleep(interval)
