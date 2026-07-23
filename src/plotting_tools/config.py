"""描画設定をFigure、文字、軸、凡例、線の責務ごとに定義する。"""

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel

# Figureのsizeに必要な幅・高さの要素数。
FIGURE_DIMENSIONS = 2

type LegendLocation = (
    Literal[
        "best",
        "upper right",
        "upper left",
        "lower left",
        "lower right",
        "right",
        "center left",
        "center right",
        "lower center",
        "upper center",
        "center",
    ]
    | tuple[float, float]
    | int
)


class _PlotDefaults(BaseModel):
    """描画スタイルのライブラリ既定値を保持する。"""

    # Figureの幅・高さ。GraphBuilderへ渡す前のピクセル単位。
    default_size: tuple[int, int] = (900, 550)
    # Figureの解像度。1 inchあたりのdot数 (DPI)。
    default_dpi: int = 100
    # タイトル文字サイズ (matplotlibのpoint単位)。
    title_fontsize: int = 10
    # 軸ラベル文字サイズ (matplotlibのpoint単位)。
    label_fontsize: int = 18
    # 目盛文字サイズ (matplotlibのpoint単位)。
    tick_fontsize: int = 16
    # 凡例文字サイズ (matplotlibのpoint単位)。
    legend_fontsize: int = 10
    # 文字フォント名。Noneの場合はmatplotlibの既定フォントを使う。
    font_family: str | None = None


# 各設定クラスが共有する既定値の実体。
_DEFAULTS = _PlotDefaults()


@dataclass
class FigureStyleConfig:
    """Figureの寸法 (ピクセル) と解像度 (DPI) を設定する。"""

    size: tuple[int, int] = _DEFAULTS.default_size
    dpi: int = _DEFAULTS.default_dpi

    def __post_init__(self) -> None:
        """Figure生成前に寸法と解像度を検証する。"""
        if len(self.size) != FIGURE_DIMENSIONS or any(value <= 0 for value in self.size):
            msg = "figure size must contain two positive values"
            raise ValueError(msg)

        if self.dpi <= 0:
            msg = "dpi must be positive"
            raise ValueError(msg)


@dataclass
class TextStyleConfig:
    """タイトル、軸ラベル、目盛の文字スタイル (point単位) を設定する。"""

    title_fontsize: int = _DEFAULTS.title_fontsize
    label_fontsize: int = _DEFAULTS.label_fontsize
    tick_fontsize: int = _DEFAULTS.tick_fontsize
    font_family: str | None = _DEFAULTS.font_family
    title_options: dict[str, Any] = field(default_factory=dict)
    label_options: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """文字サイズがすべて正値であることを検証する。"""
        if min(self.title_fontsize, self.label_fontsize, self.tick_fontsize) <= 0:
            msg = "font sizes must be positive"
            raise ValueError(msg)


@dataclass
class AxisStyleConfig:
    """軸範囲、目盛方向、gridの既定スタイルを設定する。"""

    xlim: tuple[float, float] | None = None
    left_ylim: tuple[float, float] | None = None
    right_ylim: tuple[float, float] | None = None
    tick_direction: Literal["in", "out", "inout"] = "in"
    grid: bool = False
    grid_which: Literal["major", "minor", "both"] = "major"
    grid_axis: Literal["x", "y", "both"] = "both"
    grid_options: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """指定された軸範囲の大小関係を検証する。"""
        limits_by_name = (
            ("xlim", self.xlim),
            ("left_ylim", self.left_ylim),
            ("right_ylim", self.right_ylim),
        )

        for name, limits in limits_by_name:
            if limits is not None and limits[0] >= limits[1]:
                msg = f"{name} lower limit must be smaller than upper limit"
                raise ValueError(msg)


@dataclass
class LegendStyleConfig:
    """凡例の表示、配置、文字サイズ (point単位) を設定する。"""

    visible: bool = True
    loc: LegendLocation = "best"
    ncols: int = 1
    frameon: bool = True
    fontsize: int = _DEFAULTS.legend_fontsize
    options: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """凡例の列数と文字サイズを検証する。"""
        if self.ncols <= 0:
            msg = "legend ncols must be positive"
            raise ValueError(msg)

        if self.fontsize <= 0:
            msg = "legend fontsize must be positive"
            raise ValueError(msg)


@dataclass
class LineStyleConfig:
    """系列の既定線幅 (matplotlibのpoint単位) を設定する。"""

    # matplotlibへ渡す線幅 (point単位)。
    width: float = 1.5

    def __post_init__(self) -> None:
        """線幅が正値であることを検証する。"""
        if self.width <= 0:
            msg = "line width must be positive"
            raise ValueError(msg)


@dataclass
class PlotStyleConfig:
    """責務別の描画設定をGraphBuilder向けにまとめる。"""

    figure: FigureStyleConfig = field(default_factory=FigureStyleConfig)
    text: TextStyleConfig = field(default_factory=TextStyleConfig)
    axes: AxisStyleConfig = field(default_factory=AxisStyleConfig)
    legend: LegendStyleConfig = field(default_factory=LegendStyleConfig)
    line: LineStyleConfig = field(default_factory=LineStyleConfig)
    strict_mathtext: bool = False
