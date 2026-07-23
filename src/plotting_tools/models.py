"""系列データと軸指定に関する公開モデルを定義する。"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd
from numpy.typing import NDArray

# Anyを使わず、matplotlibへ渡せる1次元データの範囲を公開型として表す。
type PlotXData = (
    pd.Series
    | pd.Index
    | NDArray[np.number]
    | NDArray[np.datetime64]
    | Sequence[float]
    | Sequence[str]
)
type PlotYData = pd.Series | pd.Index | NDArray[np.number] | Sequence[float]


class AxisSide(Enum):
    """系列を描画するY軸の側を表す。"""

    LEFT = "left"
    RIGHT = "right"


class ScaleEnum(Enum):
    """Y軸で利用可能なスケールを表す。"""

    LINEAR = "linear"
    LOG = "log"


@dataclass
class PlotInfo:
    """1系列分のYデータと描画属性を保持する。"""

    data: PlotYData
    axis: AxisSide = AxisSide.LEFT
    label: str = ""
    color: str | None = None
    style: str = "-"
    linewidth: float | None = None
    scale: ScaleEnum = ScaleEnum.LINEAR

    def __post_init__(self) -> None:
        """明示された線幅が正値であることを検証する。"""
        if self.linewidth is not None and self.linewidth <= 0:
            msg = "linewidth must be positive"
            raise ValueError(msg)
