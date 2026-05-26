import logging
import math
import statistics
import threading
import time
from collections import deque
from typing import Optional

import config
from board import Board
from bridge import call_floats, call_int
from readings import EnvironmentalReading

log = logging.getLogger(__name__)

def _adc_to_voltage(raw: int) -> float:
    return raw * config.MQ2_ADC_REF_VOLTAGE / config.MQ2_ADC_MAX_RAW


def _voltage_to_ppm(voltage: float, r0: float) -> float:
    """MQ2 LPG/smoke approximation using Rs/R0 power-law curve."""
    vc = 5.0  # circuit voltage
    rl = config.MQ2_LOAD_RESISTANCE_KOHM
    if voltage <= 0:
        return 0.0
    rs = (vc - voltage) / voltage * rl
    ratio = rs / r0 if r0 > 0 else config.MQ2_CLEAN_AIR_FACTOR
    # Power-law fit for smoke/LPG from MQ2 datasheet
    ppm = 613.9 * math.pow(ratio, -2.074)
    return max(0.0, ppm)


class EnvironmentalSensor:
    def __init__(self, board: Board, shared_state: dict, lock: threading.Lock,
                 stop_event: threading.Event):
        self._board    = board
        self._state    = shared_state
        self._lock     = lock
        self._stop     = stop_event
        self._start_t  = time.time()
        self._calib_readings: list[float] = []
        self._r0: Optional[float] = None                 # MQ2 R0 baseline
        self._temp_baseline:  Optional[float] = None
        self._humid_baseline: Optional[float] = None
        self._gas_baseline:   Optional[float] = None
        self._mq2_buf: deque[float] = deque(maxlen=config.MQ2_MEDIAN_WINDOW)

    # --- Modulino Thermo ---

    def _read_hs3003(self) -> Optional[tuple[float, float]]:
        try:
            temp_c, humidity = call_floats(self._board, "sensor_env", 2)
            return temp_c, humidity
        except Exception as e:
            log.debug("Bridge sensor_env read error: %s", e)
            return None

    # --- MQ2 ---

    def _elapsed(self) -> float:
        return time.time() - self._start_t

    def _mq2_status(self) -> str:
        elapsed = self._elapsed()
        if elapsed < config.MQ2_WARMUP_SEC:
            return "INACTIVE"
        if self._r0 is None:
            return "CALIBRATING"
        return "OK"

    def _read_gas_ppm(self) -> Optional[float]:
        try:
            raw = call_int(self._board, "sensor_mq2")
            voltage = _adc_to_voltage(raw)
            r0 = self._r0 if self._r0 else config.MQ2_LOAD_RESISTANCE_KOHM / config.MQ2_CLEAN_AIR_FACTOR
            ppm = _voltage_to_ppm(voltage, r0)
        except Exception as e:
            log.debug("Bridge sensor_mq2 read error: %s", e)
            return None

        self._mq2_buf.append(ppm)
        if len(self._mq2_buf) >= config.MQ2_MEDIAN_WINDOW:
            var = statistics.variance(self._mq2_buf)
            if var > config.MQ2_NOISE_VAR_THRESHOLD:
                return statistics.median(self._mq2_buf)
        return ppm

    def _calibrate(self, ppm: float) -> None:
        """Accumulate readings during calibration window, then fix R0."""
        elapsed = self._elapsed()
        if config.MQ2_WARMUP_SEC <= elapsed < config.MQ2_WARMUP_SEC + config.MQ2_CALIB_SEC:
            self._calib_readings.append(ppm)
        elif elapsed >= config.MQ2_WARMUP_SEC + config.MQ2_CALIB_SEC and self._r0 is None:
            if self._calib_readings:
                avg_ppm = sum(self._calib_readings) / len(self._calib_readings)
                # Back-calculate R0 from average ppm
                # ppm = 613.9 * (Rs/R0)^-2.074  →  Rs/R0 = (ppm/613.9)^(-1/2.074)
                ratio = math.pow(avg_ppm / 613.9, -1 / 2.074)
                rl    = config.MQ2_LOAD_RESISTANCE_KOHM
                self._r0 = rl / ratio
                self._gas_baseline  = avg_ppm
                log.info("MQ2 calibrated: R0=%.2f kΩ, gas_baseline=%.1f ppm", self._r0, avg_ppm)

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                self._loop()
            except Exception:
                log.exception("EnvironmentalSensor crashed — restarting in 1s")
                time.sleep(1)

    def _loop(self) -> None:
        if not self._board.bridge_available:
            log.error("Environmental sensor unavailable: Arduino Bridge API is required")
            self._stop.wait(5)
            return

        calib_temps:  list[float] = []
        calib_humids: list[float] = []

        while not self._stop.is_set():
            ths = self._read_hs3003()
            status = self._mq2_status()

            temp_c: Optional[float]   = None
            humid:  Optional[float]   = None
            gas:    Optional[float]   = None

            if ths is not None:
                temp_c, humid = ths

                # Accumulate baselines during warmup + calibration window
                elapsed = self._elapsed()
                if (config.MQ2_WARMUP_SEC
                        <= elapsed
                        < config.MQ2_WARMUP_SEC + config.MQ2_CALIB_SEC):
                    calib_temps.append(temp_c)
                    calib_humids.append(humid)
                elif (elapsed >= config.MQ2_WARMUP_SEC + config.MQ2_CALIB_SEC
                      and self._temp_baseline is None
                      and calib_temps):
                    self._temp_baseline  = sum(calib_temps)  / len(calib_temps)
                    self._humid_baseline = sum(calib_humids) / len(calib_humids)
                    log.info("Env baselines: temp=%.1f°C humid=%.1f%%",
                             self._temp_baseline, self._humid_baseline)

            if status != "INACTIVE":
                raw_ppm = self._read_gas_ppm()
                if raw_ppm is not None:
                    self._calibrate(raw_ppm)
                    gas = raw_ppm

            reading = EnvironmentalReading(
                timestamp=time.time(),
                temperature_c=temp_c if temp_c is not None else 0.0,
                humidity_pct=humid  if humid  is not None else 0.0,
                gas_ppm=gas,
                mq2_status=status,
                temp_baseline=self._temp_baseline,
                humid_baseline=self._humid_baseline,
                gas_baseline=self._gas_baseline,
            )
            with self._lock:
                self._state['env'] = reading

            time.sleep(1.0 / config.ENV_HZ)
