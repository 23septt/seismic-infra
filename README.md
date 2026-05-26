# SeismoGuard-R

Multi-hazard disaster response robot with edge AI seismic and environmental detection. Runs fully on-device — no cloud dependency.

## Hardware

| Component | Role | I2C Address |
|---|---|---|
| LSM6DSOX (×2) | Seismic acceleration / motion detect | 0x6A / 0x6B |
| HS3003 | Temperature + humidity | 0x44 |
| VL53L4CD | Time-of-flight distance | 0x29 |
| Modulino Pixels | RGB status indicator | 0x6C |
| Modulino Buzzer | Alert tones | 0x3C |
| MQ2 | Gas / smoke (via STM32 ADC → IIO sysfs) | — |
| Servo | Physical response actuator (sysfs PWM) | — |
| Camera | Vision / obstacle detection | — |

**Platform:** Arduino UNO Q — Qualcomm QRB2210 SoC, Debian Linux. Not Raspberry Pi. RPi.GPIO/pigpio do not work here.

Modulino Pixels and Modulino Buzzer are driven through the UNO Q Arduino Bridge RPC path when available. The Linux process sends compact `Bridge.notify()` messages to MCU methods exposed by `arduino/seismoguard_bridge/seismoguard_bridge.ino`; raw I2C remains as a fallback for non-Bridge runs.

## Software architecture

```
seismoguard/
├── config.py            # all tunable constants
├── hal/                 # Hardware Abstraction Layer
│   ├── board.py         # Board ABC
│   ├── board_qrb.py     # QRB2210 (smbus2 + python-periphery)
│   └── board_mock.py    # in-memory mock for tests
├── sensors/
│   ├── seismic.py       # STA/LTA seismic detector
│   ├── environmental.py # temp, humidity, gas
│   ├── spatial.py       # ToF distance
│   └── vision.py        # camera vision loop
├── fusion/
│   └── decision.py      # pure make_assessment() fusion function
├── response/
│   ├── state_machine.py # ResponseFSM (class 0–3)
│   └── actuators.py     # pixels, buzzer, servo, audio
├── dashboard/
│   └── server.py        # Flask REST API (/api/state, /api/alert)
├── main.py              # 5 threads + main fusion loop
└── tests/               # 29 tests, no hardware needed
```

The MCU companion sketch lives in `arduino/seismoguard_bridge/` and registers these Bridge RPC methods:

| Method | Direction | Purpose |
|---|---|---|
| `pixels_set_all(r, g, b, brightness, count)` | Linux → MCU | Set all Modulino Pixels LEDs |
| `buzzer_tone(frequency, duration)` | Linux → MCU | Play or silence the Modulino Buzzer |
| `mcu_status(status)` | MCU → Linux | Report MCU bridge status to the Python log |

The main loop runs at `MAIN_LOOP_HZ` (config.py), reading shared sensor state updated by four daemon threads and calling `make_assessment()` → `ResponseFSM.update()` each tick.

## Setup

### Dependencies

```bash
pip install -r requirements.txt
```

Requires Python 3.10+. On the QRB2210 target, also install system packages:

```bash
sudo apt install python3-smbus2 alsa-utils ffmpeg
```

### Audio files (Thai TTS)

Run once on any internet-connected machine before deploying to the robot:

```bash
pip install gtts
python scripts/generate_audio.py
```

This writes `seismoguard/response/audio/class{1,2,3}_*.wav`. Copy the entire `seismoguard/` directory to the robot afterward.

### Hardware probe

On first boot, check that all I2C devices are visible:

```bash
python -m seismoguard  # logs PRESENT/ABSENT for each expected device
```

Or directly: `i2cdetect -y 1`

## Running

```bash
python -m seismoguard
```

Dashboard available at `http://<robot-ip>:5000` once running.

To stop: `Ctrl+C` — clean shutdown of all threads.

## Tests

```bash
pytest seismoguard/tests/
```

All 29 tests run on any machine via `BoardMock` — no hardware required.

## Alert classes

| Class | Meaning | Response |
|---|---|---|
| 0 | All clear | Pixels off |
| 1 | Low hazard | Pixels amber, low buzz |
| 2 | Moderate hazard | Pixels orange, alert buzz, audio |
| 3 | Severe hazard | Pixels red, alarm buzz, audio, servo |

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE).
