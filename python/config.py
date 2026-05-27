import math
import os

# --- Seismic STA/LTA ---
SEISMIC_RATE_HZ = 50
STA_WINDOW_SEC = 0.5
LTA_WINDOW_SEC = 30.0
RATIO_TRIGGER = 6.0
MIN_TRIGGER_SAMPLES = 3
SPIKE_REJECT_FACTOR = 50
POST_TRIGGER_SAMPLES = 150  # 3 seconds at 50 Hz

# Recursive filter coefficients (derived from windows)
ALPHA = 1 - math.exp(-1 / (SEISMIC_RATE_HZ * STA_WINDOW_SEC))
BETA  = 1 - math.exp(-1 / (SEISMIC_RATE_HZ * LTA_WINDOW_SEC))

# Suppress ratio output until LTA has had one full window to charge up (samples).
# Prevents false triggers during the initial LTA ramp-up period.
LTA_WARMUP_SAMPLES = int(SEISMIC_RATE_HZ * LTA_WINDOW_SEC)  # = 1500

# Seismic class thresholds (Mpd)
MPD_CLASS1 = 4.5
MPD_CLASS2 = 5.0
MPD_CLASS3 = 6.5

# Modulino Movement acceleration is reported in g; seismic processing uses m/s².
MODULINO_ACCEL_G_TO_MS2 = 9.80665

# --- Timing ---
COOLDOWN_SEC = 30
MAIN_LOOP_HZ = 5      # fusion + FSM rate
ENV_HZ       = 1

# --- Fire detection: Modulino Thermo + DHT11 ---
ENV_BASELINE_SEC = 30
FIRE_TEMP_ELEVATED_C = 40.0
FIRE_TEMP_CRITICAL_C = 50.0
FIRE_TEMP_ELEVATED_DELTA = 6.0
FIRE_TEMP_CRITICAL_DELTA = 10.0
FIRE_HUMID_DROP_DELTA = -15.0

# --- Dashboard ---
FLASK_PORT = int(os.environ.get("PORT", "5000"))

# --- Pixels color map (R, G, B) ---
PIXEL_COLOR = {
    0: (0,   255, 0),    # GREEN
    1: (255, 200, 0),    # YELLOW
    2: (255, 0,   0),    # RED
    3: (255, 0,   0),    # RED
}
PIXEL_COUNT = 8
PIXEL_BRIGHTNESS = 64   # 0-255
