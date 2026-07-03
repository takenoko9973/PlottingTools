"""GraphBuilderの基本動作を検証するbehavior test。"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter, MultipleLocator

from plotting_tools import (
    AxisSide,
    AxisStyleConfig,
    FigureStyleConfig,
    GraphBuilder,
    LegendStyleConfig,
    LineStyleConfig,
    PlotInfo,
    PlotStyleConfig,
    ScaleEnum,
    TextStyleConfig,
    format_sci_mathtext,
)


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
    """壊れたmathtextをwarning付きで安全なラベルへ置換することを確認する。"""
    invalid_mathtext = r"$\frac{broken$"
    builder = GraphBuilder()
    with pytest.warns(UserWarning, match="invalid mathtext"):
        builder.set_title(invalid_mathtext)
    with pytest.warns(UserWarning, match="invalid mathtext"):
        builder.set_labels(invalid_mathtext, invalid_mathtext, invalid_mathtext)
    with pytest.warns(UserWarning, match="invalid mathtext"):
        builder.add_plot(
            pd.Series([0.0, 1.0]),
            PlotInfo(data=pd.Series([1.0, 2.0]), label=invalid_mathtext),
        )

    figure = builder.finalize()
    figure.canvas.draw()

    assert builder.ax1.get_title() == "[Label Error]"


def test_graph_builder_applies_font_family_to_all_text() -> None:
    """スタイルAPIのフォント指定が主要なテキスト要素へ反映されることを確認する。"""
    font_family = "DejaVu Serif"
    builder = GraphBuilder(PlotStyleConfig(text=TextStyleConfig(font_family=font_family)))
    builder.set_title("title")
    builder.set_labels("x", "left", "right")
    builder.add_plot(
        pd.Series([0.0, 1.0]),
        PlotInfo(data=pd.Series([1.0, 2.0]), label="sample"),
    )
    annotation = builder.add_safe_text(0.5, 0.5, "annotation")

    builder.finalize().canvas.draw()

    assert builder.ax1.title.get_fontfamily() == [font_family]
    assert builder.ax1.xaxis.label.get_fontfamily() == [font_family]
    assert builder.ax1.yaxis.label.get_fontfamily() == [font_family]
    assert builder.ax2 is not None
    assert builder.ax2.yaxis.label.get_fontfamily() == [font_family]
    assert annotation.get_fontfamily() == [font_family]
    assert all(label.get_fontfamily() == [font_family] for label in builder.ax1.get_xticklabels())
    legend = builder.ax1.get_legend()
    assert legend is not None
    assert all(text.get_fontfamily() == [font_family] for text in legend.get_texts())


@pytest.mark.parametrize(
    ("size", "dpi", "message"),
    [
        ((0, 100), 100, "figure size"),
        ((900, 550), -1, "dpi must be positive"),
    ],
)
def test_figure_style_rejects_non_positive_values(
    size: tuple[int, int], dpi: int, message: str
) -> None:
    """不正なFigure設定を生成時に拒否することを確認する。"""
    with pytest.raises(ValueError, match=message):
        FigureStyleConfig(size=size, dpi=dpi)


def test_set_ylim_sets_strict_limits() -> None:
    """set_ylimが自動範囲によらない固定範囲を設定することを確認する。"""
    builder = GraphBuilder()
    builder.set_ylim(AxisSide.LEFT, 0.05, 2e7)
    builder.add_plot([0, 1], PlotInfo(data=[-10.0, 3e7]))

    builder.finalize()

    assert builder.ax1.get_ylim() == pytest.approx((0.05, 2e7))


def test_expand_ylim_to_include_extends_automatic_limits() -> None:
    """包含範囲APIが自動範囲を狭めずに拡張することを確認する。"""
    builder = GraphBuilder()
    builder.add_plot([0, 1], PlotInfo(data=[1.0, 2.0]))
    builder.expand_ylim_to_include(AxisSide.LEFT, -5.0, 10.0)

    builder.finalize()

    assert builder.ax1.get_ylim() == pytest.approx((-5.0, 10.0))


def test_locator_and_formatter_api() -> None:
    """locator/formatterをAxesへ直接触れず設定できることを確認する。"""
    builder = GraphBuilder()
    x_locator = MultipleLocator(2)
    y_locator = MultipleLocator(5)
    formatter = FuncFormatter(lambda value, _position: f"{value:g}")

    builder.set_x_locator(x_locator)
    builder.set_y_locator(AxisSide.RIGHT, y_locator)
    builder.set_y_formatter(AxisSide.RIGHT, formatter)

    assert builder.ax1.xaxis.get_major_locator() is x_locator
    assert builder.get_axis(AxisSide.RIGHT).yaxis.get_major_locator() is y_locator
    assert builder.get_axis(AxisSide.RIGHT).yaxis.get_major_formatter() is formatter


def test_legend_style_and_early_creation() -> None:
    """凡例をfinalize前に生成でき、設定が反映されることを確認する。"""
    upper_left_location_code = 2
    style = PlotStyleConfig(legend=LegendStyleConfig(loc="upper left", ncols=2, frameon=False))
    builder = GraphBuilder(style)
    builder.add_plot([0, 1], PlotInfo(data=[1.0, 2.0], label="sample"))

    legend = builder.create_legend()
    assert legend is not None
    legend.set_title("custom")
    builder.finalize()

    assert builder.ax1.get_legend() is legend
    assert legend._loc == upper_left_location_code  # noqa: SLF001
    assert legend.get_frame_on() is False
    assert legend.get_title().get_text() == "custom"


def test_legend_can_be_disabled() -> None:
    """設定から凡例を非表示にできることを確認する。"""
    builder = GraphBuilder(PlotStyleConfig(legend=LegendStyleConfig(visible=False)))
    builder.add_plot([0, 1], PlotInfo(data=[1.0, 2.0], label="sample"))

    builder.finalize()

    assert builder.ax1.get_legend() is None


def test_finalize_propagates_layout_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """finalizeがlayout例外を成功扱いにしないことを確認する。"""
    builder = GraphBuilder()

    def raise_layout_error() -> None:
        msg = "layout failed"
        raise RuntimeError(msg)

    monkeypatch.setattr(builder.fig, "tight_layout", raise_layout_error)

    with pytest.raises(RuntimeError, match="layout failed"):
        builder.finalize()


def test_strict_mathtext_raises() -> None:
    """Strict modeでは不正mathtextを即時拒否することを確認する。"""
    builder = GraphBuilder(PlotStyleConfig(strict_mathtext=True))

    with pytest.raises(ValueError, match="invalid mathtext"):
        builder.set_title(r"$\frac{broken$")


def test_style_applies_axis_grid_line_and_title_options() -> None:
    """責務別設定が軸、線、個別テキストへ反映されることを確認する。"""
    style = PlotStyleConfig(
        axes=AxisStyleConfig(grid=True, xlim=(0.0, 2.0), left_ylim=(0.0, 5.0)),
        line=LineStyleConfig(width=3.0),
        text=TextStyleConfig(title_options={"color": "red"}),
    )
    builder = GraphBuilder(style)
    builder.set_title("title")
    builder.add_plot([0, 1], PlotInfo(data=[1.0, 2.0]))

    assert builder.ax1.get_xlim() == pytest.approx((0.0, 2.0))
    assert builder.ax1.get_ylim() == pytest.approx((0.0, 5.0))
    assert builder.lines[0].get_linewidth() == pytest.approx(3.0)
    assert builder.ax1.title.get_color() == "red"
    assert any(line.get_visible() for line in builder.ax1.get_xgridlines())


def test_context_manager_clears_figure() -> None:
    """Context manager終了時にFigure内のAxesを破棄することを確認する。"""
    with GraphBuilder() as builder:
        builder.add_plot([0, 1], PlotInfo(data=[1.0, 2.0]))
        figure = builder.finalize()

    assert figure.axes == []
    assert builder.lines == []
    assert builder.labels == []
