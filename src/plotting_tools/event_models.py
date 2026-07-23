"""イベント注釈の入力とラベル配置用データを型付きモデルとして定義する。"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from plotting_tools.models import PlotYData, ScaleEnum


@dataclass(frozen=True)
class EventSpan:
    """一定期間を示すイベント注釈を表す。"""

    event: str
    start: float
    end: float
    label: str | None = None
    dx: float = 0.0
    y: float | None = None

    def __post_init__(self) -> None:
        """期間の開始位置が終了位置より前であることを検証する。"""
        if self.start >= self.end:
            msg = "event span start must be smaller than end"
            raise ValueError(msg)


@dataclass(frozen=True)
class EventPoint:
    """特定時点を示すイベント注釈を表す。"""

    event: str
    time: float
    label: str | None = None
    dx: float = 0.0
    y: float | None = None


@dataclass
class EventPlotConfig:
    """イベントの色、期間、時点を保持する描画設定。"""

    colors: dict[str, str] = field(default_factory=dict)
    spans: list[EventSpan] = field(default_factory=list)
    points: list[EventPoint] = field(default_factory=list)


@dataclass(frozen=True)
class EventLayoutData:
    """イベントラベルが避ける左右系列と軸条件を保持する。"""

    x: PlotYData
    primary_y: PlotYData
    secondary_y: PlotYData
    secondary_ylim: tuple[float, float]
    primary_scale: ScaleEnum = ScaleEnum.LINEAR
    secondary_scale: ScaleEnum = ScaleEnum.LINEAR

    def __post_init__(self) -> None:
        """ラベル配置に使う系列の次元、長さ、軸範囲を検証する。"""
        data_by_name = (
            ("x", self.x),
            ("primary_y", self.primary_y),
            ("secondary_y", self.secondary_y),
        )

        for name, data in data_by_name:
            if isinstance(data, pd.DataFrame) or np.ndim(data) != 1:
                msg = f"{name} must be one-dimensional"
                raise ValueError(msg)

        expected_length = len(self.x)
        if len(self.primary_y) != expected_length or len(self.secondary_y) != expected_length:
            msg = "event layout series must have the same length"
            raise ValueError(msg)

        ymin, ymax = self.secondary_ylim
        if ymin >= ymax:
            msg = "secondary_ylim lower limit must be smaller than upper limit"
            raise ValueError(msg)
