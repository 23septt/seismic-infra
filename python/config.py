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
SPATIAL_HZ   = 5
ENV_HZ       = 1

# --- MQ2 Gas Sensor ---
MQ2_WARMUP_SEC          = 60
MQ2_CALIB_SEC           = 30
MQ2_MEDIAN_WINDOW       = 5
MQ2_NOISE_VAR_THRESHOLD = 100.0  # ppm² variance
MQ2_ADC_MAX_RAW         = 16383.0
MQ2_ADC_REF_VOLTAGE    = 5.0
MQ2_LOAD_RESISTANCE_KOHM = 10.0
MQ2_CLEAN_AIR_FACTOR    = 9.83   # Rs/R0 in clean air

# --- Environmental thresholds (delta from baseline) ---
GAS_CAUTION_DELTA    = 50.0    # ppm above baseline
GAS_CRITICAL_DELTA   = 200.0
TEMP_ELEVATED_DELTA  = 2.0     # °C above baseline
TEMP_CRITICAL_DELTA  = 5.0
HUMID_DROP_DELTA     = -5.0    # % below baseline (negative = drop)
HUMID_CRITICAL_DELTA = -15.0
ZONE_DIST_MM         = 1000    # 100 cm in mm
MOTION_THRESHOLD     = 0.05    # rad/s gyro magnitude

# --- System resources ---
RAM_LIMIT_BYTES = 1_610_612_736  # 1.6 GB

# --- Dashboard ---
FLASK_PORT = int(os.environ.get("PORT", "5000"))

# --- Servo PWM (sysfs) ---
SERVO1_PWM_CHIP = 0
SERVO1_PWM_CH   = 0
SERVO2_PWM_CHIP = 0
SERVO2_PWM_CH   = 1

SERVO_NEUTRAL_US = 1500.0   # 90°
SERVO_CLOSE_US   = 1000.0   # 0°
SERVO_DEPLOY_US  = 2000.0   # 180°
SERVO_FREQ_HZ    = 50

# --- Pixels color map (R, G, B) ---
PIXEL_COLOR = {
    0: (0,   255, 0),    # GREEN
    1: (255, 200, 0),    # YELLOW
    2: (255, 0,   0),    # RED
    3: (255, 0,   0),    # RED
}
PIXEL_COUNT = 8
PIXEL_BRIGHTNESS = 64   # 0-255
