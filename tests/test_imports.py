"""利用側へ公開するimport経路のsmoke test。"""

import plotting_tools
from plotting_tools import (
    AxisSide,
    EventDrawer,
    EventLayoutData,
    EventPlotConfig,
    EventPoint,
    EventSpan,
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
    assert EventLayoutData
    assert EventPlotConfig
    assert EventPoint
    assert EventSpan


def test_internal_implementation_is_not_exported() -> None:
    """内部モデルとレイアウト実装が公開APIへ混在しないことを確認する。"""
    internal_names = {
        "LabelItem",
        "LabelLayoutEngine",
        "LabelPriority",
        "PlotConfig",
        "PlotXData",
        "PlotYData",
    }

    assert internal_names.isdisjoint(plotting_tools.__all__)
