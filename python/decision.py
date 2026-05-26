import time
from dataclasses import dataclass, field
from typing import Optional

import config
from readings import EnvironmentalReading, SeismicReading


@dataclass
class HazardAssessment:
    timestamp: float
    seismic_class: int
    env_upgrade: int
    final_class: int
    Mpd: Optional[float]
    flags: dict = field(default_factory=dict)


def make_assessment(
    seismic: Optional[SeismicReading],
    env: Optional[EnvironmentalReading],
) -> HazardAssessment:
    """Pure function — no hardware access, fully unit-testable."""

    seismic_class = seismic.seismic_class if seismic is not None else 0
    Mpd           = seismic.Mpd          if seismic is not None else None

    flags = {
        "GAS_CAUTION":    False,
        "GAS_CRITICAL":   False,
        "TEMP_ELEVATED":  False,
        "TEMP_CRITICAL":  False,
        "HUMID_DROP":     False,
        "HUMID_CRITICAL": False,
    }

    if env is not None and env.mq2_status == "OK":
        gas_b   = env.gas_baseline   or 0.0
        temp_b  = env.temp_baseline  or env.temperature_c
        humid_b = env.humid_baseline or env.humidity_pct

        gas_delta   = (env.gas_ppm or 0.0) - gas_b
        temp_delta  = env.temperature_c - temp_b
        humid_delta = env.humidity_pct  - humid_b

        flags["GAS_CAUTION"]    = gas_delta   >= config.GAS_CAUTION_DELTA
        flags["GAS_CRITICAL"]   = gas_delta   >= config.GAS_CRITICAL_DELTA
        flags["TEMP_ELEVATED"]  = temp_delta  >= config.TEMP_ELEVATED_DELTA
        flags["TEMP_CRITICAL"]  = temp_delta  >= config.TEMP_CRITICAL_DELTA
        flags["HUMID_DROP"]     = humid_delta <= config.HUMID_DROP_DELTA
        flags["HUMID_CRITICAL"] = humid_delta <= config.HUMID_CRITICAL_DELTA

    # env_upgrade logic
    env_upgrade = 0
    if (flags["GAS_CRITICAL"]
            or flags["TEMP_CRITICAL"]
            or flags["HUMID_CRITICAL"]):
        env_upgrade = 1
    if flags["GAS_CAUTION"] and flags["TEMP_ELEVATED"]:  # compound
        env_upgrade = max(env_upgrade, 1)

    final_class = min(seismic_class + env_upgrade, 3)

    # Standalone env trigger (no seismic event) → force at least class 2
    if seismic_class == 0 and (flags["GAS_CRITICAL"] or flags["TEMP_CRITICAL"]):
        final_class = max(final_class, 2)

    return HazardAssessment(
        timestamp=time.time(),
        seismic_class=seismic_class,
        env_upgrade=env_upgrade,
        final_class=final_class,
        Mpd=Mpd,
        flags=flags,
    )
