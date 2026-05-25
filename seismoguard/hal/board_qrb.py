import logging
import os
import threading

import smbus2

from .. import config
from .board import Board

log = logging.getLogger(__name__)


class BoardQRB(Board):
    """Concrete implementation for Qualcomm QRB2210 on Arduino UNO Q.

    I2C  → smbus2
    ADC  → IIO sysfs, falls back to STM32 serial bridge
    PWM  → /sys/class/pwm sysfs via python-periphery
    """

    def __init__(self):
        self._bus = smbus2.SMBus(config.I2C_BUS)
        self._i2c_lock = threading.Lock()
        self._adc_mode = self._detect_adc_mode()
        self._serial = None
        if self._adc_mode == "serial":
            self._serial = self._open_serial()
        self._pwm_handles: dict[tuple[int, int], object] = {}

    # ------------------------------------------------------------------
    # I2C
    # ------------------------------------------------------------------

    def i2c_read_bytes(self, addr: int, register: int, length: int) -> bytes:
        with self._i2c_lock:
            return bytes(self._bus.read_i2c_block_data(addr, register, length))

    def i2c_write_bytes(self, addr: int, register: int, data: bytes) -> None:
        with self._i2c_lock:
            self._bus.write_i2c_block_data(addr, register, list(data))

    def i2c_read_byte(self, addr: int) -> int:
        with self._i2c_lock:
            return self._bus.read_byte(addr)

    def i2c_write_raw(self, addr: int, data: bytes) -> None:
        with self._i2c_lock:
            msg = smbus2.i2c_msg.write(addr, list(data))
            self._bus.i2c_rdwr(msg)

    # ------------------------------------------------------------------
    # ADC
    # ------------------------------------------------------------------

    def _detect_adc_mode(self) -> str:
        iio_path = os.path.join(config.IIO_DEVICE_PATH, f"in_voltage{config.MQ2_ADC_CHANNEL}_raw")
        if os.path.exists(iio_path):
            log.info("ADC mode: IIO sysfs (%s)", iio_path)
            return "iio"
        log.info("ADC mode: STM32 serial bridge (%s)", config.SERIAL_BRIDGE_PORT)
        return "serial"

    def _open_serial(self):
        try:
            import serial
            s = serial.Serial(config.SERIAL_BRIDGE_PORT, config.SERIAL_BRIDGE_BAUD, timeout=1)
            return s
        except Exception as e:
            log.error("Serial bridge open failed: %s", e)
            return None

    def read_analog(self, channel: int) -> int:
        if self._adc_mode == "iio":
            path = os.path.join(config.IIO_DEVICE_PATH, f"in_voltage{channel}_raw")
            try:
                with open(path) as f:
                    return int(f.read().strip())
            except OSError as e:
                log.error("IIO read failed: %s", e)
                return 0
        else:
            return self._serial_analog_read(channel)

    def _serial_analog_read(self, channel: int) -> int:
        if self._serial is None:
            return 0
        try:
            cmd = f"ANALOG {channel}\n".encode()
            self._serial.write(cmd)
            resp = self._serial.readline().decode().strip()
            return int(resp)
        except Exception as e:
            log.error("Serial analog read failed: %s", e)
            return 0

    # ------------------------------------------------------------------
    # PWM
    # ------------------------------------------------------------------

    def set_pwm(self, chip: int, channel: int, duty_us: float) -> None:
        key = (chip, channel)
        try:
            from periphery import PWM
            if key not in self._pwm_handles:
                pwm = PWM(chip, channel)
                pwm.frequency = config.SERVO_FREQ_HZ
                pwm.enable()
                self._pwm_handles[key] = pwm
            period_us = 1_000_000 / config.SERVO_FREQ_HZ
            self._pwm_handles[key].duty_cycle = duty_us / period_us
        except Exception as e:
            log.error("PWM set failed chip=%d ch=%d duty_us=%.1f: %s", chip, channel, duty_us, e)

    # ------------------------------------------------------------------

    def close(self) -> None:
        self._bus.close()
        if self._serial:
            self._serial.close()
        for pwm in self._pwm_handles.values():
            try:
                pwm.disable()
                pwm.close()
            except Exception:
                pass
