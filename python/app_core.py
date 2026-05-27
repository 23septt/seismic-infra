"""SeismoGuard-R — entry point."""

import logging
import platform
import threading
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("main")

import config
from actuators import ActuatorController
from dashboard import DashboardServer
from decision import make_assessment
from state_machine import ResponseFSM


def _make_board():
    if platform.system() == "Linux":
        try:
            from board_qrb import BoardQRB
            return BoardQRB()
        except Exception as e:
            log.error("BoardQRB init failed (%s) — falling back to mock", e)
    from board_mock import BoardMock
    return BoardMock()


def main() -> None:
    shared_state: dict = {
        "seismic":          None,
        "env":              None,
        "assessment":       None,
        "fsm_class":        0,
        "alert_kind":       "all_clear",
    }
    state_lock   = threading.Lock()
    stop_all     = threading.Event()

    board      = _make_board()
    board.bridge_provide("mcu_status", lambda status: log.info("MCU bridge: %s", status))
    if not board.bridge_available:
        log.warning("Arduino Bridge unavailable; Modulino sensors and indicators are disabled")

    actuators  = ActuatorController(board)
    fsm        = ResponseFSM(actuators)
    dashboard  = DashboardServer(shared_state, state_lock)

    # ---- build sensor objects ----
    from environmental import EnvironmentalSensor
    from seismic import SeismicSensor

    seismic_sensor = SeismicSensor(board, shared_state, state_lock, stop_all)
    env_sensor     = EnvironmentalSensor(board, shared_state, state_lock, stop_all)

    # ---- launch threads ----
    threads = [
        threading.Thread(target=seismic_sensor.run,  name="seismic",  daemon=True),
        threading.Thread(target=env_sensor.run,      name="env",      daemon=True),
    ]
    for t in threads:
        t.start()
        log.info("Started thread: %s", t.name)

    dashboard.start()

    interval = 1.0 / config.MAIN_LOOP_HZ

    log.info("SeismoGuard-R running. Press Ctrl+C to stop.")
    try:
        while True:
            with state_lock:
                s = shared_state["seismic"]
                e = shared_state["env"]

            assessment = make_assessment(s, e)
            new_class  = fsm.update(assessment)

            with state_lock:
                shared_state["assessment"] = assessment
                shared_state["fsm_class"]  = new_class
                shared_state["alert_kind"] = assessment.alert_kind

            time.sleep(interval)

    except KeyboardInterrupt:
        log.info("Shutting down...")
    finally:
        stop_all.set()
        board.close()
        log.info("Done.")


if __name__ == "__main__":
    main()
