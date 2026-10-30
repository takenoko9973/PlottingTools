"""科学表記と軸設定の保持を利用者に見える出力で検証する。"""

import math
import sys
from functools import partial
from pathlib import Path

import pytest
from matplotlib.mathtext import MathTextParser
from matplotlib.ticker import (
    FuncFormatter,
    LogFormatterMathtext,
    LogLocator,
    MultipleLocator,
    ScalarFormatter,
)

from plotting_tools import AxisSide, GraphBuilder, PlotInfo, ScaleEnum, format_sci_mathtext


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.0, "0"),
        (-0.0, "0"),
        (1.0, r"$1.0 \times 10^{0}$"),
        (-2.5e6, r"$-2.5 \times 10^{6}$"),
        (1e-8, r"$1.0 \times 10^{-8}$"),
        (1e9, r"$1.0 \times 10^{9}$"),
        (9.99, r"$1.0 \times 10^{1}$"),
        (-9.99e-4, r"$-1.0 \times 10^{-3}$"),
        (math.ulp(0.0), r"$4.9 \times 10^{-324}$"),
        (-math.ulp(0.0), r"$-4.9 \times 10^{-324}$"),
        (sys.float_info.max, r"$1.8 \times 10^{308}$"),
        (math.inf, r"$\infty$"),
        (-math.inf, r"$-\infty$"),
        (math.nan, r"$\mathrm{NaN}$"),
    ],
)
def test_scientific_values_are_normalized_and_renderable(value: float, expected: str) -> None:
    """有限値と特殊値の科学表記が期待どおりで描画可能なことを確認する。"""
    result = format_sci_mathtext(value, 0)
    assert result == expected
    MathTextParser("agg").parse(result)


def test_scientific_precision_works_with_native_funcformatter() -> None:
    """指定精度の科学表記と不正精度の拒否を確認する。"""
    formatter = FuncFormatter(partial(format_sci_mathtext, precision=3))
    assert formatter(1.23456e-8, 0) == r"$1.235 \times 10^{-8}$"
    assert format_sci_mathtext(99.99, precision=0) == r"$1 \times 10^{2}$"
    with pytest.raises(ValueError, match="precision"):
        format_sci_mathtext(1, precision=-1)


def test_automatic_mathtext_for_x_and_both_y_axes() -> None:
    """X軸と左右Y軸が指数をMathtextで表示することを確認する。"""
    with GraphBuilder() as builder:
        builder.add_plot([1e-8, 2e-8, 3e-8], PlotInfo(data=[1e9, 2e9, 3e9]))
        builder.add_plot([1e-8, 2e-8, 3e-8], PlotInfo(data=[1e-8, 2e-8, 3e-8], axis=AxisSide.RIGHT))
        builder.finalize().canvas.draw()
        for axis in (builder.ax1.xaxis, builder.ax1.yaxis, builder.get_ax2().yaxis):
            formatter = axis.get_major_formatter()
            assert isinstance(formatter, ScalarFormatter)
            assert formatter.get_useMathText()
            assert r"\times" in axis.get_offset_text().get_text()
            assert all(r"\times" not in label.get_text() for label in axis.get_ticklabels())
    with GraphBuilder() as ordinary:
        ordinary.add_plot([0, 1, 2], PlotInfo(data=[1, 2, 3]))
        ordinary.finalize().canvas.draw()
        assert ordinary.ax1.yaxis.get_offset_text().get_text() == ""


@pytest.mark.parametrize("scale", [ScaleEnum.LINEAR, ScaleEnum.LOG])
def test_later_series_preserve_scale_formatter_and_locator(scale: ScaleEnum) -> None:
    """系列追加後も明示した軸設定を保持することを確認する。"""
    with GraphBuilder() as builder:
        for side in AxisSide:
            builder.set_yscale(side, scale)
            formatter = FuncFormatter(lambda value, _pos: f"custom {value:g}")
            locator = MultipleLocator(1)
            xformatter = FuncFormatter(lambda value, _pos: f"x {value:g}")
            group = builder.y if side is AxisSide.LEFT else builder.right_y
            group.style(major_formatter=formatter, major_locator=locator)
            builder.x.style(major_formatter=xformatter)
            builder.add_plot([1, 2], PlotInfo(data=[1, 2], axis=side))
            builder.add_plot([1, 2], PlotInfo(data=[2, 3], axis=side, scale=scale))
            builder.finalize()
            axis = builder.get_axis(side)
            assert axis.get_yscale() == scale.value
            assert axis.yaxis.get_major_formatter() is formatter
            assert axis.yaxis.get_major_locator() is locator
            assert builder.ax1.xaxis.get_major_formatter() is xformatter


def test_log_axis_retains_native_mathtext_formatter() -> None:
    """対数軸がMatplotlibの書式と補助目盛を保持することを確認する。"""
    with GraphBuilder() as builder:
        builder.add_plot([1, 2], PlotInfo(data=[1e-8, 1e-2], scale=ScaleEnum.LOG))
        builder.add_plot([1, 2], PlotInfo(data=[1e-7, 1e-1]))
        builder.finalize().canvas.draw()
        assert builder.ax1.get_yscale() == "log"
        assert isinstance(builder.ax1.yaxis.get_major_formatter(), LogFormatterMathtext)
        assert isinstance(builder.ax1.yaxis.get_minor_locator(), LogLocator)


def test_template_formatter_and_minor_locator_settings(tmp_path: Path) -> None:
    """テンプレートの指数書式と補助目盛間隔が反映されることを確認する。"""
    path = tmp_path / "ticks.mplstyle"
    path.write_text(
        "axes.formatter.use_mathtext: False\nxtick.minor.ndivs: 2\n"
        "ytick.minor.ndivs: 4\nxtick.minor.visible: True\nytick.minor.visible: True\n",
        encoding="utf-8",
    )
    with GraphBuilder(style=path) as builder:
        builder.set_xlim(0, 2)
        builder.set_ylim(AxisSide.LEFT, 0, 2)
        builder.x.style(major_locator=MultipleLocator(1))
        builder.y.style(major_locator=MultipleLocator(1))
        builder.finalize().canvas.draw()
        assert not builder.ax1.xaxis.get_major_formatter().get_useMathText()
        assert builder.ax1.xaxis.get_minorticklocs() == pytest.approx([0.5, 1.5])
        assert builder.ax1.yaxis.get_minorticklocs() == pytest.approx(
            [0.25, 0.5, 0.75, 1.25, 1.5, 1.75]
        )


def test_explicit_scale_transition_preserves_custom_tickers() -> None:
    """軸種変更で利用者指定の目盛と書式を失わないことを確認する。"""
    with GraphBuilder() as builder:
        for side in AxisSide:
            axis = builder.get_axis(side)
            major = FuncFormatter(lambda value, _pos: f"major {value:g}")
            minor = FuncFormatter(lambda value, _pos: f"minor {value:g}")
            major_locator = MultipleLocator(1)
            minor_locator = MultipleLocator(0.25)
            group = builder.y if side is AxisSide.LEFT else builder.right_y
            group.style(
                major_formatter=major,
                minor_formatter=minor,
                major_locator=major_locator,
                minor_locator=minor_locator,
            )
            builder.add_plot([1, 2], PlotInfo(data=[1, 2], axis=side, scale=ScaleEnum.LOG))
            assert axis.yaxis.get_major_formatter() is major
            assert axis.yaxis.get_minor_formatter() is minor
            assert axis.yaxis.get_major_locator() is major_locator
            assert axis.yaxis.get_minor_locator() is minor_locator


def test_template_can_disable_minor_ticks(tmp_path: Path) -> None:
    """テンプレートから補助目盛を無効化できることを確認する。"""
    path = tmp_path / "no-minor.mplstyle"
    path.write_text("xtick.minor.visible: False\nytick.minor.visible: False\n", encoding="utf-8")
    with GraphBuilder(style=path) as builder:
        assert len(builder.ax1.xaxis.get_minorticklocs()) == 0
        assert len(builder.ax1.yaxis.get_minorticklocs()) == 0
