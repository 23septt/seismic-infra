import logging
import os
import threading
import time

import config
from readings import VisionResult

log = logging.getLogger(__name__)


def vision_loop(shared_state: dict, state_lock: threading.Lock,
                stop_event: threading.Event) -> None:
    """OpenCV webcam thread. Fails gracefully if camera absent or RAM exceeded."""
    try:
        import cv2
        import psutil
    except ImportError as e:
        log.warning("Vision dependencies unavailable (%s) — thread disabled", e)
        with state_lock:
            shared_state['vision_available'] = False
        return

    cap = None
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            log.info("No webcam found — vision thread disabled")
            with state_lock:
                shared_state['vision_available'] = False
            return

        proc = psutil.Process(os.getpid())
        prev_gray = None
        frame_idx  = 0

        while not stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                log.warning("Webcam read failed — stopping vision thread")
                break

            frame_idx += 1

            # RAM guard — check every 30 frames (~1s at 30fps)
            if frame_idx % 30 == 0:
                rss = proc.memory_info().rss
                if rss > config.RAM_LIMIT_BYTES:
                    log.warning("RAM %.2f GB exceeds limit — killing vision thread",
                                rss / 1e9)
                    stop_event.set()
                    break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            motion_detected = False
            confidence = 0.0

            if prev_gray is not None:
                diff = cv2.absdiff(prev_gray, gray)
                non_zero = float(cv2.countNonZero(diff))
                total     = float(gray.size)
                confidence = non_zero / total
                motion_detected = confidence > 0.01

            prev_gray = gray

            result = VisionResult(
                timestamp=time.time(),
                available=True,
                motion_detected=motion_detected,
                confidence=confidence,
            )
            with state_lock:
                shared_state['vision'] = result

            # ~30fps
            time.sleep(0.033)

    except Exception:
        log.exception("Vision thread unexpected error")
    finally:
        if cap is not None:
            cap.release()
        with state_lock:
            shared_state['vision_available'] = False
        log.info("Vision thread exited")
