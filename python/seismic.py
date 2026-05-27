import logging
import math
import threading
import time
from typing import Optional

import numpy as np

import config
from board import Board
from bridge import call_floats
from readings import SeismicReading

log = logging.getLogger(__name__)

def _classify_mpd(mpd: float) -> int:
    if mpd < config.MPD_CLASS1:
        return 0
    if mpd < config.MPD_CLASS2:
        return 1
    if mpd < config.MPD_CLASS3:
        return 2
    return 3


def compute_sta_lta(samples: np.ndarray, return_rejected: bool = False,
                     warmup_samples: int = 0):
    """Pure STA/LTA computation on a numpy array — used by tests and the live thread.

    Returns ratios array. If return_rejected=True, also returns a boolean mask
    indicating which samples were spike-rejected.

    warmup_samples: number of initial samples during which ratio is suppressed to 0.0
    to allow LTA to converge before triggers are evaluated. Default 0 (no suppression).
    Pass config.LTA_WARMUP_SAMPLES for production-equivalent behaviour.
    """
    n = len(samples)
    ratios   = np.zeros(n)
    rejected = np.zeros(n, dtype=bool)

    sta = 0.0
    lta = 1e-9
    mean_z = 0.0

    for i, v in enumerate(samples):
        # Tentatively compute updated mean using current sample
        new_mean_z = config.ALPHA * v + (1 - config.ALPHA) * mean_z
        cf = (v - new_mean_z) ** 2

        # Spike rejection — do NOT commit mean_z if spike, to prevent cascade contamination
        if lta > 1e-9 and cf > config.SPIKE_REJECT_FACTOR * lta:
            rejected[i] = True
            ratios[i] = 0.0 if i < warmup_samples else (sta / lta)
            continue

        # Not a spike: commit the mean update and advance filters
        mean_z = new_mean_z
        sta = config.ALPHA * cf + (1 - config.ALPHA) * sta
        lta = config.BETA  * cf + (1 - config.BETA)  * lta
        ratios[i] = 0.0 if i < warmup_samples else (sta / lta if lta > 1e-9 else 0.0)

    if return_rejected:
        return ratios, rejected
    return ratios


def _estimate_magnitude(acc_buffer: list[float]) -> Optional[float]:
    """Double-integrate acceleration → peak displacement → Mpd."""
    dt = 1.0 / config.SEISMIC_RATE_HZ
    acc = np.array(acc_buffer, dtype=float)
    # Detrend
    acc -= np.mean(acc)
    # Integrate to velocity, then to displacement (trapezoidal)
    vel  = np.cumsum(acc) * dt
    disp = np.cumsum(vel) * dt
    Pd_m = float(np.max(np.abs(disp)))
    if Pd_m <= 0:
        return None
    Pd_cm = Pd_m * 100.0
    return math.log10(Pd_cm) + 5.39  # Wu & Kanamori 2005


class SeismicSensor:
    def __init__(self, board: Board, shared_state: dict, lock: threading.Lock,
                 stop_event: threading.Event):
        self._board = board
        self._state = shared_state
        self._lock  = lock
        self._stop  = stop_event

    def _read_z_raw(self) -> Optional[float]:
        try:
            _, _, z_g, _, _, _ = call_floats(self._board, "sensor_accel", 6)
            return z_g * config.MODULINO_ACCEL_G_TO_MS2
        except Exception as e:
            log.debug("Bridge sensor_accel read error: %s", e)
            return None

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                self._loop()
            except Exception:
                log.exception("SeismicSensor crashed — restarting in 1s")
                time.sleep(1)

    def _loop(self) -> None:
        if not self._board.bridge_available:
            log.error("Seismic sensor unavailable: Arduino Bridge API is required")
            self._stop.wait(5)
            return

        sta       = 0.0
        lta       = 1e-9
        mean_z    = 0.0
        trigger_count = 0
        sample_count  = 0
        burst_buf: list[float] = []
        in_burst  = False
        seismic_class = 0
        Mpd: Optional[float] = None

        while not self._stop.is_set():
            v_z = self._read_z_raw()
            if v_z is None:
                time.sleep(0.02)
                continue

            sample_count += 1
            armed = sample_count > config.LTA_WARMUP_SAMPLES

            new_mean_z = config.ALPHA * v_z + (1 - config.ALPHA) * mean_z
            cf_t = (v_z - new_mean_z) ** 2

            # Spike rejection — don't commit mean_z to prevent cascade contamination
            if lta > 1e-9 and cf_t > config.SPIKE_REJECT_FACTOR * lta:
                ratio = sta / lta if armed else 0.0
                self._publish(v_z, cf_t, sta, lta, ratio, seismic_class, Mpd, in_burst)
                self._adaptive_sleep(ratio)
                continue

            mean_z = new_mean_z
            sta = config.ALPHA * cf_t + (1 - config.ALPHA) * sta
            lta = config.BETA  * cf_t + (1 - config.BETA)  * lta
            ratio = (sta / lta if lta > 1e-9 else 0.0) if armed else 0.0

            if armed and ratio >= config.RATIO_TRIGGER:
                trigger_count += 1
            else:
                trigger_count = 0

            if trigger_count >= config.MIN_TRIGGER_SAMPLES and not in_burst:
                in_burst  = True
                burst_buf = []

            if in_burst:
                burst_buf.append(v_z)
                if len(burst_buf) >= config.POST_TRIGGER_SAMPLES:
                    Mpd = _estimate_magnitude(burst_buf)
                    seismic_class = _classify_mpd(Mpd) if Mpd is not None else 0
                    in_burst = False
                    burst_buf = []

            self._publish(v_z, cf_t, sta, lta, ratio, seismic_class, Mpd, in_burst)
            self._adaptive_sleep(ratio)

    def _publish(self, v_z, cf_t, sta, lta, ratio, sc, mpd, in_burst) -> None:
        reading = SeismicReading(
            timestamp=time.time(),
            v_z=v_z, cf_t=cf_t, sta=sta, lta=lta, ratio=ratio,
            seismic_class=sc, Mpd=mpd, in_burst=in_burst,
        )
        with self._lock:
            self._state['seismic'] = reading

    @staticmethod
    def _adaptive_sleep(ratio: float) -> None:
        time.sleep(0.02 if ratio > 3.0 else 0.1)
