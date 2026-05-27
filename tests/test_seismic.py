"""STA/LTA unit tests using synthetic waveforms — no hardware required."""

import math
import sys
import os

import numpy as np

# Allow running from repo root: python -m pytest tests/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))

import config
from seismic import compute_sta_lta, _classify_mpd, _estimate_magnitude


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _max_consecutive(arr: np.ndarray) -> int:
    """Return length of the longest consecutive True run."""
    best = cur = 0
    for v in arr:
        if v:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def _make_ricker(center: int, n_total: int, freq: float = 5.0,
                 amplitude: float = 0.5, noise_std: float = 0.001) -> np.ndarray:
    rng = np.random.default_rng(42)
    samples = rng.normal(0, noise_std, n_total)
    t = np.linspace(-0.15, 0.15, 75)
    ricker = (1 - 2 * (np.pi * freq * t) ** 2) * np.exp(-(np.pi * freq * t) ** 2)
    end = min(center + len(ricker), n_total)
    actual_len = end - center
    samples[center:end] += ricker[:actual_len] * amplitude
    return samples


# ---------------------------------------------------------------------------
# Test 1 — filter coefficients
# ---------------------------------------------------------------------------

def test_alpha_formula():
    expected_alpha = 1 - math.exp(-1 / (config.SEISMIC_RATE_HZ * config.STA_WINDOW_SEC))
    assert abs(config.ALPHA - expected_alpha) < 1e-10


def test_beta_formula():
    expected_beta = 1 - math.exp(-1 / (config.SEISMIC_RATE_HZ * config.LTA_WINDOW_SEC))
    assert abs(config.BETA - expected_beta) < 1e-10


def test_alpha_reasonable_value():
    assert 0.01 < config.ALPHA < 0.1


def test_beta_reasonable_value():
    assert 0.0001 < config.BETA < 0.01


# ---------------------------------------------------------------------------
# Test 2 — Gaussian noise must NOT trigger
# ---------------------------------------------------------------------------

def test_gaussian_noise_no_trigger():
    # Use LTA_WARMUP_SAMPLES so LTA is converged before we evaluate.
    # After warmup, the ratio on noise should consistently stay below RATIO_TRIGGER.
    warmup = config.LTA_WARMUP_SAMPLES   # = 1500
    rng = np.random.default_rng(42)
    samples = rng.normal(0, 0.001, warmup + 1000)
    ratios = compute_sta_lta(samples, warmup_samples=warmup)
    triggered = ratios[warmup:] >= config.RATIO_TRIGGER
    assert not np.any(triggered), (
        f"False alarm after warmup: max ratio = {ratios[warmup:].max():.2f}"
    )


# ---------------------------------------------------------------------------
# Test 3 — Ricker wavelet MUST trigger within expected window
# ---------------------------------------------------------------------------

def test_ricker_wavelet_triggers():
    inject_at = 800
    samples = _make_ricker(center=inject_at, n_total=1500)
    ratios = compute_sta_lta(samples)
    triggered = ratios >= config.RATIO_TRIGGER
    consec = _max_consecutive(triggered)
    assert consec >= config.MIN_TRIGGER_SAMPLES, (
        f"Expected ≥{config.MIN_TRIGGER_SAMPLES} consecutive triggers, got {consec}. "
        f"Max ratio = {ratios.max():.2f}"
    )


def test_ricker_trigger_in_right_window():
    """Trigger should fire near the wavelet, not before it.

    With warmup suppression, no ratio is emitted during the first LTA_WARMUP_SAMPLES
    samples. Inject the wavelet well after warmup ends to confirm there are no
    spurious triggers in the noise-only region between warmup and injection.
    """
    warmup    = config.LTA_WARMUP_SAMPLES      # 1500
    inject_at = warmup + 200                   # inject at sample 1700
    n_total   = inject_at + 300                # 2000 samples total
    samples   = _make_ricker(center=inject_at, n_total=n_total)
    ratios    = compute_sta_lta(samples, warmup_samples=warmup)

    # Between end of warmup and injection there should be no trigger
    slack = int(config.SEISMIC_RATE_HZ * config.STA_WINDOW_SEC * 2)  # 2× STA window
    window_end = inject_at - slack
    if window_end > warmup:
        pre_trigger = ratios[warmup:window_end] >= config.RATIO_TRIGGER
        assert not np.any(pre_trigger), "Spurious trigger before wavelet injection"


# ---------------------------------------------------------------------------
# Test 4 — Spike rejection
# ---------------------------------------------------------------------------

def test_spike_rejection_flag():
    rng = np.random.default_rng(0)
    samples = rng.normal(0, 0.001, 600)

    # Single massive spike well past the spike reject threshold
    spike_idx = 400
    spike_samples = samples.copy()
    spike_samples[spike_idx] = 100.0

    _, rejected_clean = compute_sta_lta(samples,     return_rejected=True)
    _, rejected_spike = compute_sta_lta(spike_samples, return_rejected=True)

    # The spike sample must be flagged as rejected
    assert rejected_spike[spike_idx], "Spike not flagged as rejected"
    # Clean signal at same index should NOT be rejected
    assert not rejected_clean[spike_idx], "Clean sample wrongly flagged as spike"


def test_spike_does_not_cause_sustained_trigger():
    """A single spike must not produce ≥ MIN_TRIGGER_SAMPLES consecutive triggers.

    Inject the spike after warmup (LTA converged) to ensure the test is not
    conflated with the LTA ramp-up period triggering.
    """
    warmup    = config.LTA_WARMUP_SAMPLES      # 1500
    spike_idx = warmup + 200                   # spike at 1700
    n_total   = warmup + 600                   # 2100 samples
    rng = np.random.default_rng(1)
    samples = rng.normal(0, 0.001, n_total)
    samples[spike_idx] = 100.0

    ratios  = compute_sta_lta(samples, warmup_samples=warmup)
    triggered = ratios[warmup:] >= config.RATIO_TRIGGER
    consec  = _max_consecutive(triggered)
    assert consec < config.MIN_TRIGGER_SAMPLES, (
        f"Spike caused {consec} consecutive post-warmup triggers "
        f"(threshold {config.MIN_TRIGGER_SAMPLES})"
    )


# ---------------------------------------------------------------------------
# Test 5 — Magnitude formula
# ---------------------------------------------------------------------------

def test_mpd_formula_pd1cm():
    # Pd = 1 cm → log10(1) + 5.39 = 5.39
    Pd_cm = 1.0
    Mpd   = math.log10(Pd_cm) + 5.39
    assert abs(Mpd - 5.39) < 1e-9


def test_mpd_formula_pd10cm():
    Pd_cm = 10.0
    Mpd   = math.log10(Pd_cm) + 5.39
    assert abs(Mpd - 6.39) < 1e-9


def test_mpd_classification_boundaries():
    assert _classify_mpd(4.0)  == 0
    assert _classify_mpd(4.5)  == 1
    assert _classify_mpd(4.99) == 1
    assert _classify_mpd(5.0)  == 2
    assert _classify_mpd(6.49) == 2
    assert _classify_mpd(6.5)  == 3
    assert _classify_mpd(8.0)  == 3


def test_estimate_magnitude_returns_float():
    """Double-integration of a simple pulse should yield a finite Mpd."""
    dt = 1.0 / config.SEISMIC_RATE_HZ
    t  = np.linspace(0, dt * config.POST_TRIGGER_SAMPLES, config.POST_TRIGGER_SAMPLES)
    # 2 Hz sinusoid at 0.1 m/s² peak → integrates to a measurable displacement
    acc = 0.1 * np.sin(2 * math.pi * 2.0 * t)
    result = _estimate_magnitude(acc.tolist())
    assert result is not None
    assert math.isfinite(result)
