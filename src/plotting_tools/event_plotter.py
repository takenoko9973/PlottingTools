"""イベントの登録、図形の管理、確定時のラベル配置を担当する。"""

from __future__ import annotations

from dataclasses import replace
from math import isfinite
from pathlib import Path
from shlex import split
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any

import matplotlib as mpl
import matplotlib.style as mplstyle
from matplotlib.colors import to_rgba
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

from plotting_tools._label_layout import Bounds, LabelItem, LabelLayoutEngine, LabelPriority
from plotting_tools.event_models import EventPoint, EventSpan

if TYPE_CHECKING:
    from collections.abc import Iterable

    from matplotlib.text import Text

    from plotting_tools.graph_builder import GraphBuilder


def _load_styles(
    styles: list[str | Path],
) -> tuple[list[str | Path | dict[str, Any]], list[tuple[str, str]]]:
    """独自キーだけを取り出し、標準部分の解釈はMatplotlibへ委ねる。"""
    standard_styles: list[str | Path | dict[str, Any]] = []
    event_settings: list[tuple[str, str]] = []
    for style in styles:
        # Matplotlibと同じく文字列の登録名を優先し、明示Pathと区別する。
        if isinstance(style, str) and (style == "default" or style in mplstyle.library):
            standard_styles.append(style)
            continue
        path = Path(style)
        if not path.is_file():
            standard_styles.append(style)
            continue
        standard_lines: list[str] = []
        has_event_settings = False
        for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
            if not line.lstrip().startswith("plotting_tools.events."):
                standard_lines.append(line)
                continue
            key, separator, value = line.partition(":")
            name = key.strip().removeprefix("plotting_tools.events.")
            if name not in {"span_alpha", "point_alpha", "default_color"}:
                msg = f"unknown event style: {key.strip()}"
                raise ValueError(msg)
            # 独自項目の値だけを解析する。引用hexの#と末尾コメントを区別する。
            tokens = split(value, comments=True)
            if not separator or not tokens:
                msg = f"invalid event style: {line.strip()}"
                raise ValueError(msg)
            event_settings.append((name, " ".join(tokens)))
            has_event_settings = True
            # 標準parserの行番号を保ち、独自行を未知キーとして警告させない。
            standard_lines.append("\n")
        if not has_event_settings:
            standard_styles.append(style)
            continue
        # 公開parserはファイルを受け取る。Windowsでも書込handleを閉じてから読む。
        # 成否にかかわらずcontext終了時に一時ファイルを除去する。
        with TemporaryDirectory() as directory:
            standard_path = Path(directory) / "standard.mplstyle"
            standard_path.write_text("".join(standard_lines), encoding="utf-8")
            parameters = mpl.rc_params_from_file(standard_path, use_default_template=False)
            standard_styles.append(dict(parameters.items()))
    return standard_styles, event_settings


class EventGroup:
    """Plot.eventsから操作するイベント群。独立生成用の公開クラスではない。"""

    def __init__(self, builder: GraphBuilder, settings: list[tuple[str, str]]) -> None:
        self._builder = builder
        self._span_alpha = 0.1
        self._point_alpha = 0.8
        self._default_color = "green"
        self._events: list[tuple[EventSpan | EventPoint, Rectangle | Line2D]] = []
        self._texts: list[tuple[Text, EventSpan | EventPoint]] = []
        for name, value in settings:
            if name == "span_alpha":
                self.style(span_alpha=float(value))
            elif name == "point_alpha":
                self.style(point_alpha=float(value))
            else:
                self.style(default_color=value)

    def style(
        self,
        *,
        span_alpha: float | None = None,
        point_alpha: float | None = None,
        default_color: str | None = None,
    ) -> None:
        """指定した共通設定だけを既存・今後のイベントへ適用する。"""
        for name, value in (("span_alpha", span_alpha), ("point_alpha", point_alpha)):
            if value is not None and not 0 <= value <= 1:
                msg = f"{name} must be between 0 and 1"
                raise ValueError(msg)
        if default_color is not None:
            to_rgba(default_color)
            self._default_color = default_color
        if span_alpha is not None:
            self._span_alpha = span_alpha
        if point_alpha is not None:
            self._point_alpha = point_alpha
        for event, artist in self._events:
            artist.set_color(event.color if event.color is not None else self._default_color)
            artist.set_alpha(
                self._span_alpha if isinstance(event, EventSpan) else self._point_alpha
            )
        for text, event in self._texts:
            if text.get_text() != "[Label Error]":
                text.set_color(event.color if event.color is not None else self._default_color)

    def add_span(
        self,
        start: float,
        end: float,
        *,
        label: str | None = None,
        color: str | None = None,
        dx: float = 0.0,
        y: float | None = None,
        time_shift_sec: float = 0.0,
        divisor: float = 1.0,
    ) -> None:
        """期間を登録する。時刻は(seconds-time_shift_sec)/divisorへ変換する。"""
        self.add_events(
            [EventSpan(start, end, label, color, dx, y)],
            time_shift_sec=time_shift_sec,
            divisor=divisor,
        )

    def add_point(
        self,
        time: float,
        *,
        label: str | None = None,
        color: str | None = None,
        dx: float = 0.0,
        y: float | None = None,
        time_shift_sec: float = 0.0,
        divisor: float = 1.0,
    ) -> None:
        """時点を登録する。dxもdivisorで除して描画座標へ変換する。"""
        self.add_events(
            [EventPoint(time, label, color, dx, y)],
            time_shift_sec=time_shift_sec,
            divisor=divisor,
        )

    def add_events(
        self,
        events: Iterable[EventSpan | EventPoint],
        *,
        time_shift_sec: float = 0.0,
        divisor: float = 1.0,
    ) -> None:
        """混在Iterableを登録し、図形を即時追加する。ラベルはfinalizeで配置する。"""
        if divisor == 0:
            msg = "divisor must not be zero"
            raise ValueError(msg)
        with self._builder._style_context():  # noqa: SLF001
            for original in events:
                event = original
                if not isinstance(event, EventSpan | EventPoint):
                    msg = "events must contain EventSpan or EventPoint"
                    raise TypeError(msg)
                label = event.label
                if label is not None:
                    # strictエラーはArtist追加前に検出し、改行は計測・描画で共通にする。
                    label = self._builder._get_safe_text(label.replace("\\n", "\n"))  # noqa: SLF001
                color = event.color if event.color is not None else self._default_color
                to_rgba(color)
                event = replace(event, label=label, dx=event.dx / divisor)
                axis = self._builder.ax1
                if isinstance(event, EventSpan):
                    start, end = sorted(
                        (
                            (event.start - time_shift_sec) / divisor,
                            (event.end - time_shift_sec) / divisor,
                        )
                    )
                    event = replace(event, start=start, end=end)
                    artist = Rectangle(
                        (start, 0),
                        end - start,
                        1,
                        transform=axis.get_xaxis_transform(),
                        color=color,
                        alpha=self._span_alpha,
                    )
                    # add_patch/axvspanはdataLimを更新する。注釈を自動範囲へ含めない。
                    axis.add_artist(artist)
                else:
                    event = replace(event, time=(event.time - time_shift_sec) / divisor)
                    artist = Line2D(
                        [event.time, event.time],
                        [0, 1],
                        transform=axis.get_xaxis_transform(),
                        color=color,
                        alpha=self._point_alpha,
                        linestyle=":",
                    )
                    axis.add_artist(artist)
                self._events.append((event, artist))

    def _clear_labels(self) -> None:
        """前回のTextをlayout測定に含めず、参照も解放する。"""
        for text, _ in self._texts:
            text.remove()
        self._texts.clear()

    def _place_labels(self) -> None:
        """最終Axes geometryで可視ラベルを一括配置する。"""
        axis = self._builder.ax1
        xmin, xmax = sorted(axis.get_xlim())
        to_axes = axis.get_xaxis_transform() - axis.transAxes
        labels: list[LabelItem] = []
        labeled_events: list[EventSpan | EventPoint] = []
        boundaries: list[float] = []
        for event, _ in self._events:
            bounds = None
            if isinstance(event, EventSpan):
                start, end = max(xmin, event.start), min(xmax, event.end)
                if start >= end:
                    continue
                target = (start + end) / 2 + event.dx
                left, right = sorted(to_axes.transform([(start, 0), (end, 0)])[:, 0])
                bounds = (float(left), float(right))
                boundaries.extend(to_axes.transform((x, 0))[0] for x in (event.start, event.end))
                priority = LabelPriority.SPAN
            else:
                if not xmin <= event.time <= xmax:
                    continue
                target = event.time + event.dx
                boundaries.append(to_axes.transform((event.time, 0))[0])
                priority = LabelPriority.POINT
            if event.label is None:
                continue
            target_x = float(to_axes.transform((target, 0))[0])
            if not isfinite(target_x):
                continue
            labels.append(
                LabelItem(
                    label=event.label,
                    color=event.color if event.color is not None else self._default_color,
                    priority=priority,
                    target_x=target_x,
                    x_bounds=bounds,
                    y_hint=event.y,
                )
            )
            labeled_events.append(event)
        if not labels:
            return
        legend = axis.get_legend()
        obstacles = []
        if legend is not None and legend.get_visible():
            box = legend.get_window_extent().transformed(axis.transAxes.inverted())
            obstacles.append(Bounds(box.x0, box.x1, box.y0, box.y1))
        fontsize = float(mpl.rcParams["font.size"])
        engine = LabelLayoutEngine(self._builder, sorted(set(boundaries)), fontsize, obstacles)
        engine.compute_layout(labels)
        for item, event in zip(labels, labeled_events, strict=True):
            text = self._builder.add_safe_text(
                item.final_x,
                item.final_y,
                item.label,
                color=item.color,
                fontsize=fontsize,
                ha=item.horizontal_alignment,
                va=item.vertical_alignment,
                transform=axis.transAxes,
                zorder=3,
            )
            text.set_in_layout(False)
            self._texts.append((text, event))
