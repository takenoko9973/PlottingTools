"""既存のMatplotlib Artistへグループ別の表示設定を適用する。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from plotting_tools.models import AxisSide

if TYPE_CHECKING:
    from matplotlib.axis import Axis
    from matplotlib.collections import PathCollection
    from matplotlib.legend import Legend
    from matplotlib.lines import Line2D
    from matplotlib.text import Text
    from matplotlib.ticker import Formatter, Locator
    from matplotlib.typing import ColorType, LegendLocType

    from plotting_tools.graph_builder import GraphBuilder


class AxisStyleGroup:
    """X軸または左右Y軸の既存Artistを操作する。"""

    def __init__(self, builder: GraphBuilder, target: Literal["x", "y", "right_y"]) -> None:
        self._builder = builder
        self._target = target

    def style(  # noqa: C901, PLR0913
        self,
        *,
        label_size: float | None = None,
        label_color: ColorType | None = None,
        tick_label_size: float | None = None,
        tick_direction: Literal["in", "out", "inout"] | None = None,
        tick_length: float | None = None,
        tick_width: float | None = None,
        major_locator: Locator | None = None,
        minor_locator: Locator | None = None,
        major_formatter: Formatter | None = None,
        minor_formatter: Formatter | None = None,
        grid: bool | None = None,
    ) -> None:
        """指定した属性だけを更新する。文字サイズ・目盛寸法はpt単位。"""
        side = AxisSide.RIGHT if self._target == "right_y" else AxisSide.LEFT
        axes = self._builder.get_axis(side)
        axis: Axis = axes.xaxis if self._target == "x" else axes.yaxis
        if label_size is not None:
            axis.label.set_fontsize(label_size)
        if label_color is not None:
            axis.label.set_color(label_color)
        if tick_label_size is not None:
            axis.set_tick_params(which="both", labelsize=tick_label_size)
        if tick_direction is not None:
            axis.set_tick_params(which="both", direction=tick_direction)
        if tick_length is not None:
            axis.set_tick_params(which="major", length=tick_length)
        if tick_width is not None:
            axis.set_tick_params(which="major", width=tick_width)
        if major_locator is not None:
            axis.set_major_locator(major_locator)
        if minor_locator is not None:
            axis.set_minor_locator(minor_locator)
        if major_formatter is not None:
            axis.set_major_formatter(major_formatter)
        if minor_formatter is not None:
            axis.set_minor_formatter(minor_formatter)
        if grid is not None:
            axis.grid(grid)


class TitleStyleGroup:
    """タイトル文字列と独立して既存Textの外観を操作する。"""

    def __init__(self, text: Text) -> None:
        self._text = text

    def style(self, *, font_size: float | None = None, color: ColorType | None = None) -> None:
        """指定した文字サイズ(pt)と色だけを変更する。"""
        if font_size is not None:
            self._text.set_fontsize(font_size)
        if color is not None:
            self._text.set_color(color)


class LegendStyleGroup:
    """再生成に必要な明示値だけを保持し、既存Legendを操作する。"""

    def __init__(self, builder: GraphBuilder) -> None:
        self._builder = builder
        self._visible = True
        self._loc: LegendLocType | None = None
        self._font_size: float | None = None
        self._frame: bool | None = None
        self._ncols: int | None = None

    @property
    def visible(self) -> bool:
        """イベント注釈の衝突判定にも用いる実際の表示状態。"""
        legend = self._builder.ax1.get_legend()
        return legend.get_visible() if legend is not None else self._visible

    def style(  # noqa: C901
        self,
        *,
        visible: bool | None = None,
        loc: LegendLocType | None = None,
        font_size: float | None = None,
        frame: bool | None = None,
        ncols: int | None = None,
    ) -> None:
        """生成前の設定または生成済み凡例の指定属性を更新する。"""
        if ncols is not None and ncols <= 0:
            msg = "legend ncols must be positive"
            raise ValueError(msg)
        legend = self._builder.ax1.get_legend()
        # イベントの衝突測定では凡例を一時生成して除去するため、再生成に
        # 必要な明示値だけ保持する。Artistの全属性を複製する設定モデルは持たない。
        if visible is not None:
            self._visible = visible
        if loc is not None:
            self._loc = loc
        if font_size is not None:
            self._font_size = font_size
        if frame is not None:
            self._frame = frame
        if ncols is not None:
            self._ncols = ncols
        if legend is None:
            return
        if visible is not None:
            legend.set_visible(visible)
        if loc is not None:
            legend.set_loc(loc)
        if frame is not None:
            legend.set_frame_on(frame)
        if ncols is not None or font_size is not None:
            self._refresh_layout(legend, ncols, font_size)

    @staticmethod
    def _refresh_layout(legend: Legend, ncols: int | None, font_size: float | None) -> None:
        """既存凡例を維持したままMatplotlibに項目を再配置させる。"""
        texts = legend.get_texts()
        title = legend.get_title()
        if ncols is not None:
            legend.set_ncols(ncols)
        if font_size is not None:
            legend.prop.set_size(font_size)
            for text in texts:
                text.set_fontsize(font_size)
            legend._fontsize = font_size  # ty: ignore[unresolved-attribute]  # noqa: SLF001
        # Matplotlibのset_ncolsは既存boxを再配置しない。内部のbox構築だけを
        # 呼び直し、Legend・frame・利用者が編集したTextの属性は維持する。
        legend._init_legend_box(  # ty: ignore[unresolved-attribute]  # noqa: SLF001
            legend.legend_handles, [text.get_text() for text in texts]
        )
        for updated, previous in zip(legend.get_texts(), texts, strict=True):
            transform = updated.get_transform()
            updated.update_from(previous)
            updated.set_transform(transform)
        legend.set_title(title.get_text(), prop=title.get_fontproperties())
        transform = legend.get_title().get_transform()
        legend.get_title().update_from(title)
        legend.get_title().set_transform(transform)
        legend.set_loc(legend._loc)  # ty: ignore[unresolved-attribute]  # noqa: SLF001

    def _create(self, handles: list[Line2D | PathCollection], labels: list[str]) -> Legend | None:
        """明示された設定と現在の系列から凡例を生成する。"""
        items = [(handle, label) for handle, label in zip(handles, labels, strict=True) if label]
        if not self._visible or not items:
            return None
        legend_handles, legend_labels = zip(*items, strict=True)
        return self._builder.ax1.legend(
            legend_handles,
            legend_labels,
            loc=self._loc,
            fontsize=self._font_size,
            frameon=self._frame,
            ncols=self._ncols if self._ncols is not None else 1,
        )
