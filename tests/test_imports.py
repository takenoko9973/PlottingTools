"""利用側へ公開するimport経路のsmoke test。"""

from plotting_tools import (
    AxisSide,
    EventDrawer,
    EventPlotConfig,
    GraphBuilder,
    PlotInfo,
    ScaleEnum,
)


def test_public_plot_api_is_importable() -> None:
    """基本描画APIがpackage rootから参照できることを保証する。"""
    assert GraphBuilder
    assert PlotInfo
    assert AxisSide
    assert ScaleEnum


def test_public_event_api_is_importable() -> None:
    """イベント描画APIがpackage rootから参照できることを保証する。"""
    assert EventDrawer
    assert EventPlotConfig
