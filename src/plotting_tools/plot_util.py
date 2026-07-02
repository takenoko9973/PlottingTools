"""Figure、Axes、系列情報を扱う描画ユーティリティ。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol, cast

from matplotlib import pyplot as plt
from matplotlib.mathtext import MathTextParser
from matplotlib.ticker import AutoMinorLocator
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    import pandas as pd
    from matplotlib.artist import Artist
    from matplotlib.axes import Axes
    from matplotlib.backend_bases import RendererBase
    from matplotlib.figure import Figure
    from matplotlib.lines import Line2D
    from matplotlib.text import Text

EPSILON = 1e-9


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


APP_CONFIG = PlotConfig()


@dataclass
class PlotStyleConfig:
    """GraphBuilderへ渡すFigureと文字サイズの設定。"""

    size: tuple[int, int] = (APP_CONFIG.default_size[0], APP_CONFIG.default_size[1])
    dpi: int = APP_CONFIG.default_dpi
    title_fontsize: int = APP_CONFIG.title_fontsize
    label_fontsize: int = APP_CONFIG.label_fontsize
    tick_fontsize: int = APP_CONFIG.tick_fontsize
    legend_fontsize: int = APP_CONFIG.legend_fontsize


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

    data: pd.Series[Any]
    axis: AxisSide = AxisSide.LEFT
    label: str = ""
    color: str | None = None
    style: str = "-"
    scale: ScaleEnum = ScaleEnum.LINEAR


class GraphBuilder:
    """左右Y軸を扱う薄いmatplotlib描画wrapper。"""

    def __init__(self, style_config: PlotStyleConfig | None = None) -> None:
        """Figureと左Y軸を生成し、共通の軸スタイルを適用する。"""
        self.style = style_config or PlotStyleConfig()
        self.fig, self.ax1 = plt.subplots(
            figsize=(
                self.style.size[0] / self.style.dpi,
                self.style.size[1] / self.style.dpi,
            ),
            dpi=self.style.dpi,
        )
        self.ax2: Axes | None = None
        self._setup_axis(self.ax1)
        self.ax1.tick_params(
            axis="both",
            which="major",
            labelsize=self.style.tick_fontsize,
            direction="in",
            top=True,
            left=True,
        )
        self.ax1.tick_params(
            axis="both",
            which="minor",
            direction="in",
            top=True,
            left=True,
        )
        self.lines: list[Line2D] = []
        self.labels: list[str] = []
        self._base_ylim: dict[AxisSide, tuple[float, float] | None] = {
            AxisSide.LEFT: None,
            AxisSide.RIGHT: None,
        }
        try:
            self._math_parser: MathTextParser | None = MathTextParser("agg")
        except Exception:  # noqa: BLE001
            self._math_parser = None

    def _is_valid_latex(self, text: str) -> bool:
        """matplotlibのmathtext parserで文字列を事前検証する。"""
        if not text or "$" not in text or self._math_parser is None:
            return True
        try:
            self._math_parser.parse(text)
        except Exception:  # noqa: BLE001
            return False
        return True

    def _get_safe_text(self, text: str) -> str:
        """無効なmathtextを描画可能な代替ラベルへ置き換える。"""
        return text if self._is_valid_latex(text) else "[Label Error]"

    @staticmethod
    def _setup_axis(ax: Axes) -> None:
        """軸へminor tick locatorを設定する。"""
        ax.xaxis.set_minor_locator(AutoMinorLocator(5))
        ax.yaxis.set_minor_locator(AutoMinorLocator(5))

    def get_ax2(self) -> Axes:
        """右Y軸を必要になった時点で生成して返す。"""
        if self.ax2 is None:
            self.ax2 = self.ax1.twinx()
            self._setup_axis(self.ax2)
            self.ax2.tick_params(
                which="major",
                labelsize=self.style.tick_fontsize,
                direction="in",
                right=True,
            )
            self.ax2.tick_params(which="minor", direction="in", right=True)
        return self.ax2

    def set_labels(self, xlabel: str, ylabel_left: str, ylabel_right: str = "") -> None:
        """X軸と左右Y軸のラベルを設定する。"""
        self.ax1.set_xlabel(self._get_safe_text(xlabel), fontsize=self.style.label_fontsize)
        self.ax1.set_ylabel(self._get_safe_text(ylabel_left), fontsize=self.style.label_fontsize)
        if ylabel_right:
            self.get_ax2().set_ylabel(
                self._get_safe_text(ylabel_right),
                fontsize=self.style.label_fontsize,
            )

    def set_title(self, title: str) -> None:
        """mathtextを検証してグラフタイトルを設定する。"""
        self.ax1.set_title(self._get_safe_text(title), fontsize=self.style.title_fontsize)

    def set_xlim(self, xmin: float, xmax: float) -> None:
        """同一値の場合にも幅を持つX軸範囲を設定する。"""
        if abs(xmax - xmin) < EPSILON:
            xmin -= 0.5
            xmax += 0.5
        self.ax1.set_xlim(xmin, xmax)

    def set_base_ylim(self, side: AxisSide, ymin: float, ymax: float) -> None:
        """自動範囲より狭くならないY軸の基準範囲を登録する。"""
        self._base_ylim[side] = (ymin, ymax)

    def set_yscale(self, side: AxisSide, scale: ScaleEnum | str) -> None:
        """指定した側のY軸スケールを設定する。"""
        target_ax = self.ax1 if side is AxisSide.LEFT else self.get_ax2()
        target_ax.set_yscale(scale.value if isinstance(scale, ScaleEnum) else scale)

    def add_plot(self, x_data: pd.Series[Any], plot_info: PlotInfo) -> None:
        """系列を指定されたY軸へ追加し、凡例情報を保持する。"""
        target_ax = self.ax1 if plot_info.axis is AxisSide.LEFT else self.get_ax2()
        target_ax.set_yscale(plot_info.scale.value)
        safe_label = self._get_safe_text(plot_info.label)
        (line,) = target_ax.plot(
            x_data,
            plot_info.data,
            plot_info.style,
            color=plot_info.color,
            label=safe_label,
        )
        if safe_label:
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
        if self._is_valid_latex(text):
            return axis.text(x, y, text, **kwargs)
        kwargs.pop("color", None)
        return axis.text(x, y, "[Label Error]", color="red", **kwargs)

    def get_safe_text_dimensions(
        self,
        text: str,
        fontsize: int,
        ax_side: AxisSide = AxisSide.LEFT,
    ) -> tuple[float, float]:
        """ラベル配置に使う文字列のデータ幅とAxes相対高さを返す。"""
        axis = self.ax1 if ax_side is AxisSide.LEFT else self.get_ax2()
        renderer = cast("_RendererCanvas", self.fig.canvas).get_renderer()
        artist: Artist | None = None
        try:
            artist = axis.text(0, 0, text, fontsize=fontsize)
            bbox_display = artist.get_window_extent(renderer=renderer)
        except Exception:  # noqa: BLE001
            if artist is not None:
                artist.remove()
            artist = axis.text(0, 0, "[Label Error]", fontsize=fontsize, color="red")
            bbox_display = artist.get_window_extent(renderer=renderer)
        bbox_data = bbox_display.transformed(axis.transData.inverted())
        bbox_axes = bbox_display.transformed(axis.transAxes.inverted())
        artist.remove()
        return float(bbox_data.width), float(bbox_axes.height)

    def finalize(self) -> Figure:
        """軸範囲、凡例、layoutを確定してFigureを返す。"""
        self.adjust_axes_limits()
        try:
            if self.labels:
                self.ax1.legend(
                    self.lines,
                    self.labels,
                    loc="best",
                    fontsize=self.style.legend_fontsize,
                )
            self.fig.tight_layout()
        except Exception:  # noqa: BLE001, S110
            pass
        return self.fig
