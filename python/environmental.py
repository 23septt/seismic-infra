import logging
import math
import threading
import time
from typing import Optional

import config
from board import Board
from bridge import call_floats
from readings import EnvironmentalReading

log = logging.getLogger(__name__)


def _valid(value: Optional[float]) -> bool:
    return value is not None and math.isfinite(value)


class EnvironmentalSensor:
    def __init__(self, board: Board, shared_state: dict, lock: threading.Lock,
                 stop_event: threading.Event):
        self._board = board
        self._state = shared_state
        self._lock = lock
        self._stop = stop_event
        self._start_t = time.time()
        self._temp_samples: list[float] = []
        self._humid_samples: list[float] = []
        self._temp_baseline: Optional[float] = None
        self._humid_baseline: Optional[float] = None

    def _read_environment(self) -> tuple[Optional[float], Optional[float],
                                        Optional[float], Optional[float]]:
        try:
            values = call_floats(self._board, "sensor_env", 4)
            thermo_temp, thermo_humid, dht_temp, dht_humid = values
            return thermo_temp, thermo_humid, dht_temp, dht_humid
        except Exception as e:
            log.debug("Bridge sensor_env read error: %s", e)
            return None, None, None, None

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                self._loop()
            except Exception:
                log.exception("EnvironmentalSensor crashed, restarting in 1s")
                time.sleep(1)

    def _loop(self) -> None:
        if not self._board.bridge_available:
            log.error("Environmental sensor unavailable: Arduino Bridge API is required")
            self._stop.wait(5)
            return

        while not self._stop.is_set():
            thermo_temp, thermo_humid, dht_temp, dht_humid = self._read_environment()

            temp_values = [v for v in (thermo_temp, dht_temp) if _valid(v)]
            humid_values = [v for v in (thermo_humid, dht_humid) if _valid(v)]

            temp_c = max(temp_values) if temp_values else 0.0
            humid_pct = min(humid_values) if humid_values else 0.0

            if temp_values and humid_values:
                elapsed = time.time() - self._start_t
                if elapsed < config.ENV_BASELINE_SEC:
                    self._temp_samples.append(temp_c)
                    self._humid_samples.append(humid_pct)
                    status = "CALIBRATING"
                else:
                    if self._temp_baseline is None and self._temp_samples:
                        self._temp_baseline = sum(self._temp_samples) / len(self._temp_samples)
                        self._humid_baseline = sum(self._humid_samples) / len(self._humid_samples)
                        log.info("Env baselines: temp=%.1fC humid=%.1f%%",
                                 self._temp_baseline, self._humid_baseline)
                    status = "OK"
            else:
                status = "UNAVAILABLE"

            reading = EnvironmentalReading(
                timestamp=time.time(),
                temperature_c=temp_c,
                humidity_pct=humid_pct,
                dht_temperature_c=dht_temp if _valid(dht_temp) else None,
                dht_humidity_pct=dht_humid if _valid(dht_humid) else None,
                status=status,
                temp_baseline=self._temp_baseline,
                humid_baseline=self._humid_baseline,
            )
            with self._lock:
                self._state["env"] = reading

            time.sleep(1.0 / config.ENV_HZ)
