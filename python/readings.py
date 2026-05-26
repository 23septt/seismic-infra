from dataclasses import dataclass
from typing import Optional

__all__ = ["SeismicReading", "EnvironmentalReading"]


@dataclass
class SeismicReading:
    timestamp: float
    v_z: float
    cf_t: float
    sta: float
    lta: float
    ratio: float
    seismic_class: int
    Mpd: Optional[float]
    in_burst: bool


@dataclass
class EnvironmentalReading:
    timestamp: float
    temperature_c: float
    humidity_pct: float
    dht_temperature_c: Optional[float]
    dht_humidity_pct: Optional[float]
    status: str              # "UNAVAILABLE" | "CALIBRATING" | "OK"
    temp_baseline: Optional[float]
    humid_baseline: Optional[float]
