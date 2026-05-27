"""Unit tests for decision.py, no hardware required."""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))

from decision import make_assessment
from readings import EnvironmentalReading, SeismicReading


def _seismic(cls: int, mpd: float = None) -> SeismicReading:
    return SeismicReading(
        timestamp=time.time(), v_z=0.0, cf_t=0.0, sta=0.0, lta=1e-9, ratio=0.0,
        seismic_class=cls, Mpd=mpd, in_burst=False,
    )


def _env(temp: float = 25.0, humid: float = 60.0, status: str = "OK") -> EnvironmentalReading:
    return EnvironmentalReading(
        timestamp=time.time(),
        temperature_c=temp,
        humidity_pct=humid,
        dht_temperature_c=temp,
        dht_humidity_pct=humid,
        status=status,
        temp_baseline=25.0,
        humid_baseline=60.0,
    )


def test_no_seismic_no_env():
    a = make_assessment(None, None)
    assert a.final_class == 0
    assert a.alert_kind == "all_clear"


def test_earthquake_alert_kind():
    a = make_assessment(_seismic(2, mpd=5.5), None)
    assert a.final_class == 2
    assert a.alert_kind == "earthquake"


def test_fire_temp_elevated():
    a = make_assessment(_seismic(0), _env(temp=41.0, humid=58.0))
    assert a.fire_class == 1
    assert a.final_class == 1
    assert a.alert_kind == "fire"
    assert a.flags["FIRE_TEMP_ELEVATED"]


def test_fire_temp_and_humidity_drop_class2():
    a = make_assessment(_seismic(0), _env(temp=42.0, humid=40.0))
    assert a.fire_class == 2
    assert a.final_class == 2
    assert a.alert_kind == "fire"
    assert a.flags["FIRE_HUMIDITY_DROPPING"]


def test_fire_temp_critical_class3():
    a = make_assessment(_seismic(0), _env(temp=52.0, humid=45.0))
    assert a.fire_class == 3
    assert a.final_class == 3
    assert a.alert_kind == "fire"
    assert a.flags["FIRE_TEMP_CRITICAL"]


def test_combined_fire_and_earthquake():
    a = make_assessment(_seismic(2, mpd=5.5), _env(temp=52.0, humid=45.0))
    assert a.fire_class == 3
    assert a.seismic_class == 2
    assert a.final_class == 3
    assert a.alert_kind == "combined"


def test_env_unavailable_does_not_fire():
    a = make_assessment(_seismic(0), _env(temp=55.0, humid=20.0, status="UNAVAILABLE"))
    assert a.fire_class == 0
    assert a.final_class == 0
    assert a.alert_kind == "all_clear"


def test_env_calibrating_absolute_critical_still_fires():
    a = make_assessment(_seismic(0), _env(temp=55.0, humid=20.0, status="CALIBRATING"))
    assert a.fire_class == 3
    assert a.final_class == 3
    assert a.alert_kind == "fire"
