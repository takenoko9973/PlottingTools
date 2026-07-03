"""Figure、Axes、系列情報を扱う描画ユーティリティ。"""

from __future__ import annotations

import math
import warnings
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal, Protocol, Self, cast

import numpy as np
import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.mathtext import MathTextParser
from matplotlib.ticker import AutoMinorLocator
from numpy.typing import NDArray
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from matplotlib.artist import Artist
    from matplotlib.axes import Axes
    from matplotlib.axis import Axis
    from matplotlib.backend_bases import RendererBase
    from matplotlib.legend import Legend
    from matplotlib.lines import Line2D
    from matplotlib.text import Text
    from matplotlib.ticker import Formatter, Locator

EPSILON = 1e-9
FIGURE_DIMENSIONS = 2

# matplotlibへ渡せる型を明示しつつ、Anyによる無制限な入力許可を避ける。
type PlotXData = (
    pd.Series
    | pd.Index
    | NDArray[np.number]
    | NDArray[np.datetime64]
    | Sequence[float]
    | Sequence[str]
)
type PlotYData = pd.Series | pd.Index | NDArray[np.number] | Sequence[float]


class _RendererCanvas(Protocol):
    """テキスト寸法計算に必要なcanvasの最小インターフェース。"""

    def get_renderer(self) -> RendererBase: ...


class PlotConfig(BaseModel):
    """描画スタイルの既定値を保持する。"""

    default_size: list[int] = Field(default_factory=lambda: [900, 550])
    default_dpi: int = 100
    title_fontsize: int = 10
    label_fontsize: int = 18
    tick_fontsize: int = 16
    legend_fontsize: int = 10
    font_family: str | None = None


APP_CONFIG = PlotConfig()


@dataclass
class FigureStyleConfig:
    """Figureの寸法と解像度。"""

    size: tuple[int, int] = (APP_CONFIG.default_size[0], APP_CONFIG.default_size[1])
    dpi: int = APP_CONFIG.default_dpi

    def __post_init__(self) -> None:
        if len(self.size) != FIGURE_DIMENSIONS or any(value <= 0 for value in self.size):
            msg = "figure size must contain two positive values"
            raise ValueError(msg)
        if self.dpi <= 0:
            msg = "dpi must be positive"
            raise ValueError(msg)


@dataclass
class TextStyleConfig:
    """タイトル、軸ラベル、目盛の文字スタイル。"""

    title_fontsize: int = APP_CONFIG.title_fontsize
    label_fontsize: int = APP_CONFIG.label_fontsize
    tick_fontsize: int = APP_CONFIG.tick_fontsize
    font_family: str | None = APP_CONFIG.font_family
    title_options: dict[str, Any] = field(default_factory=dict)
    label_options: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if min(self.title_fontsize, self.label_fontsize, self.tick_fontsize) <= 0:
            msg = "font sizes must be positive"
            raise ValueError(msg)


@dataclass
class AxisStyleConfig:
    """軸範囲、目盛方向、gridの既定スタイル。"""

    xlim: tuple[float, float] | None = None
    left_ylim: tuple[float, float] | None = None
    right_ylim: tuple[float, float] | None = None
    tick_direction: Literal["in", "out", "inout"] = "in"
    grid: bool = False
    grid_which: Literal["major", "minor", "both"] = "major"
    grid_axis: Literal["x", "y", "both"] = "both"
    grid_options: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, limits in (
            ("xlim", self.xlim),
            ("left_ylim", self.left_ylim),
            ("right_ylim", self.right_ylim),
        ):
            if limits is not None and limits[0] >= limits[1]:
                msg = f"{name} lower limit must be smaller than upper limit"
                raise ValueError(msg)


@dataclass
class LegendStyleConfig:
    """凡例の表示と配置スタイル。"""

    visible: bool = True
    loc: str = "best"
    ncols: int = 1
    frameon: bool = True
    fontsize: int = APP_CONFIG.legend_fontsize
    options: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.ncols <= 0:
            msg = "legend ncols must be positive"
            raise ValueError(msg)
        if self.fontsize <= 0:
            msg = "legend fontsize must be positive"
            raise ValueError(msg)


@dataclass
class LineStyleConfig:
    """系列の既定線スタイル。"""

    width: float = 1.5

    def __post_init__(self) -> None:
        if self.width <= 0:
            msg = "line width must be positive"
            raise ValueError(msg)


@dataclass
class PlotStyleConfig:
    """責務別の描画設定をまとめるGraphBuilder設定。"""

    figure: FigureStyleConfig = field(default_factory=FigureStyleConfig)
    text: TextStyleConfig = field(default_factory=TextStyleConfig)
    axes: AxisStyleConfig = field(default_factory=AxisStyleConfig)
    legend: LegendStyleConfig = field(default_factory=LegendStyleConfig)
    line: LineStyleConfig = field(default_factory=LineStyleConfig)
    strict_mathtext: bool = False


def format_sci_mathtext(x: float, pos: object = None) -> str:  # noqa: ARG001
    """数値をmathtextで表示可能な科学表記へ変換する。"""
    if x == 0:
        return "0"
    exponent = math.floor(math.log10(abs(x)))
    coefficient = x / (10**exponent)
    return f"${coefficient:.1f} \\times 10^{{{exponent}}}$"


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
    """1系列分のデータと描画属性を保持する。"""

    data: PlotYData
    axis: AxisSide = AxisSide.LEFT
    label: str = ""
    color: str | None = None
    style: str = "-"
    linewidth: float | None = None
    scale: ScaleEnum = ScaleEnum.LINEAR

    def __post_init__(self) -> None:
        if self.linewidth is not None and self.linewidth <= 0:
            msg = "linewidth must be positive"
            raise ValueError(msg)


class GraphBuilder:
    """左右Y軸を扱う薄いmatplotlib描画wrapper。"""

    def __init__(self, style_config: PlotStyleConfig | None = None) -> None:
        """Figureと左Y軸を生成し、共通の軸スタイルを適用する。"""
        self.style = style_config or PlotStyleConfig()
        self.fig = Figure(
            figsize=(
                self.style.figure.size[0] / self.style.figure.dpi,
                self.style.figure.size[1] / self.style.figure.dpi,
            ),
            dpi=self.style.figure.dpi,
        )
        FigureCanvasAgg(self.fig)
        self.ax1 = self.fig.add_subplot()
        self.ax2: Axes | None = None
        self._setup_axis(self.ax1)
        self.lines: list[Line2D] = []
        self.labels: list[str] = []
        self._base_ylim: dict[AxisSide, tuple[float, float] | None] = {
            AxisSide.LEFT: None,
            AxisSide.RIGHT: None,
        }
        self._math_parser = MathTextParser("agg")
        if self.style.axes.xlim is not None:
            self.ax1.set_xlim(*self.style.axes.xlim)
        if self.style.axes.left_ylim is not None:
            self.set_ylim(AxisSide.LEFT, *self.style.axes.left_ylim)
        if self.style.axes.right_ylim is not None:
            self.set_ylim(AxisSide.RIGHT, *self.style.axes.right_ylim)

    def _apply_tick_font(self, ax: Axes) -> None:
        """生成済みの目盛ラベルへ指定フォントを適用する。"""
        if self.style.text.font_family is None:
            return
        for label in (*ax.get_xticklabels(), *ax.get_yticklabels()):
            label.set_fontfamily(self.style.text.font_family)

    def _is_valid_latex(self, text: str) -> bool:
        """matplotlibのmathtext parserで文字列を事前検証する。"""
        if not text or "$" not in text:
            return True
        try:
            self._math_parser.parse(text)
        except Exception:  # noqa: BLE001
            return False
        return True

    def _get_safe_text(self, text: str) -> str:
        """無効なmathtextを描画可能な代替ラベルへ置き換える。"""
        if self._is_valid_latex(text):
            return text
        msg = f"invalid mathtext: {text!r}"
        if self.style.strict_mathtext:
            raise ValueError(msg)
        warnings.warn(msg, UserWarning, stacklevel=3)
        return "[Label Error]"

    def _setup_axis(self, ax: Axes) -> None:
        """軸へ目盛とgridの既定スタイルを設定する。"""
        ax.xaxis.set_minor_locator(AutoMinorLocator(5))
        ax.yaxis.set_minor_locator(AutoMinorLocator(5))
        ax.tick_params(
            axis="both",
            which="major",
            labelsize=self.style.text.tick_fontsize,
            direction=self.style.axes.tick_direction,
            top=True,
        )
        ax.tick_params(
            axis="both",
            which="minor",
            direction=self.style.axes.tick_direction,
            top=True,
        )
        ax.grid(
            self.style.axes.grid,
            which=self.style.axes.grid_which,
            axis=self.style.axes.grid_axis,
            **self.style.axes.grid_options,
        )

    def get_ax2(self) -> Axes:
        """右Y軸を必要になった時点で生成して返す。"""
        if self.ax2 is None:
            self.ax2 = self.ax1.twinx()
            self._setup_axis(self.ax2)
            self._apply_tick_font(self.ax2)
        return self.ax2

    def get_axis(self, side: AxisSide = AxisSide.LEFT) -> Axes:
        """高度なmatplotlib設定に使う指定側のAxesを返す。"""
        return self.ax1 if side is AxisSide.LEFT else self.get_ax2()

    def set_labels(self, xlabel: str, ylabel_left: str, ylabel_right: str = "") -> None:
        """X軸と左右Y軸のラベルを設定する。"""
        options: dict[str, Any] = {
            "fontsize": self.style.text.label_fontsize,
            **self.style.text.label_options,
        }
        xlabel_text = self.ax1.set_xlabel(self._get_safe_text(xlabel), fontdict=options)
        ylabel_left_text = self.ax1.set_ylabel(self._get_safe_text(ylabel_left), fontdict=options)
        if self.style.text.font_family is not None:
            xlabel_text.set_fontfamily(self.style.text.font_family)
            ylabel_left_text.set_fontfamily(self.style.text.font_family)
        if ylabel_right:
            ylabel_right_text = self.get_ax2().set_ylabel(
                self._get_safe_text(ylabel_right), fontdict=options
            )
            if self.style.text.font_family is not None:
                ylabel_right_text.set_fontfamily(self.style.text.font_family)

    def set_title(self, title: str) -> None:
        """mathtextを検証してグラフタイトルを設定する。"""
        options: dict[str, Any] = {
            "fontsize": self.style.text.title_fontsize,
            **self.style.text.title_options,
        }
        title_text = self.ax1.set_title(self._get_safe_text(title), fontdict=options)
        if self.style.text.font_family is not None:
            title_text.set_fontfamily(self.style.text.font_family)

    def set_xlim(self, xmin: float, xmax: float) -> None:
        """同一値の場合にも幅を持つX軸範囲を設定する。"""
        if abs(xmax - xmin) < EPSILON:
            xmin -= 0.5
            xmax += 0.5
        self.ax1.set_xlim(xmin, xmax)

    def expand_ylim_to_include(self, side: AxisSide, ymin: float, ymax: float) -> None:
        """自動範囲が最低限包含するY軸範囲を登録する。"""
        if ymin >= ymax:
            msg = "ymin must be smaller than ymax"
            raise ValueError(msg)
        self._base_ylim[side] = (ymin, ymax)

    def set_ylim(self, side: AxisSide, ymin: float, ymax: float) -> None:
        """自動範囲に左右されない厳密なY軸範囲を設定する。"""
        if ymin >= ymax:
            msg = "ymin must be smaller than ymax"
            raise ValueError(msg)
        self.get_axis(side).set_ylim(ymin, ymax)

    @staticmethod
    def _set_locator(
        axis: Axis,
        locator: Locator,
        which: Literal["major", "minor"],
    ) -> None:
        if which == "major":
            axis.set_major_locator(locator)
        else:
            axis.set_minor_locator(locator)

    def set_x_locator(
        self, locator: Locator, *, which: Literal["major", "minor"] = "major"
    ) -> None:
        """X軸のmajor/minor locatorを設定する。"""
        self._set_locator(self.ax1.xaxis, locator, which)

    def set_y_locator(
        self,
        side: AxisSide,
        locator: Locator,
        *,
        which: Literal["major", "minor"] = "major",
    ) -> None:
        """指定Y軸のmajor/minor locatorを設定する。"""
        self._set_locator(self.get_axis(side).yaxis, locator, which)

    @staticmethod
    def _set_formatter(
        axis: Axis,
        formatter: Formatter,
        which: Literal["major", "minor"],
    ) -> None:
        if which == "major":
            axis.set_major_formatter(formatter)
        else:
            axis.set_minor_formatter(formatter)

    def set_x_formatter(
        self,
        formatter: Formatter,
        *,
        which: Literal["major", "minor"] = "major",
    ) -> None:
        """X軸のmajor/minor formatterを設定する。"""
        self._set_formatter(self.ax1.xaxis, formatter, which)

    def set_y_formatter(
        self,
        side: AxisSide,
        formatter: Formatter,
        *,
        which: Literal["major", "minor"] = "major",
    ) -> None:
        """指定Y軸のmajor/minor formatterを設定する。"""
        self._set_formatter(self.get_axis(side).yaxis, formatter, which)

    def set_yscale(self, side: AxisSide, scale: ScaleEnum | str) -> None:
        """指定した側のY軸スケールを設定する。"""
        target_ax = self.ax1 if side is AxisSide.LEFT else self.get_ax2()
        target_ax.set_yscale(scale.value if isinstance(scale, ScaleEnum) else scale)

    @staticmethod
    def _validate_plot_data(x_data: PlotXData, y_data: PlotYData) -> None:
        """X/Yデータが1次元かつ同じ長さであることを検証する。"""
        # 型注釈だけでは2次元のndarrayや実行時に渡されるDataFrameを排除できない。
        if isinstance(x_data, pd.DataFrame) or np.ndim(x_data) != 1:
            msg = "x_data must be one-dimensional"
            raise ValueError(msg)
        if isinstance(y_data, pd.DataFrame) or np.ndim(y_data) != 1:
            msg = "plot_info.data must be one-dimensional"
            raise ValueError(msg)
        if len(x_data) != len(y_data):
            msg = "x_data and plot_info.data must have the same length"
            raise ValueError(msg)

    def add_plot(self, x_data: PlotXData, plot_info: PlotInfo) -> None:
        """系列を指定されたY軸へ追加し、凡例情報を保持する。"""
        self._validate_plot_data(x_data, plot_info.data)
        target_ax = self.ax1 if plot_info.axis is AxisSide.LEFT else self.get_ax2()
        target_ax.set_yscale(plot_info.scale.value)
        safe_label = self._get_safe_text(plot_info.label)
        (line,) = target_ax.plot(
            x_data,
            plot_info.data,
            plot_info.style,
            color=plot_info.color,
            label=safe_label,
            linewidth=(
                plot_info.linewidth if plot_info.linewidth is not None else self.style.line.width
            ),
        )
        self.lines.append(line)
        self.labels.append(safe_label)

    def adjust_axes_limits(self) -> None:
        """自動計算範囲と基準範囲を包含するY軸範囲へ調整する。"""
        for side in AxisSide:
            axis = self.ax1 if side is AxisSide.LEFT else self.ax2
            base_ylim = self._base_ylim[side]
            if axis is None or base_ylim is None:
                continue
            ymin_base, ymax_base = base_ylim
            ymin_auto, ymax_auto = axis.get_ylim()
            axis.set_ylim(min(ymin_base, ymin_auto), max(ymax_base, ymax_auto))

    def add_safe_text(
        self,
        x: float,
        y: float,
        text: str,
        ax_side: AxisSide = AxisSide.LEFT,
        **kwargs: Any,  # noqa: ANN401
    ) -> Text:
        """無効なmathtextを安全な代替文字列にして配置する。"""
        axis = self.ax1 if ax_side is AxisSide.LEFT else self.get_ax2()
        if self.style.text.font_family is not None:
            kwargs.setdefault("fontfamily", self.style.text.font_family)
        safe_text = self._get_safe_text(text)
        if safe_text == "[Label Error]":
            kwargs.pop("color", None)
            kwargs["color"] = "red"
        return axis.text(x, y, safe_text, **kwargs)

    def get_safe_text_dimensions(
        self,
        text: str,
        fontsize: int,
        ax_side: AxisSide = AxisSide.LEFT,
    ) -> tuple[float, float]:
        """ラベル配置に使う文字列のデータ幅とAxes相対高さを返す。"""
        axis = self.ax1 if ax_side is AxisSide.LEFT else self.get_ax2()
        renderer = cast("_RendererCanvas", self.fig.canvas).get_renderer()
        safe_text = self._get_safe_text(text)
        artist: Artist = axis.text(0, 0, safe_text, fontsize=fontsize)
        if self.style.text.font_family is not None:
            artist.set_fontfamily(self.style.text.font_family)
        bbox_display = artist.get_window_extent(renderer=renderer)
        bbox_data = bbox_display.transformed(axis.transData.inverted())
        bbox_axes = bbox_display.transformed(axis.transAxes.inverted())
        artist.remove()
        return float(bbox_data.width), float(bbox_axes.height)

    def create_legend(self) -> Legend | None:
        """現在の系列と設定から凡例を生成し、事前調整可能な状態で返す。"""
        current = self.ax1.get_legend()
        if not self.style.legend.visible:
            if current is not None:
                current.remove()
            return None
        legend_items = [
            (line, label) for line, label in zip(self.lines, self.labels, strict=True) if label
        ]
        if not legend_items:
            return None
        legend_lines, legend_labels = zip(*legend_items, strict=True)
        options = {
            "loc": self.style.legend.loc,
            "ncols": self.style.legend.ncols,
            "frameon": self.style.legend.frameon,
            "fontsize": self.style.legend.fontsize,
            **self.style.legend.options,
        }
        legend = self.ax1.legend(legend_lines, legend_labels, **options)
        if self.style.text.font_family is not None:
            for text in legend.get_texts():
                text.set_fontfamily(self.style.text.font_family)
        return legend

    def finalize(self) -> Figure:
        """軸範囲、凡例、layoutを確定してFigureを返す。"""
        self.adjust_axes_limits()
        self._apply_tick_font(self.ax1)
        if self.ax2 is not None:
            self._apply_tick_font(self.ax2)
        if not self.style.legend.visible:
            current_legend = self.ax1.get_legend()
            if current_legend is not None:
                current_legend.remove()
        elif self.ax1.get_legend() is None:
            self.create_legend()
        self.fig.tight_layout()
        return self.fig

    def close(self) -> None:
        """Figureが保持するArtistを破棄してbatch処理でのメモリ保持を防ぐ。"""
        self.lines.clear()
        self.labels.clear()
        if self.ax2 is not None:
            self.ax2.clear()
        self.ax1.clear()
        self.fig.clear()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
