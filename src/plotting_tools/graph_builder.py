"""Figure、Axes、系列の追加、描画確定をGraphBuilderとしてまとめる。"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any, Literal, Protocol, Self, cast

import numpy as np
import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.mathtext import MathTextParser
from matplotlib.ticker import AutoMinorLocator

from plotting_tools.config import LegendLocation, PlotStyleConfig
from plotting_tools.models import AxisSide, PlotInfo, PlotXData, PlotYData, ScaleEnum

if TYPE_CHECKING:
    from matplotlib.artist import Artist
    from matplotlib.axes import Axes
    from matplotlib.axis import Axis
    from matplotlib.backend_bases import RendererBase
    from matplotlib.legend import Legend
    from matplotlib.lines import Line2D
    from matplotlib.text import Text
    from matplotlib.ticker import Formatter, Locator

# X軸範囲の幅が単一点とみなせるか判定する許容差 (データ座標)。
EPSILON = 1e-9


class _RendererCanvas(Protocol):
    """テキスト寸法計算に必要なcanvasの最小インターフェース。"""

    def get_renderer(self) -> RendererBase:
        """現在のFigure rendererを返す。"""


class GraphBuilder:
    """左右Y軸を扱う薄いmatplotlib描画wrapper。"""

    def __init__(self, style_config: PlotStyleConfig | None = None) -> None:
        """Figureと左Y軸を生成し、共通の軸スタイルを適用する。"""
        self.style = style_config or PlotStyleConfig()
        self.fig = self._create_figure()
        self.ax1 = self.fig.add_subplot()
        self.ax2: Axes | None = None

        self.lines: list[Line2D] = []
        self.labels: list[str] = []
        self._base_ylim: dict[AxisSide, tuple[float, float] | None] = {
            AxisSide.LEFT: None,
            AxisSide.RIGHT: None,
        }
        self._math_parser = MathTextParser("agg")

        self._setup_axis(self.ax1)
        self._apply_initial_limits()

    def _create_figure(self) -> Figure:
        """ピクセル指定をインチへ変換し、headless描画可能なFigureを生成する。"""
        width_px, height_px = self.style.figure.size
        dpi = self.style.figure.dpi
        figure = Figure(
            figsize=(width_px / dpi, height_px / dpi),
            dpi=dpi,
        )
        FigureCanvasAgg(figure)
        return figure

    def _apply_initial_limits(self) -> None:
        """スタイルで指定された初期軸範囲を各Axesへ反映する。"""
        axes_style = self.style.axes

        if axes_style.xlim is not None:
            self.ax1.set_xlim(*axes_style.xlim)

        if axes_style.left_ylim is not None:
            self.set_ylim(AxisSide.LEFT, *axes_style.left_ylim)

        if axes_style.right_ylim is not None:
            self.set_ylim(AxisSide.RIGHT, *axes_style.right_ylim)

    def _setup_axis(self, axis: Axes) -> None:
        """Axesへ目盛とgridの既定スタイルを設定する。"""
        axis.xaxis.set_minor_locator(AutoMinorLocator(5))
        axis.yaxis.set_minor_locator(AutoMinorLocator(5))

        axis.tick_params(
            axis="both",
            which="major",
            labelsize=self.style.text.tick_fontsize,
            direction=self.style.axes.tick_direction,
            top=True,
        )
        axis.tick_params(
            axis="both",
            which="minor",
            direction=self.style.axes.tick_direction,
            top=True,
        )

        # grid=Falseで線設定を渡すと、matplotlibがgridを再び有効化するため空dictを渡す。
        grid_options = self.style.axes.grid_options if self.style.axes.grid else {}
        axis.grid(
            self.style.axes.grid,
            which=self.style.axes.grid_which,
            axis=self.style.axes.grid_axis,
            **grid_options,
        )

    def _apply_tick_font(self, axis: Axes) -> None:
        """生成済みの目盛ラベルへ指定フォントを適用する。"""
        font_family = self.style.text.font_family
        if font_family is None:
            return

        tick_labels = (*axis.get_xticklabels(), *axis.get_yticklabels())
        for label in tick_labels:
            label.set_fontfamily(font_family)

    def _is_valid_mathtext(self, text: str) -> bool:
        """matplotlibのmathtext parserで文字列を事前検証する。"""
        if not text or "$" not in text:
            return True

        try:
            self._math_parser.parse(text)
        except ValueError:
            return False

        return True

    def _get_safe_text(self, text: str) -> str:
        """無効なmathtextを描画可能な代替ラベルへ置き換える。"""
        if self._is_valid_mathtext(text):
            return text

        msg = f"invalid mathtext: {text!r}"
        if self.style.strict_mathtext:
            raise ValueError(msg)

        warnings.warn(msg, UserWarning, stacklevel=3)
        return "[Label Error]"

    def _apply_font_family(self, text: Text) -> None:
        """fontdict経由では型が不安定なfont familyをTextへ直接設定する。"""
        font_family = self.style.text.font_family
        if font_family is not None:
            text.set_fontfamily(font_family)

    # Axes access and configuration

    def get_ax2(self) -> Axes:
        """右Y軸を必要になった時点で生成して返す。"""
        if self.ax2 is None:
            self.ax2 = self.ax1.twinx()
            self._setup_axis(self.ax2)
            self._apply_tick_font(self.ax2)

        return self.ax2

    def get_axis(self, side: AxisSide = AxisSide.LEFT) -> Axes:
        """高度なmatplotlib設定に使う指定側のAxesを返す。"""
        if side is AxisSide.LEFT:
            return self.ax1

        return self.get_ax2()

    def set_labels(self, xlabel: str, ylabel_left: str, ylabel_right: str = "") -> None:
        """X軸と左右Y軸のラベルを設定する。"""
        options: dict[str, Any] = {
            "fontsize": self.style.text.label_fontsize,
            **self.style.text.label_options,
        }

        xlabel_text = self.ax1.set_xlabel(
            self._get_safe_text(xlabel),
            fontdict=options,
        )
        left_label_text = self.ax1.set_ylabel(
            self._get_safe_text(ylabel_left),
            fontdict=options,
        )
        self._apply_font_family(xlabel_text)
        self._apply_font_family(left_label_text)

        if ylabel_right:
            right_label_text = self.get_ax2().set_ylabel(
                self._get_safe_text(ylabel_right),
                fontdict=options,
            )
            self._apply_font_family(right_label_text)

    def set_title(self, title: str) -> None:
        """mathtextを検証してグラフタイトルを設定する。"""
        options: dict[str, Any] = {
            "fontsize": self.style.text.title_fontsize,
            **self.style.text.title_options,
        }
        title_text = self.ax1.set_title(
            self._get_safe_text(title),
            fontdict=options,
        )
        self._apply_font_family(title_text)

    def set_xlim(self, xmin: float, xmax: float) -> None:
        """同一値の場合にも幅を持つX軸範囲を設定する。"""
        # matplotlibのsingular warningを避け、単一点の周囲に視認可能な幅を確保する。
        if abs(xmax - xmin) < EPSILON:
            xmin -= 0.5
            xmax += 0.5

        self.ax1.set_xlim(xmin, xmax)

    def set_ylim(self, side: AxisSide, ymin: float, ymax: float) -> None:
        """自動範囲に左右されない厳密なY軸範囲を設定する。"""
        if ymin >= ymax:
            msg = "ymin must be smaller than ymax"
            raise ValueError(msg)

        self.get_axis(side).set_ylim(ymin, ymax)

    def expand_ylim_to_include(self, side: AxisSide, ymin: float, ymax: float) -> None:
        """自動範囲が最低限包含するY軸範囲を登録する。"""
        if ymin >= ymax:
            msg = "ymin must be smaller than ymax"
            raise ValueError(msg)

        self._base_ylim[side] = (ymin, ymax)

    @staticmethod
    def _set_locator(
        axis: Axis,
        locator: Locator,
        which: Literal["major", "minor"],
    ) -> None:
        """指定されたmajor/minor側へlocatorを設定する。"""
        if which == "major":
            axis.set_major_locator(locator)
        else:
            axis.set_minor_locator(locator)

    def set_x_locator(
        self,
        locator: Locator,
        *,
        which: Literal["major", "minor"] = "major",
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
        """指定されたmajor/minor側へformatterを設定する。"""
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
        scale_name = scale.value if isinstance(scale, ScaleEnum) else scale
        self.get_axis(side).set_yscale(scale_name)

    # Plot series and annotations

    @staticmethod
    def _validate_plot_data(x_data: PlotXData, y_data: PlotYData) -> None:
        """X/Yデータが1次元かつ同じ長さであることを検証する。"""
        # 型注釈だけでは2次元ndarrayや実行時のDataFrameを排除できない。
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

        target_axis = self.get_axis(plot_info.axis)
        target_axis.set_yscale(plot_info.scale.value)
        safe_label = self._get_safe_text(plot_info.label)
        linewidth = plot_info.linewidth or self.style.line.width

        (line,) = target_axis.plot(
            x_data,
            plot_info.data,
            plot_info.style,
            color=plot_info.color,
            label=safe_label,
            linewidth=linewidth,
        )
        self.lines.append(line)
        self.labels.append(safe_label)

    def add_safe_text(
        self,
        x: float,
        y: float,
        text: str,
        ax_side: AxisSide = AxisSide.LEFT,
        **kwargs: Any,  # noqa: ANN401
    ) -> Text:
        """無効なmathtextを安全な代替文字列にして配置する。"""
        axis = self.get_axis(ax_side)
        font_family = self.style.text.font_family
        if font_family is not None:
            kwargs.setdefault("fontfamily", font_family)

        safe_text = self._get_safe_text(text)
        if safe_text == "[Label Error]":
            # 壊れたラベルを通常の注釈と誤認しないよう、指定色より赤を優先する。
            kwargs["color"] = "red"

        return axis.text(x, y, safe_text, **kwargs)

    def get_safe_text_dimensions(
        self,
        text: str,
        fontsize: int,
        ax_side: AxisSide = AxisSide.LEFT,
    ) -> tuple[float, float]:
        """ラベル配置に使う文字列のデータ幅とAxes相対高さを返す。"""
        axis = self.get_axis(ax_side)
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

    # Finalization and resource cleanup

    def adjust_axes_limits(self) -> None:
        """自動計算範囲と基準範囲を包含するY軸範囲へ調整する。"""
        for side in AxisSide:
            axis = self.ax1 if side is AxisSide.LEFT else self.ax2
            base_ylim = self._base_ylim[side]

            if axis is None or base_ylim is None:
                continue

            ymin_base, ymax_base = base_ylim
            ymin_auto, ymax_auto = axis.get_ylim()
            axis.set_ylim(
                min(ymin_base, ymin_auto),
                max(ymax_base, ymax_auto),
            )

    def create_legend(self) -> Legend | None:
        """現在の系列と設定から凡例を生成し、事前調整可能な状態で返す。"""
        current_legend = self.ax1.get_legend()
        if not self.style.legend.visible:
            if current_legend is not None:
                current_legend.remove()
            return None

        legend_items = [
            (line, label) for line, label in zip(self.lines, self.labels, strict=True) if label
        ]
        if not legend_items:
            return None

        legend_lines, legend_labels = zip(*legend_items, strict=True)
        # 既存APIと同様、options内の重複キーを個別設定より優先してmatplotlibへ渡す。
        additional_options = self.style.legend.options.copy()
        legend_location = cast(
            "LegendLocation",
            additional_options.pop("loc", self.style.legend.loc),
        )
        legend_columns = cast(
            "int",
            additional_options.pop("ncols", self.style.legend.ncols),
        )
        legend_frame = cast(
            "bool",
            additional_options.pop("frameon", self.style.legend.frameon),
        )
        legend_fontsize = cast(
            "int",
            additional_options.pop("fontsize", self.style.legend.fontsize),
        )
        legend = self.ax1.legend(
            legend_lines,
            legend_labels,
            loc=legend_location,
            ncols=legend_columns,
            frameon=legend_frame,
            fontsize=legend_fontsize,
            **additional_options,
        )

        font_family = self.style.text.font_family
        if font_family is not None:
            for text in legend.get_texts():
                text.set_fontfamily(font_family)

        return legend

    def _finalize_legend(self) -> None:
        """表示設定に従って既存凡例の削除または凡例生成を行う。"""
        current_legend = self.ax1.get_legend()

        if not self.style.legend.visible:
            if current_legend is not None:
                current_legend.remove()
            return

        if current_legend is None:
            self.create_legend()

    def finalize(self) -> Figure:
        """軸範囲、凡例、layoutを確定してFigureを返す。"""
        self.adjust_axes_limits()
        self._apply_tick_font(self.ax1)

        if self.ax2 is not None:
            self._apply_tick_font(self.ax2)

        self._finalize_legend()
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
        """Context manager内で同じGraphBuilderを返す。"""
        return self

    def __exit__(self, *args: object) -> None:
        """Context manager終了時にFigureが保持するArtistを破棄する。"""
        self.close()
