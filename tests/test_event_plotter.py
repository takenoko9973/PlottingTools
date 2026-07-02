"""イベント注釈のsmoke test。"""

import pandas as pd

from plotting_tools import EventDrawer, EventPlotConfig, GraphBuilder, PlotInfo


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
            {
                "event": "process",
                "start": 0.5,
                "end": 1.5,
                "label": "span",
            }
        ],
        points=[{"event": "process", "time": 2.0, "label": "point"}],
    )

    EventDrawer(builder, config).draw_events(
        time_s=x_data,
        main_data_s=main_data,
        is_log_main=False,
        pressure_data_s=pressure_data,
        is_log_press=True,
        ylim_press=(1e-5, 1e-3),
    )
    figure = builder.finalize()
    figure.canvas.draw()

    assert len(builder.ax1.patches) == 1
    assert len(builder.ax1.texts) == expected_annotation_count
