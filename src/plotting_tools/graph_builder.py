"""Figure、Axes、系列の追加、描画確定をGraphBuilderとしてまとめる。"""

from __future__ import annotations

import warnings
from math import isfinite
from numbers import Real
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol, Self, cast

import matplotlib as mpl
import matplotlib.style as mplstyle
import numpy as np
import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.mathtext import MathTextParser
from matplotlib.ticker import AutoMinorLocator
from mpl_toolkits.axes_grid1.axes_divider import Divider
from mpl_toolkits.axes_grid1.axes_size import Fixed

from plotting_tools.config import PlotStyleConfig
from plotting_tools.models import AxisSide, PlotInfo, PlotXData, PlotYData, ScaleEnum

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

    from matplotlib.artist import Artist
    from matplotlib.axes import Axes
    from matplotlib.axis import Axis
    from matplotlib.backend_bases import RendererBase
    from matplotlib.collections import PathCollection
    from matplotlib.legend import Legend
    from matplotlib.lines import Line2D
    from matplotlib.text import Text
    from matplotlib.ticker import Formatter, Locator
    from matplotlib.typing import LineStyleType, MarkerType
    from numpy.typing import ArrayLike

# X軸範囲の幅が単一点とみなせるか判定する許容差 (データ座標)。
EPSILON = 1e-9


class _RendererCanvas(Protocol):
    """テキスト寸法計算に必要なcanvasの最小インターフェース。"""

    def get_renderer(self) -> RendererBase:
        """現在のFigure rendererを返す。"""


class GraphBuilder:
    """左右Y軸を扱う薄いmatplotlib描画wrapper。"""

    def __init__(
        self,
        style_config: PlotStyleConfig | None = None,
        *,
        style: str | Path | list[str | Path] | None = None,
        fig_size: tuple[float, float] | None = None,
        axes_size: tuple[float, float] | None = None,
    ) -> None:
        """Figureと左Y軸を生成する。fig_size/axes_sizeは排他的なインチ寸法。"""
        if fig_size is not None and axes_size is not None:
            msg = "fig_size and axes_size cannot be specified together"
            raise ValueError(msg)
        self._fig_size = self._validate_size("fig_size", fig_size)
        self._axes_size = self._validate_size("axes_size", axes_size)
        self.style = style_config or PlotStyleConfig()
        paper = Path(__file__).with_name("styles") / "paper.mplstyle"
        if style is None:
            selected = []
        elif isinstance(style, list):
            selected = style
        else:
            selected = [style]
        styles = [paper, *(paper if item == "paper" else item for item in selected)]
        # 生成時の設定を保持し、後から別のグラフやglobal rcParamsが変わっても分離する。
        with mplstyle.context(styles, after_reset=True):
            self._rc_params = dict(mpl.rcParams)
        # backendはrc_contextで復元されないため、グラフの設定対象に含めない。
        self._rc_params.pop("backend", None)
        self.fig = self._create_figure()
        with self._style_context():
            self.ax1 = self.fig.add_subplot()
        self.ax2: Axes | None = None

        self.lines: list[Line2D] = []
        self._legend_handles: list[Line2D | PathCollection] = []
        self.labels: list[str] = []
        self._base_ylim: dict[AxisSide, tuple[float, float] | None] = {
            AxisSide.LEFT: None,
            AxisSide.RIGHT: None,
        }
        self._math_parser = MathTextParser("agg")

        with self._style_context():
            self._setup_axis(self.ax1)
        self._apply_initial_limits()
        if self._axes_size is not None:
            self._position_fixed_axes(0, 0, 0, 0)

    @staticmethod
    def _validate_size(name: str, size: tuple[float, float] | None) -> tuple[float, float] | None:
        """インチ寸法を正の有限実数2つとして検証する。"""
        if size is None:
            return None
        msg = f"{name} must contain two positive finite numbers"
        try:
            width, height = size
        except (TypeError, ValueError) as exc:
            raise ValueError(msg) from exc
        if any(
            not isinstance(value, Real) or not isfinite(value) or value <= 0
            for value in (width, height)
        ):
            raise ValueError(msg)
        return float(width), float(height)

    def _style_context(self) -> AbstractContextManager[None]:
        """対象グラフのテンプレートと明示フォントを操作中だけ有効にする。"""
        params = self._rc_params.copy()
        if self.style.text.font_family is not None:
            params["font.family"] = self.style.text.font_family
        if self.style.axes.grid_which is not None:
            params["axes.grid.which"] = self.style.axes.grid_which
        if self.style.axes.grid_axis is not None:
            params["axes.grid.axis"] = self.style.axes.grid_axis
        return mpl.rc_context(rc=params)

    def _create_figure(self) -> Figure:
        """明示インチ寸法、従来pixel寸法、styleの順でFigure寸法を解決する。"""
        with self._style_context():
            options: dict[str, Any] = {}
            dpi = self.style.figure.dpi
            if dpi is not None:
                options["dpi"] = dpi
            if self._fig_size is not None or self._axes_size is not None:
                options["figsize"] = self._fig_size or self._axes_size
            elif self.style.figure.size is not None:
                width_px, height_px = self.style.figure.size
                effective_dpi = dpi if dpi is not None else mpl.rcParams["figure.dpi"]
                options["figsize"] = (width_px / effective_dpi, height_px / effective_dpi)
            figure = Figure(**options)
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
        # 分割数をグラフの設定で確定し、context外の遅延描画でも同じ間隔を保つ。
        # ライブラリ既定のlocatorは、scale変更時に標準の対数locatorへ交換できる状態にする。
        if mpl.rcParams["xtick.minor.visible"]:
            axis.xaxis.set_minor_locator(AutoMinorLocator(mpl.rcParams["xtick.minor.ndivs"]))
            axis.xaxis.isDefault_minloc = True
        if mpl.rcParams["ytick.minor.visible"]:
            axis.yaxis.set_minor_locator(AutoMinorLocator(mpl.rcParams["ytick.minor.ndivs"]))
            axis.yaxis.isDefault_minloc = True

        tick_options: dict[str, Any] = {}
        if self.style.text.tick_fontsize is not None:
            tick_options["labelsize"] = self.style.text.tick_fontsize
        if self.style.axes.tick_direction is not None:
            tick_options["direction"] = self.style.axes.tick_direction
        axis.tick_params(axis="both", which="major", **tick_options)
        tick_options.pop("labelsize", None)
        axis.tick_params(axis="both", which="minor", **tick_options)

        axes_style = self.style.axes
        if axes_style.grid is not None or axes_style.grid_options:
            # grid=Falseで線設定を渡すと再び有効になるため、明示無効時は渡さない。
            options = axes_style.grid_options if axes_style.grid is not False else {}
            axis.grid(
                axes_style.grid,
                which=axes_style.grid_which or mpl.rcParams["axes.grid.which"],
                axis=axes_style.grid_axis or mpl.rcParams["axes.grid.axis"],
                **options,
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
        with self._style_context():
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
        with self._style_context():
            options: dict[str, Any] = {
                **self.style.text.label_options,
            }

            if self.style.text.label_fontsize is not None:
                options.setdefault("fontsize", self.style.text.label_fontsize)

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
        with self._style_context():
            options: dict[str, Any] = {
                **self.style.text.title_options,
            }
            if self.style.text.title_fontsize is not None:
                options.setdefault("fontsize", self.style.text.title_fontsize)
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
        with self._style_context():
            scale_name = scale.value if isinstance(scale, ScaleEnum) else scale
            axis = self.get_axis(side)
            if axis.get_yscale() == scale_name:
                return

            yaxis = axis.yaxis
            custom_formatters: list[tuple[Literal["major", "minor"], Formatter]] = []
            custom_locators: list[tuple[Literal["major", "minor"], Locator]] = []
            if not yaxis.isDefault_majfmt:
                custom_formatters.append(("major", yaxis.get_major_formatter()))
            if not yaxis.isDefault_minfmt:
                custom_formatters.append(("minor", yaxis.get_minor_formatter()))
            if not yaxis.isDefault_majloc:
                custom_locators.append(("major", yaxis.get_major_locator()))
            if not yaxis.isDefault_minloc:
                custom_locators.append(("minor", yaxis.get_minor_locator()))

            # Matplotlibはscale変更時にtickerも初期化する。明示指定だけ復元し、
            # 既定のtickerにはlinear/logそれぞれの標準実装を使う。
            axis.set_yscale(scale_name)
            for which, formatter in custom_formatters:
                self._set_formatter(yaxis, formatter, which)
            for which, locator in custom_locators:
                self._set_locator(yaxis, locator, which)

    # Plot series and annotations

    def line(
        self,
        x: PlotXData,
        y: PlotYData,
        *,
        label: str = "",
        color: str | None = None,
        linestyle: LineStyleType | None = None,
        linewidth: float | None = None,
        marker: MarkerType | None = None,
        markersize: float | None = None,
        side: AxisSide | Literal["left", "right"] = AxisSide.LEFT,
        scale: ScaleEnum | Literal["linear", "log"] | None = None,
    ) -> Line2D:
        """X/Yと必要な属性だけで系列を追加し、直接編集できるLine2Dを返す。"""
        axis_side = side if isinstance(side, AxisSide) else AxisSide(side)
        axis_scale = ScaleEnum(scale) if scale is not None else None
        self.add_plot(
            x,
            PlotInfo(
                data=y,
                axis=axis_side,
                label=label,
                color=color,
                linewidth=linewidth,
                scale=axis_scale,
            ),
        )
        line = self.lines[-1]
        if linestyle is not None:
            # PlotInfo.styleの位置引数fmtと異なり、属性名の線種は標準setterで扱う。
            line.set_linestyle(linestyle)
        if marker is not None:
            line.set_marker(marker)
        if markersize is not None:
            line.set_markersize(markersize)
        return line

    def scatter(
        self,
        x: PlotXData,
        y: PlotYData,
        *,
        color: str | None = None,
        marker: MarkerType | None = None,
        s: float | ArrayLike | None = None,
        label: str = "",
        side: AxisSide | Literal["left", "right"] = AxisSide.LEFT,
        scale: ScaleEnum | Literal["linear", "log"] | None = None,
    ) -> PathCollection:
        """X/Yを指定したY軸へ散布図として追加し、編集可能なcollectionを返す。"""
        axis_side = side if isinstance(side, AxisSide) else AxisSide(side)
        axis_scale = ScaleEnum(scale) if scale is not None else None
        with self._style_context():
            self._validate_plot_data(x, y)
            target_axis = self.get_axis(axis_side)
            if axis_scale is not None:
                self.set_yscale(axis_side, axis_scale)
            safe_label = self._get_safe_text(label)
            points = target_axis.scatter(
                x,
                y,
                color=color,
                marker=marker,
                s=s,
                label=safe_label,
            )
            self._legend_handles.append(points)
            self.labels.append(safe_label)
            return points

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
        with self._style_context():
            self._validate_plot_data(x_data, plot_info.data)

            target_axis = self.get_axis(plot_info.axis)
            if plot_info.scale is not None:
                self.set_yscale(plot_info.axis, plot_info.scale)
            safe_label = self._get_safe_text(plot_info.label)
            linewidth = (
                plot_info.linewidth if plot_info.linewidth is not None else self.style.line.width
            )
            options: dict[str, Any] = {}
            if linewidth is not None:
                options["linewidth"] = linewidth
            formats = (plot_info.style,) if plot_info.style is not None else ()

            (line,) = target_axis.plot(
                x_data,
                plot_info.data,
                *formats,
                color=plot_info.color,
                label=safe_label,
                **options,
            )
            self.lines.append(line)
            self._legend_handles.append(line)
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
        with self._style_context():
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
        fontsize: float,
        ax_side: AxisSide = AxisSide.LEFT,
    ) -> tuple[float, float]:
        """ラベル配置に使う文字列のデータ幅とAxes相対高さを返す。"""
        with self._style_context():
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
        with self._style_context():
            current_legend = self.ax1.get_legend()
            if not self.style.legend.visible:
                if current_legend is not None:
                    current_legend.remove()
                return None

            legend_items = [
                (handle, label)
                for handle, label in zip(self._legend_handles, self.labels, strict=True)
                if label
            ]
            if not legend_items:
                return None

            legend_handles, legend_labels = zip(*legend_items, strict=True)
            # 既存APIと同様、options内の重複キーを個別設定より優先してmatplotlibへ渡す。
            options: dict[str, Any] = {"ncols": self.style.legend.ncols}
            explicit_options = (
                ("loc", self.style.legend.loc),
                ("frameon", self.style.legend.frameon),
                ("fontsize", self.style.legend.fontsize),
            )
            options.update({key: value for key, value in explicit_options if value is not None})
            options.update(self.style.legend.options)
            legend = self.ax1.legend(legend_handles, legend_labels, **options)

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

    def _position_fixed_axes(self, left: float, right: float, bottom: float, top: float) -> None:
        """装飾の余白とAxesをインチ単位で配置する。"""
        assert self._axes_size is not None
        width, height = self._axes_size
        self.fig.set_size_inches(left + width + right, bottom + height + top)
        divider = Divider(
            self.fig,
            (0, 0, 1, 1),
            horizontal=[Fixed(left), Fixed(width), Fixed(right)],
            vertical=[Fixed(bottom), Fixed(height), Fixed(top)],
            aspect=False,
        )
        locator = divider.new_locator(nx=1, ny=1)
        self.ax1.set_axes_locator(locator)
        if self.ax2 is not None:
            self.ax2.set_axes_locator(locator)

    def _layout_fixed_axes(self) -> None:
        """Axesの実寸を保ち、装飾が収まるFigure寸法を描画結果から決める。"""
        # tight/constrained layoutによる再配置を避け、inch固定のlocatorに委ねる。
        self.fig.set_layout_engine("none")
        # tight_layout既定と同じfont sizeの1.08倍を外周の余白として確保する。
        pad = 1.08 * self._rc_params["font.size"] / 72
        # 毎回同じ寸法から測り直し、finalize/saveによる余白の累積を防ぐ。
        self._position_fixed_axes(pad, pad, pad, pad)
        self.fig.canvas.draw()
        renderer = cast("_RendererCanvas", self.fig.canvas).get_renderer()
        axes_bbox = self.ax1.bbox
        left = right = bottom = top = 0.0
        for axis in (self.ax1, self.ax2):
            if axis is None:
                continue
            bounds = axis.get_tightbbox(renderer)
            if bounds is None:
                continue
            left = max(left, axes_bbox.x0 - bounds.x0)
            right = max(right, bounds.x1 - axes_bbox.x1)
            bottom = max(bottom, axes_bbox.y0 - bounds.y0)
            top = max(top, bounds.y1 - axes_bbox.y1)
        # bboxは描画pixel、Fixedはinch。保存backendのDPI変更時も実寸を保つ。
        dpi = self.fig.dpi
        self._position_fixed_axes(
            left / dpi + pad, right / dpi + pad, bottom / dpi + pad, top / dpi + pad
        )
        self.fig.canvas.draw()

    def finalize(self) -> Figure:
        """軸範囲、凡例、layoutを確定してFigureを返す。"""
        with self._style_context():
            self.adjust_axes_limits()
            self._apply_tick_font(self.ax1)

            if self.ax2 is not None:
                self._apply_tick_font(self.ax2)

            self._finalize_legend()
            if self._axes_size is None:
                self.fig.tight_layout()
            else:
                self._layout_fixed_axes()
            return self.fig

    def save(self, path: str | Path, **kwargs: Any) -> None:  # noqa: ANN401
        """layoutと保存時にもテンプレートを有効にしてMatplotlib形式で保存する。"""
        with self._style_context():
            self.finalize().savefig(path, **kwargs)

    def close(self) -> None:
        """Figureが保持するArtistを破棄してbatch処理でのメモリ保持を防ぐ。"""
        with self._style_context():
            self.lines.clear()
            self._legend_handles.clear()
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
