"""イベント登録・確定・衝突回避の振る舞いを検証する。"""

from dataclasses import FrozenInstanceError
from pathlib import Path
from xml.etree import ElementTree as ET

import matplotlib as mpl
import numpy as np
import pytest
from matplotlib.colors import to_rgba

from plotting_tools import EventPoint, EventSpan, Plot


def test_registration_defers_labels_and_preserves_autoscale() -> None:
    """イベント先行でも図形のみ追加し、データの自動範囲を拡張しない。"""
    with Plot() as plot:
        plot.events.add_events(
            iter(
                [
                    EventSpan(-100, 100, label="span"),
                    EventPoint(2, label="point"),
                ]
            )
        )
        assert len(plot.ax1.patches) == 1
        assert len(plot.ax1.lines) == 1
        assert not plot.ax1.texts
        plot.line([0, 4], [0, 1])
        assert plot.ax1.get_xlim() == pytest.approx((-0.2, 4.2))
        plot.finalize()
        assert {text.get_text() for text in plot.ax1.texts} == {"span", "point"}


@pytest.mark.parametrize("event_type", [EventSpan, EventPoint])
def test_homogeneous_iterables_and_unlabeled_shapes(
    event_type: type[EventSpan | EventPoint],
) -> None:
    """片方の型だけのgeneratorとラベルなしイベントも登録できる。"""
    events = (
        [EventSpan(1, 2), EventSpan(2, 3)]
        if event_type is EventSpan
        else [EventPoint(1), EventPoint(2)]
    )
    with Plot() as plot:
        plot.events.add_events(event for event in events)
        plot.set_xlim(0, 4)
        plot.finalize()
        assert not plot.ax1.texts
        assert len(plot.ax1.patches) + len(plot.ax1.lines) == 2


def test_invalid_inputs_and_immutable_models() -> None:
    """単体・一括で同じ期間検証を使い、未対応型や除数ゼロを拒否する。"""
    event = EventPoint(1)
    with pytest.raises(FrozenInstanceError):
        event.time = 2  # type: ignore[misc]
    with Plot() as plot:
        for start, end in [(2, 1), (1, 1), (float("nan"), 2)]:
            with pytest.raises(ValueError, match="start must be smaller"):
                EventSpan(start, end)
            with pytest.raises(ValueError, match="start must be smaller"):
                plot.events.add_span(start, end)
        with pytest.raises(TypeError, match="EventSpan or EventPoint"):
            plot.events.add_events([object()])  # type: ignore[list-item]
        with pytest.raises(ValueError, match="divisor"):
            plot.events.add_point(1, divisor=0)
        assert not plot.ax1.lines
        assert not plot.ax1.patches


def test_coordinate_conversion_partial_visibility_and_negative_ranges() -> None:
    """表示範囲確定まで座標を保持し、可視期間中心とdx/yを反映する。"""
    with Plot() as plot:
        plot.events.add_span(-40, 20, label="partial", dx=2, y=0.3, time_shift_sec=0, divisor=2)
        plot.events.add_point(-8, label="point", dx=2, y=0.6, time_shift_sec=2, divisor=2)
        plot.events.add_point(20, label="outside")
        plot.set_xlim(-10, 0)
        plot.finalize()
        labels = {text.get_text(): text for text in plot.ax1.texts}
        assert labels.keys() == {"partial", "point"}
        # 可視区間[-10,0]の中心-5に、元単位のdx/2=1を加える。
        expected_x = plot.ax1.transData.transform((-4, 0))[0]
        for name in labels:
            assert labels[name].get_transform().transform(labels[name].get_position())[
                0
            ] == pytest.approx(expected_x)
        assert labels["partial"].get_position()[1] == pytest.approx(0.3)
        assert labels["point"].get_position()[1] == pytest.approx(0.6)
        plot.set_xlim(10, 30)
        plot.finalize()
        assert [text.get_text() for text in plot.ax1.texts] == ["outside"]


@pytest.mark.parametrize("fixed", [False, True])
def test_repeated_finalize_save_and_later_additions(tmp_path: Path, fixed: bool) -> None:
    """再確定・再保存・追加後も旧Textや図形、寸法を累積しない。"""
    options = {"axes_size": (4, 3)} if fixed else {"fig_size": (6, 4)}
    with Plot(**options) as plot:
        plot.events.add_span(1, 3, label="span")
        plot.line([0, 4], [0, 1])
        plot.finalize()
        previous = plot.ax1.texts[0]
        size = plot.fig.get_size_inches().copy()
        position = previous.get_position()
        for index in range(3):
            plot.save(tmp_path / f"repeat-{index}.svg")
            assert len(plot.ax1.patches) == 1
            assert len(plot.ax1.texts) == 1
            assert previous.axes is None
            assert plot.ax1.texts[0].get_position() == pytest.approx(position)
            assert plot.fig.get_size_inches() == pytest.approx(size)
            if fixed:
                assert plot.ax1.bbox.size / plot.fig.dpi == pytest.approx((4, 3))
        plot.events.add_point(2, label="later")
        plot.scatter([1, 2, 3], [0.95, 0.95, 0.95], side="right")
        plot.finalize()
        assert len(plot.ax1.patches) == 1
        assert len(plot.ax1.texts) == 2
        assert len(plot.ax1.lines) == 2
        first, second = plot.ax1.texts
        assert not first.get_window_extent().overlaps(second.get_window_extent())


@pytest.mark.parametrize("side", ["left", "right"])
@pytest.mark.parametrize("scale", ["linear", "log"])
@pytest.mark.parametrize("inverted", [False, True])
@pytest.mark.parametrize("kind", ["line", "scatter"])
def test_labels_avoid_independent_series(
    side: str,
    scale: str,
    inverted: bool,
    kind: str,
) -> None:
    """左右・log・反転でも各系列固有の非昇順X/Yの表示位置を避ける。"""
    with Plot(fig_size=(8, 5)) as plot:
        plot.events.add_point(1, label="Measurement")
        plot.line([0, 2], [0.1, 0.1])
        values = [10**0.95] * 3 if scale == "log" else [0.95] * 3
        getattr(plot, kind)([2, 0, 1], values, side=side, scale=scale)
        axis = plot.ax1 if side == "left" else plot.get_ax2()
        axis.set_ylim(1, 10) if scale == "log" else axis.set_ylim(0, 1)
        if inverted:
            axis.invert_yaxis()
        plot.finalize()
        bounds = plot.ax1.texts[0].get_window_extent()
        display_y = axis.transData.transform((1, values[0]))[1]
        assert not bounds.y0 <= display_y <= bounds.y1


def test_sparse_segments_and_edited_artists_are_evaluated() -> None:
    """ラベル領域に点がなくても横切る線分を避け、再確定時は編集を読む。"""
    with Plot(fig_size=(8, 5)) as plot:
        line = plot.line([2, 0], [0.95, 0.95])
        plot.ax1.set_ylim(0, 1)
        plot.events.add_point(1, label="Measurement")
        plot.finalize()
        assert plot.ax1.texts[0].get_position()[1] != pytest.approx(0.95)
        line.set_ydata([0.1, 0.1])
        plot.finalize()
        assert plot.ax1.texts[0].get_position()[1] == pytest.approx(0.95)
        scatter = plot.scatter([1], [0.95])
        plot.finalize()
        assert plot.ax1.texts[0].get_position()[1] != pytest.approx(0.95)
        scatter.set_offsets([[1, 0.1]])
        plot.finalize()
        assert plot.ax1.texts[0].get_position()[1] == pytest.approx(0.95)


def test_empty_nonfinite_duplicate_and_invalid_log_data() -> None:
    """空・欠損・重複X・非正log値は安全に扱い、欠損の間を結ばない。"""
    with Plot() as plot:
        plot.line([], [])
        plot.line([0, 1, 1, 2, np.nan], [1, np.nan, 2, 0, np.inf], scale="log")
        plot.scatter([], [], side="right")
        plot.scatter([1, 1, 2], [np.nan, -1, 2], side="right", scale="log")
        plot.set_xlim(0, 2)
        plot.events.add_point(1, label="valid")
        plot.finalize().canvas.draw()
        assert len(plot.ax1.texts) == 1
        assert np.isfinite(plot.ax1.texts[0].get_position()).all()


@pytest.mark.parametrize("visible", [False, True])
def test_legend_and_separately_registered_labels(visible: bool) -> None:
    """確定時の凡例と全イベントをまとめて避け、既存凡例を保持する。"""
    with Plot(fig_size=(8, 5)) as plot:
        plot.events.add_point(1, label="point")
        plot.events.add_span(0.5, 1.5, label="span")
        plot.line([0, 2], [0.5, 0.5], label="First")
        plot.legend.style(visible=visible, loc="upper center")
        plot.scatter([0, 2], [0.4, 0.4], label="Later")
        plot.finalize().canvas.draw()
        point, span = plot.ax1.texts
        assert not point.get_window_extent().overlaps(span.get_window_extent())
        legend = plot.ax1.get_legend()
        if visible:
            assert legend is not None
            assert [text.get_text() for text in legend.get_texts()] == ["First", "Later"]
            for text in plot.ax1.texts:
                assert not text.get_window_extent().overlaps(legend.get_window_extent())
            plot.finalize()
            assert plot.ax1.get_legend() is legend
        else:
            assert legend is None


def test_mathtext_validation_before_drawing_and_multiline() -> None:
    """strict失敗で図形を残さず、通常モードは一度警告して赤い代替を使う。"""
    with Plot(strict_mathtext=True) as plot:
        with pytest.raises(ValueError, match="invalid mathtext"):
            plot.events.add_span(0, 1, label=r"$\frac{bad$")
        assert not plot.ax1.patches
        assert not plot.ax1.texts
    with Plot() as plot:
        with pytest.warns(UserWarning, match="invalid mathtext"):
            plot.events.add_point(0.5, label=r"$\frac{bad$", color="blue")
        plot.events.add_span(0, 1, label=r"Heating\n$T_0$", y=0.4)
        plot.set_xlim(0, 1)
        plot.finalize().canvas.draw()
        invalid, multiline = plot.ax1.texts
        assert invalid.get_text() == "[Label Error]"
        assert invalid.get_color() == "red"
        assert multiline.get_text() == "Heating\n$T_0$"
        plot.events.style(default_color="orange")
        assert invalid.get_color() == "red"


def test_style_priority_updates_and_svg_alpha(tmp_path: Path) -> None:
    """標準styleの重ね合わせとイベント設定、明示色、SVG透明度を確認する。"""
    first = tmp_path / "first.mplstyle"
    second = tmp_path / "second.mplstyle"
    first.write_text(
        "lines.linewidth: 4\nplotting_tools.events.span_alpha: 0.3\n"
        "plotting_tools.events.point_alpha: 0.6\nplotting_tools.events.default_color: blue\n",
        encoding="utf-8",
    )
    second.write_text(
        "lines.linewidth: 5\nplotting_tools.events.span_alpha: 0.5\n", encoding="utf-8"
    )
    before = dict(mpl.rcParams)
    with Plot(style=["default", first, second]) as plot, Plot() as other:
        plot.events.add_span(0, 1, label="common")
        plot.events.add_point(0.5, label="explicit", color="red")
        other.events.add_span(0, 1)
        other.events.add_point(0.5)
        assert other.ax1.patches[0].get_alpha() == pytest.approx(0.1)
        assert other.ax1.lines[0].get_alpha() == pytest.approx(0.8)
        assert other.ax1.lines[0].get_linestyle() == ":"
        assert to_rgba(other.ax1.lines[0].get_color()) == to_rgba("green")
        assert plot.ax1.patches[0].get_alpha() == pytest.approx(0.5)
        assert plot.ax1.lines[0].get_alpha() == pytest.approx(0.6)
        assert plot.line([0, 1], [0, 1]).get_linewidth() == pytest.approx(5)
        plot.set_xlim(0, 1)
        plot.finalize()
        plot.events.style(span_alpha=0.7, point_alpha=0.9, default_color="orange")
        assert plot.ax1.patches[0].get_facecolor() == to_rgba("orange", 0.7)
        assert plot.ax1.lines[0].get_color() == "red"
        assert [text.get_color() for text in plot.ax1.texts] == ["orange", "red"]
        plot.events.add_span(0.2, 0.4)
        assert plot.ax1.patches[1].get_alpha() == pytest.approx(0.7)
        output = tmp_path / "events.svg"
        plot.save(output)
        root = ET.parse(output).getroot()  # noqa: S314
        styles = [node.attrib.get("style", "") for node in root.iter()]
        assert any("opacity: 0.7" in style for style in styles)
        assert any("stroke-opacity: 0.9" in style for style in styles)
    assert dict(mpl.rcParams) == before


@pytest.mark.parametrize("value", [-0.1, 1.1, float("nan"), float("inf")])
@pytest.mark.parametrize("name", ["span_alpha", "point_alpha"])
def test_invalid_alpha(name: str, value: float) -> None:
    """範囲外・非有限の透明度は拒否する。"""
    with Plot() as plot, pytest.raises(ValueError, match="between 0 and 1"):
        plot.events.style(**{name: value})
