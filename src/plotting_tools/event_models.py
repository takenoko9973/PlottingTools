"""イベント注釈の入力を軽量な不変モデルとして定義する。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class EventSpan:
    """一定期間を示すイベント注釈を表す。"""

    start: float
    end: float
    label: str | None = None
    color: str | None = None
    dx: float = 0.0
    y: float | None = None

    def __post_init__(self) -> None:
        """期間の開始位置が終了位置より前であることを検証する。"""
        if not self.start < self.end:
            msg = "event span start must be smaller than end"
            raise ValueError(msg)


@dataclass(frozen=True)
class EventPoint:
    """特定時点を示すイベント注釈を表す。"""

    time: float
    label: str | None = None
    color: str | None = None
    dx: float = 0.0
    y: float | None = None
