"""簡潔な公開APIが既存描画と入力契約を共有することを検証する。"""

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import plotting_tools as pt


@pytest.mark.parametrize("container", [list, np.array, pd.Series])
def test_line_accepts_existing_data_and_returns_editable_artist(
    container: Callable[[list[int]], object],
) -> None:
    x = container([0, 1, 2])
    y = container([1, 3, 2])
    with pt.Plot(style="paper") as plot:
        line = plot.line(x=x, y=y, color="blue", label="sample", linestyle=":", linewidth=3)
        assert line is plot.ax1.lines[0]
        assert line.get_xdata().tolist() == [0, 1, 2]
        assert line.get_ydata().tolist() == [1, 3, 2]
        assert line.get_label() == "sample"
        assert line.get_color() == "blue"
        assert line.get_linestyle() == ":"
        assert line.get_linewidth() == pytest.approx(3)
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


def test_existing_plot_info_keeps_marker_format_strings() -> None:
    with pt.GraphBuilder() as plot:
        plot.add_plot([0, 1], pt.PlotInfo(data=[1, 2], style="o--"))
        assert plot.lines[0].get_marker() == "o"
        assert plot.lines[0].get_linestyle() == "--"
