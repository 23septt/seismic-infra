"""SeismoGuard-R — entry point."""

import logging
import os
import platform
import threading
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("main")

from . import config
from .fusion.decision import make_assessment
from .response.actuators import ActuatorController
from .response.state_machine import ResponseFSM
from .dashboard.server import DashboardServer


def _make_board():
    if platform.system() == "Linux":
        try:
            from .hal.board_qrb import BoardQRB
            return BoardQRB()
        except Exception as e:
            log.error("BoardQRB init failed (%s) — falling back to mock", e)
    from .hal.board_mock import BoardMock
    return BoardMock()


def probe_i2c_bus(board) -> None:
    """Log which expected I2C devices are present on the bus."""
    candidates = {
        "LSM6DSOX_seismic":  config.LSM6DSOX_SEISMIC_ADDR,
        "LSM6DSOX_motion":   config.LSM6DSOX_MOTION_ADDR,
        "HS3003":            config.HS3003_ADDR,
        "VL53L4CD":          config.VL53L4CD_ADDR,
        "Modulino_Pixels":   config.PIXELS_ADDR,
        "Modulino_Buzzer":   config.BUZZER_ADDR,
    }
    for name, addr in candidates.items():
        try:
            board.i2c_read_byte(addr)
            log.info("I2C 0x%02X %-22s PRESENT", addr, name)
        except OSError:
            log.warning("I2C 0x%02X %-22s ABSENT", addr, name)


def main() -> None:
    shared_state: dict = {
        "seismic":          None,
        "env":              None,
        "spatial":          None,
        "vision":           None,
        "vision_available": True,
        "assessment":       None,
        "fsm_class":        0,
    }
    state_lock   = threading.Lock()
    stop_all     = threading.Event()
    vision_stop  = threading.Event()

    board      = _make_board()
    probe_i2c_bus(board)

    actuators  = ActuatorController(board)
    fsm        = ResponseFSM(actuators)
    dashboard  = DashboardServer(shared_state, state_lock)

    # ---- build sensor objects ----
    from .sensors.seismic       import SeismicSensor
    from .sensors.environmental import EnvironmentalSensor
    from .sensors.spatial       import SpatialSensor
    from .sensors.vision        import vision_loop

    seismic_sensor = SeismicSensor(board, shared_state, state_lock, stop_all)
    env_sensor     = EnvironmentalSensor(board, shared_state, state_lock, stop_all)
    spatial_sensor = SpatialSensor(board, shared_state, state_lock, stop_all)

    # ---- launch threads ----
    threads = [
        threading.Thread(target=seismic_sensor.run,  name="seismic",  daemon=True),
        threading.Thread(target=env_sensor.run,      name="env",      daemon=True),
        threading.Thread(target=spatial_sensor.run,  name="spatial",  daemon=True),
        threading.Thread(
            target=vision_loop,
            args=(shared_state, state_lock, vision_stop),
            name="vision",
            daemon=True,
        ),
    ]
    for t in threads:
        t.start()
        log.info("Started thread: %s", t.name)

    dashboard.start()

    # ---- main fusion loop ----
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        use_psutil = True
    except ImportError:
        use_psutil = False

    interval = 1.0 / config.MAIN_LOOP_HZ

    log.info("SeismoGuard-R running. Press Ctrl+C to stop.")
    try:
        while True:
            # RAM watchdog
            if use_psutil and not vision_stop.is_set():
                rss = proc.memory_info().rss
                if rss > config.RAM_LIMIT_BYTES:
                    log.warning("RSS %.2f GB → killing vision thread", rss / 1e9)
                    vision_stop.set()
                    with state_lock:
                        shared_state["vision_available"] = False

            with state_lock:
                s = shared_state["seismic"]
                e = shared_state["env"]

            assessment = make_assessment(s, e)
            new_class  = fsm.update(assessment)

            with state_lock:
                shared_state["assessment"] = assessment
                shared_state["fsm_class"]  = new_class

            time.sleep(interval)

    except KeyboardInterrupt:
        log.info("Shutting down...")
    finally:
        stop_all.set()
        vision_stop.set()
        board.close()
        log.info("Done.")


if __name__ == "__main__":
    main()
