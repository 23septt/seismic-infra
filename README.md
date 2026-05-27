# SeismoGuard-R

Multi-hazard disaster response robot with edge AI seismic and environmental detection. Runs fully on-device — no cloud dependency.

## Hardware

| Component | Role | Interface |
|---|---|---|
| Modulino Movement | Seismic acceleration / motion detect | MCU Modulino library via Bridge RPC |
| Modulino Thermo | Temperature + humidity | MCU Modulino library via Bridge RPC |
| Modulino Pixels | RGB status indicator | MCU Modulino library via Bridge RPC |
| Modulino Buzzer | Alert tones | MCU Modulino library via Bridge RPC |
| DHT11 | Backup temperature + humidity | MCU digital pin `D2` via Bridge RPC |

**Platform:** Arduino UNO Q — Qualcomm QRB2210 SoC, Debian Linux. Not Raspberry Pi. RPi.GPIO/pigpio do not work here.

Modulino sensors and indicators are driven from the MCU sketch through the UNO Q Arduino Bridge RPC path. The Linux process keeps the detection, fusion, dashboard, and response logic, while `sketch/sketch.ino` is the only layer that talks to the Modulino library.

## Software architecture

```
app.yaml                 # Arduino App Lab app manifest
python/
├── main.py              # App Lab Python entry point
├── app_core.py          # sensor threads + main fusion loop
├── config.py            # all tunable constants
├── dashboard.py         # Flask REST API (/api/state, /api/alert)
├── decision.py          # pure make_assessment() fusion function
├── seismic.py           # STA/LTA seismic detector
├── environmental.py     # Modulino Thermo + DHT11 fire detection
├── actuators.py         # pixels + buzzer patterns
├── state_machine.py     # ResponseFSM (class 0-3)
├── board*.py            # Hardware Abstraction Layer
└── requirements.txt     # Linux-side Python dependencies
sketch/
├── sketch.ino           # MCU bridge for Modulino sensors/actuators
└── sketch.yaml          # sketch dependencies
tests/                   # local tests, not needed by App Lab
```

The MCU companion sketch lives in `sketch/` and registers these Bridge RPC methods:

| Method | Direction | Purpose |
|---|---|---|
| `sensor_env()` | MCU → Linux | Read Modulino Thermo and DHT11 temperature/humidity |
| `sensor_accel()` | MCU → Linux | Read Modulino Movement acceleration and orientation |
| `pixels_set_all(r, g, b, brightness, count)` | Linux → MCU | Set all Modulino Pixels LEDs |
| `buzzer_tone(frequency, duration)` | Linux → MCU | Play or silence the Modulino Buzzer |
| `mcu_status(status)` | MCU → Linux | Report MCU bridge status to the Python log |

The main loop runs at `MAIN_LOOP_HZ` (config.py), reading shared seismic and environmental state and calling `make_assessment()` → `ResponseFSM.update()` each tick.

## Setup

### Dependencies

```bash
pip install -r python/requirements.txt
```

Requires Python 3.10+. In Arduino App Lab, `python/main.py` is the Linux entry point and `sketch/sketch.ino` is the MCU sketch.

## Running

```bash
cd python
python main.py
```

Dashboard available at `http://<robot-ip>:5000` once running.

To stop: `Ctrl+C` — clean shutdown of all threads.

## Tests

```bash
pytest tests/
```

All 29 tests run on any machine via `BoardMock` — no hardware required.

## Alert classes

| Class | Meaning | Response |
|---|---|---|
| 0 | All clear | Pixels off |
| 1 | Low hazard | Pulsing pixels, caution buzz |
| 2 | Moderate hazard | Faster pixels, loud hazard buzz |
| 3 | Severe hazard | Strobing pixels, loud alarm buzz |

Fire alerts use a high-low siren. Earthquake alerts use a repeated triple-pulse buzzer pattern so the two situations are easy to tell apart.

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE).
