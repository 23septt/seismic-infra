from typing import Any

from board import Board


def _parts(value: Any) -> list[str]:
    if isinstance(value, bytes):
        value = value.decode()
    if isinstance(value, str):
        return [p.strip() for p in value.split(",")]
    if isinstance(value, (list, tuple)):
        return [str(p).strip() for p in value]
    return [str(value).strip()]


def call_floats(board: Board, method: str, count: int) -> tuple[float, ...]:
    values = _parts(board.bridge_call(method))
    if len(values) < count:
        raise ValueError(f"{method} returned {len(values)} values, expected {count}")
    return tuple(float(values[i]) for i in range(count))


def call_int(board: Board, method: str) -> int:
    return int(float(_parts(board.bridge_call(method))[0]))
