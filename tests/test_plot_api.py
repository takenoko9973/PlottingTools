"""簡潔な公開APIが既存描画と入力契約を共有することを検証する。"""

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from matplotlib.collections import PathCollection
from matplotlib.lines import Line2D
from matplotlib.markers import MarkerStyle

import plotting_tools as pt


@pytest.mark.parametrize("container", [list, np.array, pd.Series])
def test_line_accepts_existing_data_and_returns_editable_artist(
    container: Callable[[list[int]], object],
) -> None:
    x = container([0, 1, 2])
    y = container([1, 3, 2])
    with pt.Plot(style="paper") as plot:
        line = plot.line(
            x=x,
            y=y,
            color="blue",
            label="sample",
            linestyle=":",
            linewidth=3,
            marker="s",
            markersize=10,
        )
        assert line is plot.ax1.lines[0]
        assert line.get_xdata().tolist() == [0, 1, 2]
        assert line.get_ydata().tolist() == [1, 3, 2]
        assert line.get_label() == "sample"
        assert line.get_color() == "blue"
        assert line.get_linestyle() == ":"
        assert line.get_linewidth() == pytest.approx(3)
        assert line.get_marker() == "s"
        assert line.get_markersize() == pytest.approx(10)
        line.set_alpha(0.5)
        assert line.get_alpha() == pytest.approx(0.5)
        figure = plot.fig
    assert figure.axes == []
    assert plot.lines == []


def test_line_supports_side_and_scale_strings_and_enums() -> None:
    expected_right_series = 2
    with pt.Plot() as plot:
        plot.line([0, 1], [1, 2], side="right", scale="log")
        plot.line([0, 1], [2, 3], side=pt.AxisSide.RIGHT)
        plot.line([0, 1], [3, 4], side=pt.AxisSide.LEFT, scale=pt.ScaleEnum.LINEAR)
        assert plot.get_ax2().get_yscale() == "log"
        assert len(plot.get_ax2().lines) == expected_right_series
        assert len(plot.ax1.lines) == 1
        assert isinstance(plot, pt.GraphBuilder)


def test_line_validation_failure_releases_context_resources() -> None:
    with pytest.raises(ValueError, match="same length"), pt.Plot() as plot:  # noqa: PT012
        plot.line([0, 1], [1, 2])
        plot.line([0, 1], [1])
    assert plot.fig.axes == []
    assert plot.lines == []


@pytest.mark.parametrize(
    ("linestyle", "expected"),
    [
        ("--", "--"),
        ("dashed", "--"),
        ("solid", "-"),
        ("dashdot", "-."),
        ("dotted", ":"),
        ("None", "None"),
    ],
)
def test_line_accepts_native_linestyle_names(linestyle: str, expected: str) -> None:
    with pt.Plot() as plot:
        line = plot.line([0, 1], [1, 2], linestyle=linestyle)
        assert line.get_linestyle() == expected


def test_line_omitted_linestyle_respects_template(tmp_path: Path) -> None:
    template = tmp_path / "line.mplstyle"
    template.write_text("lines.linestyle: --\n", encoding="utf-8")
    with pt.Plot(style=template) as plot:
        default = plot.line([0, 1], [1, 2])
        explicit = plot.line([0, 1], [2, 3], linestyle="solid")
        later = plot.line([0, 1], [3, 4])
        assert default.get_linestyle() == "--"
        assert explicit.get_linestyle() == "-"
        assert later.get_linestyle() == "--"


def test_line_omitted_marker_properties_respect_template(tmp_path: Path) -> None:
    template = tmp_path / "line-marker.mplstyle"
    template.write_text("lines.marker: ^\nlines.markersize: 9\n", encoding="utf-8")
    with pt.Plot(style=template) as plot:
        default = plot.line([0, 1], [1, 2])
        explicit = plot.line([0, 1], [2, 3], marker="d", markersize=4)
        assert default.get_marker() == "^"
        assert default.get_markersize() == pytest.approx(9)
        assert explicit.get_marker() == "d"
        assert explicit.get_markersize() == pytest.approx(4)


def test_existing_plot_info_keeps_marker_format_strings() -> None:
    with pt.GraphBuilder() as plot:
        plot.add_plot([0, 1], pt.PlotInfo(data=[1, 2], style="o--"))
        assert plot.lines[0].get_marker() == "o"
        assert plot.lines[0].get_linestyle() == "--"


def test_scatter_returns_editable_collection_with_data_and_right_scale() -> None:
    with pt.Plot() as plot:
        points = plot.scatter(
            [0, 1],
            [1, 10],
            color="tab:green",
            marker="s",
            s=[16, 64],
            label="points",
            side="right",
            scale="log",
        )
        assert isinstance(points, PathCollection)
        np.testing.assert_array_equal(points.get_offsets(), [[0, 1], [1, 10]])
        assert points.get_sizes().tolist() == [16, 64]
        assert points.get_label() == "points"
        assert points.get_facecolors()[0].tolist() == pytest.approx(
            [0.17254902, 0.62745098, 0.17254902, 1.0]
        )
        marker = MarkerStyle("s")
        expected_path = marker.get_path().transformed(marker.get_transform())
        assert points.get_paths()[0].vertices == pytest.approx(expected_path.vertices)
        assert points in plot.get_ax2().collections
        assert plot.get_ax2().get_yscale() == "log"
        left_points = plot.scatter([0, 1], [2, 3], side=pt.AxisSide.LEFT, scale=pt.ScaleEnum.LINEAR)
        assert left_points in plot.ax1.collections
        assert plot.ax1.get_yscale() == "linear"
        assert plot.lines == []


def test_scatter_defaults_follow_style_and_mixed_legend_keeps_addition_order(
    tmp_path: Path,
) -> None:
    template = tmp_path / "scatter.mplstyle"
    template.write_text(
        "scatter.marker: ^\n"
        "scatter.edgecolors: red\n"
        "lines.markersize: 8\n"
        "axes.prop_cycle: cycler('color', ['tab:purple', 'tab:orange'])\n",
        encoding="utf-8",
    )
    with pt.Plot(style=template) as plot:
        first_line = plot.line([0, 1], [1, 2], label="line first")
        points = plot.scatter([0, 1], [2, 3], label="scatter second")
        last_line = plot.line([0, 1], [3, 4], label="line third", side="right")

        assert isinstance(points, PathCollection)
        assert points.get_sizes().tolist() == [64]
        assert points.get_facecolors()[0].tolist() == pytest.approx(
            [0.58039216, 0.40392157, 0.74117647, 1.0]
        )
        assert points.get_edgecolors()[0].tolist() == pytest.approx([1.0, 0.0, 0.0, 1.0])
        marker = MarkerStyle("^")
        expected_path = marker.get_path().transformed(marker.get_transform())
        assert points.get_paths()[0].vertices == pytest.approx(expected_path.vertices)
        assert isinstance(plot.lines, list)
        assert plot.lines == [first_line, last_line]
        assert all(isinstance(line, Line2D) for line in plot.lines)
        assert plot.labels == ["line first", "scatter second", "line third"]

        legend = plot.create_legend()
        assert legend is not None
        assert [text.get_text() for text in legend.get_texts()] == [
            "line first",
            "scatter second",
            "line third",
        ]
        assert isinstance(legend.legend_handles[0], Line2D)
        assert isinstance(legend.legend_handles[1], PathCollection)
        assert isinstance(legend.legend_handles[2], Line2D)
        legend.set_loc("center left")
        assert plot.finalize().axes
        assert plot.ax1.get_legend() is legend


@pytest.mark.parametrize(
    ("x", "y", "message"),
    [
        ([[0, 1]], [1, 2], "x_data must be one-dimensional"),
        ([0, 1], [[1, 2]], "plot_info.data must be one-dimensional"),
        ([0, 1], [1], "same length"),
        (pd.DataFrame({"x": [0, 1]}), [1, 2], "x_data must be one-dimensional"),
    ],
)
def test_scatter_rejects_data_outside_existing_plot_contract(
    x: object, y: object, message: str
) -> None:
    with pt.Plot() as plot, pytest.raises(ValueError, match=message):
        plot.scatter(x, y)
