import time
from dataclasses import dataclass, field
from typing import Optional

import config
from readings import EnvironmentalReading, SeismicReading


@dataclass
class HazardAssessment:
    timestamp: float
    seismic_class: int
    fire_class: int
    final_class: int
    Mpd: Optional[float]
    alert_kind: str
    flags: dict = field(default_factory=dict)


def make_assessment(
    seismic: Optional[SeismicReading],
    env: Optional[EnvironmentalReading],
) -> HazardAssessment:
    """Pure function — no hardware access, fully unit-testable."""

    seismic_class = seismic.seismic_class if seismic is not None else 0
    Mpd           = seismic.Mpd          if seismic is not None else None

    flags = {
        "FIRE_TEMP_ELEVATED": False,
        "FIRE_TEMP_CRITICAL": False,
        "FIRE_TEMP_RISING_FAST": False,
        "FIRE_HUMIDITY_DROPPING": False,
    }

    fire_class = 0
    if env is not None and env.status != "UNAVAILABLE":
        temp_b = env.temp_baseline or env.temperature_c
        humid_b = env.humid_baseline or env.humidity_pct
        temp_delta = env.temperature_c - temp_b
        humid_delta = env.humidity_pct - humid_b

        flags["FIRE_TEMP_ELEVATED"] = (
            env.temperature_c >= config.FIRE_TEMP_ELEVATED_C
            or temp_delta >= config.FIRE_TEMP_ELEVATED_DELTA
        )
        flags["FIRE_TEMP_CRITICAL"] = (
            env.temperature_c >= config.FIRE_TEMP_CRITICAL_C
            or temp_delta >= config.FIRE_TEMP_CRITICAL_DELTA
        )
        flags["FIRE_TEMP_RISING_FAST"] = temp_delta >= config.FIRE_TEMP_CRITICAL_DELTA
        flags["FIRE_HUMIDITY_DROPPING"] = humid_delta <= config.FIRE_HUMID_DROP_DELTA

        if flags["FIRE_TEMP_CRITICAL"]:
            fire_class = 3
        elif flags["FIRE_TEMP_ELEVATED"] and flags["FIRE_HUMIDITY_DROPPING"]:
            fire_class = 2
        elif flags["FIRE_TEMP_ELEVATED"]:
            fire_class = 1

    final_class = max(seismic_class, fire_class)
    if seismic_class > 0 and fire_class > 0:
        alert_kind = "combined"
    elif fire_class > 0:
        alert_kind = "fire"
    elif seismic_class > 0:
        alert_kind = "earthquake"
    else:
        alert_kind = "all_clear"

    return HazardAssessment(
        timestamp=time.time(),
        seismic_class=seismic_class,
        fire_class=fire_class,
        final_class=final_class,
        Mpd=Mpd,
        alert_kind=alert_kind,
        flags=flags,
    )
