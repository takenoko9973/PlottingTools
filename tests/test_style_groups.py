"""グループ別設定の適用先、呼び出し順序、Artistの更新を検証する。"""

from pathlib import Path

import pytest
from matplotlib.text import Text
from matplotlib.ticker import FuncFormatter, MultipleLocator

from plotting_tools import Plot


def test_label_style_preserves_template_location(tmp_path: Path) -> None:
    """左右の軸ラベルがテンプレートの配置と明示文字サイズを維持する。"""
    template = tmp_path / "label-position.mplstyle"
    template.write_text("xaxis.labellocation: right\nyaxis.labellocation: top\n", encoding="utf-8")
    with Plot(style=template) as plot:
        plot.x.style(label_size=11)
        plot.y.style(label_size=12)
        plot.right_y.style(label_size=13)
        plot.set_labels("Time", "Left", "Right")
        assert plot.ax1.xaxis.label.get_position()[0] == pytest.approx(1)
        assert plot.ax1.yaxis.label.get_position()[1] == pytest.approx(1)
        assert plot.get_ax2().yaxis.label.get_position()[1] == pytest.approx(1)
        assert plot.ax1.xaxis.label.get_fontsize() == pytest.approx(11)
        assert plot.ax1.yaxis.label.get_fontsize() == pytest.approx(12)
        assert plot.get_ax2().yaxis.label.get_fontsize() == pytest.approx(13)


@pytest.mark.parametrize("location", ["left", "center", "right"])
def test_title_style_preserves_template_location(tmp_path: Path, location: str) -> None:
    """テンプレートのタイトル位置と呼び出し順序によらず外観を維持する。"""
    template = tmp_path / "title.mplstyle"
    template.write_text(f"axes.titlelocation: {location}\n", encoding="utf-8")
    with Plot(style=template) as plot:
        plot.title.style(font_size=13, color="red")
        plot.set_title("First")
        plot.set_title("Updated")
        plot.finalize().canvas.draw()
        assert plot.ax1.get_title(loc=location) == "Updated"
        rendered_titles = [
            text
            for text in plot.ax1.get_children()
            if isinstance(text, Text) and text.get_text() == "Updated"
        ]
        assert len(rendered_titles) == 1
        assert rendered_titles[0].get_fontsize() == pytest.approx(13)
        assert rendered_titles[0].get_color() == "red"


def test_axis_groups_are_independent_and_right_axis_is_lazy() -> None:
    """各軸を独立して装飾し、右軸は設定時に初めて生成する。"""
    with Plot() as plot:
        right_group = plot.right_y
        assert len(plot.fig.axes) == 1
        plot.x.style(label_size=10, label_color="red", tick_label_size=9)
        plot.y.style(label_size=14, tick_label_size=12)
        assert len(plot.fig.axes) == 1
        right_group.style(label_size=16, tick_label_size=13)
        plot.set_labels("Time", "Left", "Right")
        plot.finalize().canvas.draw()
        for axis, size, tick_size in (
            (plot.ax1.xaxis, 10, 9),
            (plot.ax1.yaxis, 14, 12),
            (plot.get_ax2().yaxis, 16, 13),
        ):
            assert axis.label.get_fontsize() == pytest.approx(size)
            assert all(text.get_fontsize() == tick_size for text in axis.get_ticklabels())
        assert plot.ax1.xaxis.label.get_color() == "red"


def test_omitted_styles_and_instances_preserve_template(tmp_path: Path) -> None:
    """未指定の属性と別インスタンスの設定が変更されない。"""
    template = tmp_path / "groups.mplstyle"
    template.write_text(
        "axes.labelsize: 18\naxes.labelcolor: blue\nxtick.labelsize: 15\n"
        "ytick.labelsize: 16\nxtick.direction: out\nxtick.major.size: 8\n"
        "axes.grid: True\naxes.titlesize: 19\naxes.titlecolor: green\n",
        encoding="utf-8",
    )
    with Plot(style=template) as first, Plot(style=template) as second:
        first.x.style(label_size=11, tick_direction="in", tick_length=6, tick_width=2, grid=False)
        first.title.style(font_size=13)
        first.set_title("First")
        first.set_title("Updated")
        first.set_labels("x", "y")
        assert first.ax1.title.get_text() == "Updated"
        assert first.ax1.title.get_fontsize() == pytest.approx(13)
        assert first.ax1.title.get_color() == "green"
        assert first.ax1.xaxis.label.get_color() == "blue"
        assert first.ax1.get_xticklabels()[0].get_fontsize() == pytest.approx(15)
        assert first.ax1.yaxis.label.get_fontsize() == pytest.approx(18)
        tick = first.ax1.xaxis.get_major_ticks()[0]
        assert tick.get_tickdir() == "in"
        assert tick.tick1line.get_markersize() == pytest.approx(6)
        assert tick.tick1line.get_markeredgewidth() == pytest.approx(2)
        assert not any(line.get_visible() for line in first.ax1.get_xgridlines())
        assert any(line.get_visible() for line in first.ax1.get_ygridlines())
        assert second.ax1.xaxis.label.get_fontsize() == pytest.approx(18)
        assert second.ax1.title.get_fontsize() == pytest.approx(19)
        first.x.style(label_size=12)
        assert first.ax1.xaxis.label.get_fontsize() == pytest.approx(12)


def test_x_group_distinguishes_major_and_minor_tickers() -> None:
    """主目盛と補助目盛の位置・書式を独立して設定する。"""
    with Plot() as plot:
        major = MultipleLocator(2)
        minor = MultipleLocator(0.5)
        major_format = FuncFormatter(lambda value, _pos: f"M{value:g}")
        minor_format = FuncFormatter(lambda value, _pos: f"m{value:g}")
        plot.x.style(
            major_locator=major,
            minor_locator=minor,
            major_formatter=major_format,
            minor_formatter=minor_format,
        )
        assert plot.ax1.xaxis.get_major_locator() is major
        assert plot.ax1.xaxis.get_minor_locator() is minor
        assert plot.ax1.xaxis.get_major_formatter() is major_format
        assert plot.ax1.xaxis.get_minor_formatter() is minor_format


def test_legend_styles_before_and_after_creation_preserve_direct_edits() -> None:
    """生成前設定と生成後の列数・文字サイズ変更が描画結果に反映される。"""
    with Plot() as plot:
        plot.legend.style(loc="upper left", font_size=9, frame=False)
        plot.line([0, 1], [1, 2], label="Line")
        plot.scatter([0, 1], [2, 3], label="Scatter")
        legend = plot.create_legend()
        assert legend is not None
        legend.set_title("Custom title")
        legend.get_title().set_color("purple")
        legend.get_texts()[0].set_color("red")
        legend.get_frame().set_edgecolor("green")
        plot.fig.canvas.draw()
        assert legend.get_texts()[0].get_window_extent().x0 == pytest.approx(
            legend.get_texts()[1].get_window_extent().x0
        )
        plot.legend.style(ncols=2, font_size=14)
        plot.finalize().canvas.draw()
        assert plot.ax1.get_legend() is legend
        texts = legend.get_texts()
        assert [text.get_text() for text in texts] == ["Line", "Scatter"]
        assert all(text.get_fontsize() == 14 for text in texts)
        assert texts[0].get_window_extent().x0 < texts[1].get_window_extent().x0
        assert texts[0].get_window_extent().y0 == pytest.approx(texts[1].get_window_extent().y0)
        assert texts[0].get_color() == "red"
        assert legend.get_title().get_text() == "Custom title"
        assert legend.get_title().get_color() == "purple"
        assert legend.get_frame_on() is False
        plot.legend.style(visible=False)
        plot.finalize()
        assert not legend.get_visible()
        plot.legend.style(visible=True, frame=True, loc="lower right")
        plot.finalize().canvas.draw()
        assert legend.get_visible()
        assert legend.get_frame_on() is True
        assert legend.get_window_extent().x1 < plot.ax1.bbox.x1
        assert legend.get_window_extent().y0 > plot.ax1.bbox.y0
