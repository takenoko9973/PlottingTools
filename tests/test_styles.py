"""テンプレート優先順位とグラフ単位の適用範囲を検証する。"""

from pathlib import Path
from xml.etree import ElementTree as ET

import matplotlib as mpl
import pytest

from plotting_tools import (
    EventDrawer,
    EventLayoutData,
    EventPlotConfig,
    EventPoint,
    GraphBuilder,
    PlotInfo,
)


@pytest.fixture
def template(tmp_path: Path) -> Path:
    """優先順位と描画設定の検証に使う明示的なテンプレートを返す。"""
    path = tmp_path / "custom.mplstyle"
    path.write_text(
        "figure.figsize: 7, 4\nfigure.dpi: 80\nlines.linewidth: 4\n"
        "lines.linestyle: --\nfont.family: DejaVu Serif\nfont.size: 21\n"
        "axes.labelsize: 23\naxes.titlesize: 25\nytick.labelsize: 19\n"
        "axes.grid: True\nlegend.fontsize: 17\nlegend.frameon: False\n"
        "svg.fonttype: none\n",
        encoding="utf-8",
    )
    return path


def test_template_and_explicit_series_priority(template: Path) -> None:
    """明示した系列設定がテンプレートより優先されることを確認する。"""
    with GraphBuilder(style=template) as builder:
        builder.add_plot([0, 1], PlotInfo(data=[1, 2], label="template"))
        builder.add_plot([0, 1], PlotInfo(data=[2, 3], linewidth=6, style=":"))
        builder.add_plot([0, 1], PlotInfo(data=[3, 4]))
        builder.set_labels("time", "value")
        builder.set_title("title")
        legend = builder.create_legend()
        assert builder.fig.get_size_inches() == pytest.approx((7, 4))
        assert builder.fig.dpi == pytest.approx(80)
        assert [line.get_linewidth() for line in builder.lines] == [4, 6, 4]
        assert [line.get_linestyle() for line in builder.lines] == ["--", ":", "--"]
        assert builder.lines[0].get_xdata().tolist() == [0, 1]
        assert builder.lines[0].get_ydata().tolist() == [1, 2]
        assert builder.ax1.xaxis.label.get_fontsize() == pytest.approx(23)
        assert builder.ax1.title.get_fontsize() == pytest.approx(25)
        assert legend is not None
        assert legend.get_texts()[0].get_fontsize() == pytest.approx(17)
        assert legend.get_frame_on() is False
        assert any(line.get_visible() for line in builder.ax1.get_xgridlines())
    with GraphBuilder(style=template) as builder:
        builder.add_plot([0, 1], PlotInfo(data=[1, 2], linewidth=5))
        assert builder.lines[0].get_linewidth() == pytest.approx(5)


def test_interleaved_graphs_late_axis_and_scoped_save(template: Path, tmp_path: Path) -> None:
    """交互に操作したグラフのスタイル分離と保存後の設定復元を確認する。"""
    before = mpl.rcParams.copy()
    with GraphBuilder(style=template) as first, GraphBuilder(style="default") as second:
        second.add_plot([0, 1], PlotInfo(data=[1, 2]))
        right = first.get_ax2()
        first.add_plot([0, 1], PlotInfo(data=[1, 2], label="sample"))
        first.set_labels("Time", "Value", "Other")
        assert right.yaxis.label.get_fontfamily() == ["DejaVu Serif"]
        assert right.get_yticklabels()[0].get_fontsize() == pytest.approx(19)
        assert second.lines[0].get_linewidth() == mpl.rcParamsDefault["lines.linewidth"]
        output = tmp_path / "styled.svg"
        first.save(output)
        root = ET.parse(output).getroot()  # noqa: S314
        text = "".join(root.itertext())
        assert "Time" in text
        assert "sample" in text
    assert dict(mpl.rcParams) == dict(before)


def test_style_composition_and_missing_style(template: Path, tmp_path: Path) -> None:
    """スタイルの重ね合わせ順と存在しないファイルの拒否を確認する。"""
    override = tmp_path / "override.mplstyle"
    override.write_text("lines.linewidth: 7\n", encoding="utf-8")
    with GraphBuilder(style=["paper", template, override]) as builder:
        builder.add_plot([0, 1], PlotInfo(data=[1, 2]))
        assert builder.lines[0].get_linewidth() == pytest.approx(7)
    with pytest.raises(OSError, match="missing"):
        GraphBuilder(style=tmp_path / "missing.mplstyle")


def test_event_labels_use_template_font_for_measurement_and_drawing(template: Path) -> None:
    """イベントラベルの測定と描画が同じテンプレートフォントを使うことを確認する。"""
    with GraphBuilder(style=template) as builder:
        builder.add_plot([0, 1, 2], PlotInfo(data=[1, 2, 1], label="sample"))
        events = EventPlotConfig(points=[EventPoint(event="event", time=1, label="label")])
        layout = EventLayoutData(
            x=[0, 1, 2], primary_y=[1, 2, 1], secondary_y=[1, 2, 1], secondary_ylim=(0, 3)
        )
        EventDrawer(builder, events).draw_events(layout)
        label = builder.ax1.texts[0]
        assert label.get_fontsize() == pytest.approx(21)
        assert label.get_fontfamily() == ["DejaVu Serif"]
        width, height = builder.get_safe_text_dimensions("label", 21)
        builder.fig.canvas.draw()
        bounds = label.get_window_extent()
        measured = bounds.transformed(builder.ax1.transAxes.inverted())
        assert height == pytest.approx(measured.height)
        assert width > 0
