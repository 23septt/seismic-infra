from board import Board


class BoardMock(Board):
    """No-op implementation for unit tests on Windows."""

    def close(self) -> None:
        pass
