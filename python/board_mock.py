from board import Board


class BoardMock(Board):
    """No-op implementation for unit tests on Windows."""

    def set_pwm(self, chip: int, channel: int, duty_us: float) -> None:
        pass

    def close(self) -> None:
        pass
