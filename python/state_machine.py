import logging
import threading
import time

import config
from actuators import ActuatorController
from decision import HazardAssessment

log = logging.getLogger(__name__)


class ResponseFSM:
    """4-class alert state machine with 30-second cooldown."""

    def __init__(self, actuators: ActuatorController):
        self._actuators      = actuators
        self._state          = 0
        self._last_trigger_t = 0.0
        self._lock           = threading.Lock()

    @property
    def state(self) -> int:
        with self._lock:
            return self._state

    def update(self, assessment: HazardAssessment) -> int:
        new_class = assessment.final_class
        now       = time.time()

        with self._lock:
            if new_class > self._state:
                log.info("FSM %d → %d (Mpd=%s)", self._state, new_class,
                         f"{assessment.Mpd:.2f}" if assessment.Mpd else "N/A")
                self._state          = new_class
                self._last_trigger_t = now
                self._actuators.apply(assessment)

            elif new_class < self._state:
                elapsed = now - self._last_trigger_t
                if elapsed >= config.COOLDOWN_SEC:
                    log.info("FSM %d → %d (cooldown elapsed %.0fs)",
                             self._state, new_class, elapsed)
                    self._state = new_class
                    self._actuators.apply(assessment)

            return self._state
