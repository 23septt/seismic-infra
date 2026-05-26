"""Unit tests for fusion/decision.py — pure logic, no hardware."""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))

from decision import make_assessment
from readings import EnvironmentalReading, SeismicReading


# ---------------------------------------------------------------------------
# Helpers — build minimal dataclass instances
# ---------------------------------------------------------------------------

def _seismic(cls: int, mpd: float = None) -> SeismicReading:
    return SeismicReading(
        timestamp=time.time(), v_z=0.0, cf_t=0.0, sta=0.0, lta=1e-9, ratio=0.0,
        seismic_class=cls, Mpd=mpd, in_burst=False,
    )


def _env(gas_delta: float = 0.0, temp_delta: float = 0.0, humid_delta: float = 0.0,
         status: str = "OK") -> EnvironmentalReading:
    base_temp  = 25.0
    base_humid = 60.0
    base_gas   = 100.0
    return EnvironmentalReading(
        timestamp=time.time(),
        temperature_c=base_temp  + temp_delta,
        humidity_pct= base_humid + humid_delta,
        gas_ppm=      base_gas   + gas_delta,
        mq2_status=status,
        temp_baseline=base_temp,
        humid_baseline=base_humid,
        gas_baseline=base_gas,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_no_seismic_no_env():
    a = make_assessment(None, None)
    assert a.final_class == 0
    assert a.env_upgrade == 0


def test_seismic_class2_no_env():
    a = make_assessment(_seismic(2, mpd=5.5), None)
    assert a.final_class == 2
    assert a.env_upgrade == 0


def test_seismic_class0_no_env():
    a = make_assessment(_seismic(0), None)
    assert a.final_class == 0


def test_env_inactive_no_upgrade():
    """MQ2 INACTIVE should not contribute upgrade."""
    a = make_assessment(_seismic(1), _env(gas_delta=300, status="INACTIVE"))
    assert a.env_upgrade == 0
    assert a.final_class == 1


def test_gas_critical_upgrades_by_1():
    a = make_assessment(_seismic(1), _env(gas_delta=250))  # > 200
    assert a.flags["GAS_CRITICAL"]
    assert a.env_upgrade == 1
    assert a.final_class == 2


def test_temp_critical_upgrades_by_1():
    a = make_assessment(_seismic(1), _env(temp_delta=6.0))  # > 5°C
    assert a.flags["TEMP_CRITICAL"]
    assert a.env_upgrade == 1
    assert a.final_class == 2


def test_humid_critical_upgrades_by_1():
    a = make_assessment(_seismic(1), _env(humid_delta=-20.0))  # < -15%
    assert a.flags["HUMID_CRITICAL"]
    assert a.env_upgrade == 1
    assert a.final_class == 2


def test_compound_gas_caution_temp_elevated():
    a = make_assessment(_seismic(1), _env(gas_delta=60, temp_delta=3.0))
    assert a.flags["GAS_CAUTION"]
    assert a.flags["TEMP_ELEVATED"]
    assert a.env_upgrade >= 1
    assert a.final_class == 2


def test_class2_gas_critical_capped_at_3():
    a = make_assessment(_seismic(2), _env(gas_delta=250))
    assert a.final_class == 3


def test_class3_hard_cap():
    a = make_assessment(_seismic(3), _env(gas_delta=250))
    assert a.final_class == 3


def test_standalone_gas_critical_forces_class2():
    """No seismic + GAS_CRITICAL → final_class=2."""
    a = make_assessment(_seismic(0), _env(gas_delta=250))
    assert a.seismic_class == 0
    assert a.flags["GAS_CRITICAL"]
    assert a.final_class == 2


def test_standalone_temp_critical_forces_class2():
    a = make_assessment(_seismic(0), _env(temp_delta=6.0))
    assert a.final_class == 2


def test_env_none_no_crash():
    """env=None should not raise and should produce env_upgrade=0."""
    a = make_assessment(_seismic(2), None)
    assert a.env_upgrade == 0
    assert a.final_class == 2


def test_seismic_none_env_critical_forces_class2():
    """seismic=None treated as class 0; standalone env trigger still fires."""
    a = make_assessment(None, _env(gas_delta=250))
    assert a.seismic_class == 0
    assert a.final_class == 2


def test_gas_caution_only_no_upgrade_without_temp():
    """GAS_CAUTION alone (no TEMP_ELEVATED) should NOT trigger compound upgrade."""
    a = make_assessment(_seismic(1), _env(gas_delta=60, temp_delta=0.0))
    assert a.flags["GAS_CAUTION"]
    assert not a.flags["TEMP_ELEVATED"]
    # env_upgrade may be 0 unless another critical flag is set
    assert a.env_upgrade == 0
    assert a.final_class == 1


def test_all_flags_false_for_small_deltas():
    a = make_assessment(_seismic(0), _env(gas_delta=10, temp_delta=0.5, humid_delta=-1.0))
    assert not any(a.flags.values())
    assert a.env_upgrade == 0
    assert a.final_class == 0
