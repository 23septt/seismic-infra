import logging
import math
import struct
import threading
import time
from typing import Optional

from .. import config
from ..hal.board import Board
from . import SpatialReading

log = logging.getLogger(__name__)

# VL53L4CD registers (key subset)
_VL53_MODEL_ID       = 0x010F   # expected 0xEB
_VL53_SYSTEM_START   = 0x0087
_VL53_INT_CLEAR      = 0x0086
_VL53_RESULT_DIST_HI = 0x0096
_VL53_RESULT_DIST_LO = 0x0097

# LSM6DSOX gyro registers (secondary motion chip at 0x6B)
_CTRL2_G      = 0x11
_OUTX_L_G     = 0x22
_GYRO_ODR104  = 0x40   # 104 Hz, 250 dps
_GYRO_SENS    = 8.75e-3 * math.pi / 180.0  # 8.75 mdps/LSB → rad/s


def _write16(board: Board, addr: int, reg16: int, value: int) -> None:
    reg_hi = (reg16 >> 8) & 0xFF
    reg_lo = reg16 & 0xFF
    board.i2c_write_bytes(addr, reg_hi, bytes([reg_lo, value]))


def _read16(board: Board, addr: int, reg16: int) -> int:
    reg_hi = (reg16 >> 8) & 0xFF
    reg_lo = reg16 & 0xFF
    data = board.i2c_read_bytes(addr, reg_hi, 2)
    return (data[0] << 8) | data[1]


class SpatialSensor:
    def __init__(self, board: Board, shared_state: dict, lock: threading.Lock,
                 stop_event: threading.Event,
                 seismic_i2c_lock: Optional[threading.Lock] = None):
        self._board    = board
        self._state    = shared_state
        self._lock     = lock
        self._stop     = stop_event
        # If seismic sensor shares the motion I2C address, coordinate with its lock
        self._i2c_guard = seismic_i2c_lock or threading.Lock()

    def _init_vl53(self) -> bool:
        try:
            model = _read16(self._board, config.VL53L4CD_ADDR, _VL53_MODEL_ID)
            if model != 0xEB:
                log.warning("VL53L4CD MODEL_ID=0x%04X (expected 0xEB)", model)
            return True
        except OSError as e:
            log.error("VL53L4CD init failed: %s", e)
            return False

    def _read_distance_mm(self) -> Optional[float]:
        try:
            # Single-shot trigger
            _write16(self._board, config.VL53L4CD_ADDR, _VL53_SYSTEM_START, 0x40)
            # Poll for data-ready (max 100 ms)
            deadline = time.monotonic() + 0.1
            while time.monotonic() < deadline:
                status = _read16(self._board, config.VL53L4CD_ADDR, _VL53_INT_CLEAR)
                if status & 0x01:
                    break
                time.sleep(0.005)
            hi = self._board.i2c_read_bytes(config.VL53L4CD_ADDR, _VL53_RESULT_DIST_HI & 0xFF, 1)[0]
            lo = self._board.i2c_read_bytes(config.VL53L4CD_ADDR, _VL53_RESULT_DIST_LO & 0xFF, 1)[0]
            return float((hi << 8) | lo)
        except OSError:
            return None

    def _init_gyro(self) -> bool:
        try:
            self._board.i2c_write_bytes(config.LSM6DSOX_MOTION_ADDR, _CTRL2_G,
                                        bytes([_GYRO_ODR104]))
            return True
        except OSError as e:
            log.error("Motion gyro init failed: %s", e)
            return False

    def _read_gyro_magnitude(self) -> float:
        try:
            data = self._board.i2c_read_bytes(config.LSM6DSOX_MOTION_ADDR, _OUTX_L_G, 6)
            gx, gy, gz = struct.unpack('<hhh', data)
            mag = math.sqrt(gx**2 + gy**2 + gz**2) * _GYRO_SENS
            return mag
        except OSError:
            return 0.0

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                self._loop()
            except Exception:
                log.exception("SpatialSensor crashed — restarting in 1s")
                time.sleep(1)

    def _loop(self) -> None:
        vl53_ok = self._init_vl53()
        gyro_ok = self._init_gyro()

        interval = 1.0 / config.SPATIAL_HZ

        while not self._stop.is_set():
            dist_mm: Optional[float] = None
            gyro_mag = 0.0

            if vl53_ok:
                dist_mm = self._read_distance_mm()

            if gyro_ok:
                gyro_mag = self._read_gyro_magnitude()

            reading = SpatialReading(
                timestamp=time.time(),
                distance_mm=dist_mm,
                motion_detected=gyro_mag > config.MOTION_THRESHOLD,
                gyro_magnitude=gyro_mag,
            )
            with self._lock:
                self._state['spatial'] = reading

            time.sleep(interval)
