"""GraphBuilderの基本動作を検証するbehavior test。"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure

from plotting_tools import AxisSide, GraphBuilder, PlotInfo, ScaleEnum, format_sci_mathtext


def test_format_sci_mathtext_zero() -> None:
    """ゼロが指数表記にならないことを確認する。"""
    assert format_sci_mathtext(0) == "0"


def test_set_xlim_expands_identical_limits() -> None:
    """同じ上下限を指定しても表示幅が確保されることを確認する。"""
    builder = GraphBuilder()

    builder.set_xlim(1.0, 1.0)
    xmin, xmax = builder.ax1.get_xlim()

    assert xmin < 1.0 < xmax


def test_graph_builder_creates_figure() -> None:
    """単一系列からFigureとLine2Dが生成されることを確認する。"""
    builder = GraphBuilder()
    builder.add_plot(
        pd.Series([0.0, 1.0, 2.0]),
        PlotInfo(data=pd.Series([1.0, 2.0, 1.5]), label="sample"),
    )

    figure = builder.finalize()

    assert isinstance(figure, Figure)
    assert len(builder.ax1.lines) == 1


def test_graph_builder_accepts_numpy_array() -> None:
    """NumPy配列をX/Yデータとして描画できることを確認する。"""
    x = np.array([0, 1, 2, 3])
    y = np.array([1.0, 2.0, 1.5, 3.0])
    builder = GraphBuilder()
    builder.set_labels("x", "y")
    builder.add_plot(x, PlotInfo(data=y))

    figure = builder.finalize()

    assert figure is not None
    assert len(builder.lines) == 1


def test_graph_builder_accepts_python_list() -> None:
    """PythonのlistをX/Yデータとして描画できることを確認する。"""
    x = [0, 1, 2, 3]
    y = [1.0, 2.0, 1.5, 3.0]
    builder = GraphBuilder()
    builder.set_labels("x", "y")
    builder.add_plot(x, PlotInfo(data=y))

    figure = builder.finalize()

    assert figure is not None
    assert len(builder.lines) == 1


def test_add_plot_rejects_two_dimensional_x_data() -> None:
    """2次元のXデータを明示的に拒否することを確認する。"""
    builder = GraphBuilder()

    with pytest.raises(ValueError, match="x_data must be one-dimensional"):
        builder.add_plot(
            np.array([[0, 1], [2, 3]]),
            PlotInfo(data=np.array([1.0, 2.0])),
        )


def test_add_plot_rejects_two_dimensional_y_data() -> None:
    """2次元のYデータを明示的に拒否することを確認する。"""
    builder = GraphBuilder()

    with pytest.raises(ValueError, match=r"plot_info\.data must be one-dimensional"):
        builder.add_plot(
            np.array([0, 1]),
            PlotInfo(data=np.array([[1.0, 2.0], [3.0, 4.0]])),
        )


def test_add_plot_rejects_dataframe_y_data() -> None:
    """DataFrameをYデータとして明示的に拒否することを確認する。"""
    builder = GraphBuilder()
    dataframe = pd.DataFrame({"a": [1.0, 2.0]})

    with pytest.raises(ValueError, match=r"plot_info\.data must be one-dimensional"):
        builder.add_plot(np.array([0, 1]), PlotInfo(data=dataframe))  # type: ignore[arg-type]


def test_add_plot_rejects_different_lengths() -> None:
    """X/Yデータの長さが異なる場合に拒否することを確認する。"""
    builder = GraphBuilder()

    with pytest.raises(ValueError, match="must have the same length"):
        builder.add_plot(
            np.array([0, 1, 2]),
            PlotInfo(data=np.array([1.0, 2.0])),
        )


def test_graph_builder_supports_left_and_right_axes_with_log_scale() -> None:
    """左右Y軸を併用でき、右軸へlog scaleが反映されることを確認する。"""
    expected_axis_count = 2
    x_data = pd.Series([0.0, 1.0, 2.0])
    builder = GraphBuilder()
    builder.add_plot(
        x_data,
        PlotInfo(data=pd.Series([1.0, 2.0, 3.0]), axis=AxisSide.LEFT),
    )
    builder.add_plot(
        x_data,
        PlotInfo(
            data=pd.Series([1e-3, 1e-2, 1e-1]),
            axis=AxisSide.RIGHT,
            scale=ScaleEnum.LOG,
        ),
    )

    figure = builder.finalize()

    assert len(figure.axes) == expected_axis_count
    assert builder.ax2 is not None
    assert builder.ax2.get_yscale() == "log"
    assert len(builder.ax1.lines) == 1
    assert len(builder.ax2.lines) == 1


def test_figure_can_be_saved_as_svg(tmp_path: Path) -> None:
    """完成したFigureを空でないSVGファイルとして保存できることを確認する。"""
    builder = GraphBuilder()
    builder.add_plot(
        pd.Series([0.0, 1.0]),
        PlotInfo(data=pd.Series([1.0, 2.0])),
    )
    output_path = tmp_path / "example.svg"

    builder.finalize().savefig(output_path)

    assert output_path.is_file()
    assert output_path.stat().st_size > 0


def test_invalid_mathtext_does_not_raise() -> None:
    """壊れたmathtextを安全なラベルへ置換して描画できることを確認する。"""
    invalid_mathtext = r"$\frac{broken$"
    builder = GraphBuilder()
    builder.set_title(invalid_mathtext)
    builder.set_labels(invalid_mathtext, invalid_mathtext, invalid_mathtext)
    builder.add_plot(
        pd.Series([0.0, 1.0]),
        PlotInfo(data=pd.Series([1.0, 2.0]), label=invalid_mathtext),
    )

    figure = builder.finalize()
    figure.canvas.draw()

    assert builder.ax1.get_title() == "[Label Error]"
