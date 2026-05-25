from dataclasses import dataclass
from typing import Optional

__all__ = ["SeismicReading", "EnvironmentalReading", "SpatialReading", "VisionResult"]


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
    gas_ppm: Optional[float]
    mq2_status: str          # "INACTIVE" | "CALIBRATING" | "OK"
    temp_baseline: Optional[float]
    humid_baseline: Optional[float]
    gas_baseline: Optional[float]


@dataclass
class SpatialReading:
    timestamp: float
    distance_mm: Optional[float]
    motion_detected: bool
    gyro_magnitude: float


@dataclass
class VisionResult:
    timestamp: float
    available: bool
    motion_detected: bool
    confidence: float
