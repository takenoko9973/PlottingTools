"""イベント注釈のsmoke test。"""

import pandas as pd
import pytest

from plotting_tools import (
    EventDrawer,
    EventLayoutData,
    EventPlotConfig,
    EventPoint,
    EventSpan,
    GraphBuilder,
    PlotInfo,
    ScaleEnum,
)


def test_event_drawer_draws_annotations_without_raising() -> None:
    """期間と時点の注釈およびラベルを例外なく追加できることを確認する。"""
    expected_annotation_count = 2
    x_data = pd.Series([0.0, 1.0, 2.0, 3.0])
    main_data = pd.Series([1.0, 2.0, 1.5, 3.0])
    pressure_data = pd.Series([1e-4, 2e-4, 1.5e-4, 3e-4])
    builder = GraphBuilder()
    builder.add_plot(x_data, PlotInfo(data=main_data, label="sample"))
    config = EventPlotConfig(
        colors={"process": "tab:green"},
        spans=[
            EventSpan(
                event="process",
                start=0.5,
                end=1.5,
                label="span",
            ),
        ],
        points=[
            EventPoint(
                event="process",
                time=2.0,
                label="point",
            ),
        ],
    )
    layout_data = EventLayoutData(
        x=x_data,
        primary_y=main_data,
        secondary_y=pressure_data,
        primary_scale=ScaleEnum.LINEAR,
        secondary_scale=ScaleEnum.LOG,
        secondary_ylim=(1e-5, 1e-3),
    )

    EventDrawer(builder, config).draw_events(layout_data)
    figure = builder.finalize()
    figure.canvas.draw()

    assert len(builder.ax1.patches) == 1
    assert len(builder.ax1.texts) == expected_annotation_count


def test_event_span_rejects_reversed_range() -> None:
    """期間イベントの開始位置が終了位置以上の場合に拒否することを確認する。"""
    with pytest.raises(ValueError, match="start must be smaller than end"):
        EventSpan(event="process", start=2.0, end=1.0)


def test_event_layout_rejects_different_lengths() -> None:
    """ラベル配置用系列の長さが一致しない場合に拒否することを確認する。"""
    with pytest.raises(ValueError, match="must have the same length"):
        EventLayoutData(
            x=[0.0, 1.0],
            primary_y=[1.0],
            secondary_y=[1e-4, 2e-4],
            secondary_ylim=(1e-5, 1e-3),
        )
