"""イベント注釈のsmoke test。"""

from pathlib import Path

import pandas as pd
import pytest

from plotting_tools import (
    AxisSide,
    EventDrawer,
    EventLayoutData,
    EventPlotConfig,
    EventPoint,
    EventSpan,
    FigureStyleConfig,
    GraphBuilder,
    PlotInfo,
    PlotStyleConfig,
    ScaleEnum,
)


def test_event_drawer_draws_annotations_without_raising() -> None:
    """期間と時点の注釈およびラベルを例外なく追加できることを確認する。"""
    expected_annotation_count = 2
    x_data = pd.Series([0.0, 1.0, 2.0, 3.0])
    main_data = pd.Series([1.0, 2.0, 1.5, 3.0])
    pressure_data = pd.Series([1e-4, 2e-4, 1.5e-4, 3e-4])
    builder = GraphBuilder(PlotStyleConfig(figure=FigureStyleConfig(size=(640, 480))))
    builder.add_plot(x_data, PlotInfo(data=main_data, label="sample"))
    builder.add_plot(
        x_data,
        PlotInfo(
            data=pressure_data,
            axis=AxisSide.RIGHT,
            label="pressure",
            scale=ScaleEnum.LOG,
        ),
    )
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
    assert builder.fig.get_size_inches().tolist() == [6.4, 4.8]
    assert builder.ax1.lines[0].get_ydata().tolist() == main_data.tolist()
    assert builder.get_ax2().lines[0].get_ydata().tolist() == pressure_data.tolist()
    assert builder.get_ax2().get_yscale() == "log"


@pytest.mark.parametrize("with_labeled_line", [False, True])
def test_event_drawer_handles_unlabeled_scatter_alone_and_with_a_line(
    with_labeled_line: bool,
) -> None:
    """label未指定の散布図だけでも、混在時でもイベント注釈を配置できる。"""
    x_data = [0.0, 1.0, 2.0, 3.0]
    scatter_data = [1.0, 2.0, 1.5, 3.0]
    builder = GraphBuilder()
    builder.scatter(x_data, scatter_data)
    if with_labeled_line:
        builder.line(x_data, [2.0, 2.5, 2.0, 3.5], label="reference")
    config = EventPlotConfig(points=[EventPoint(event="process", time=2.0, label="measure")])

    EventDrawer(builder, config).draw_events(
        EventLayoutData(
            x=x_data,
            primary_y=scatter_data,
            secondary_y=[1e-4, 2e-4, 1.5e-4, 3e-4],
            secondary_scale=ScaleEnum.LOG,
            secondary_ylim=(1e-5, 1e-3),
        )
    )
    figure = builder.finalize()
    figure.canvas.draw()

    assert len(builder.ax1.collections) == 1
    assert len(builder.ax1.texts) == 1
    legend = builder.ax1.get_legend()
    if with_labeled_line:
        assert legend is not None
        assert [text.get_text() for text in legend.get_texts()] == ["reference"]
    else:
        assert legend is None


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


@pytest.mark.parametrize(
    ("scale", "limits", "value"),
    [(ScaleEnum.LINEAR, (1.0, 0.0), 0.06), (ScaleEnum.LOG, (100.0, 0.01), 10**-1.76)],
)
def test_event_labels_avoid_data_on_inverted_primary_axis(
    tmp_path: Path, scale: ScaleEnum, limits: tuple[float, float], value: float
) -> None:
    """反転した主軸でもデータ線の実際の表示位置を避けて注釈を配置する。"""
    template = tmp_path / "annotation.mplstyle"
    template.write_text("font.family: DejaVu Sans\nfont.size: 12\n", encoding="utf-8")
    style = PlotStyleConfig(figure=FigureStyleConfig(size=(900, 550), dpi=100))
    with GraphBuilder(style, style=template) as builder:
        builder.add_plot([0, 1, 2], PlotInfo(data=[value] * 3, scale=scale))
        builder.ax1.set_ylim(*limits)
        EventDrawer(
            builder, EventPlotConfig(points=[EventPoint(event="process", time=1, label="measure")])
        ).draw_events(
            EventLayoutData(
                x=[0, 1, 2],
                primary_y=[value] * 3,
                secondary_y=[float("nan")] * 3,
                secondary_ylim=(0, 1),
                primary_scale=scale,
            )
        )
        builder.fig.canvas.draw()
        label = builder.ax1.texts[0]
        bounds = label.get_window_extent()
        data_display_y = builder.ax1.transData.transform((1, value))[1]
        assert not bounds.y0 <= data_display_y <= bounds.y1
