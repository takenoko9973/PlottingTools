"""GraphBuilderへイベント範囲、時点、衝突回避済みラベルを追加する。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from plotting_tools._label_layout import (
    Bounds,
    LabelItem,
    LabelLayoutEngine,
    LabelPriority,
)
from plotting_tools.event_models import (
    EventLayoutData,
    EventPlotConfig,
    EventPoint,
    EventSpan,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from plotting_tools.graph_builder import GraphBuilder


class EventDrawer:
    """イベントの描画とラベル配置をGraphBuilderへ追加する。"""

    COLOR_EVENT_DEFAULT = "green"
    ALPHA_EVENT_SPAN = 0.1
    STYLE_EVENT_POINT = ":"
    ALPHA_EVENT_POINT = 0.8
    FONTSIZE_EVENT_LABEL = 16

    def __init__(
        self,
        builder: GraphBuilder,
        config: EventPlotConfig,
        time_shift_sec: float = 0.0,
        divisor: float = 1.0,
    ) -> None:
        """描画対象、イベント設定、時間座標の変換条件を保持する。"""
        if divisor == 0:
            msg = "divisor must not be zero"
            raise ValueError(msg)

        self.builder = builder
        self.config = config
        self.time_shift_sec = time_shift_sec
        self.divisor = divisor

    def _shift_time(self, seconds: float) -> float:
        """元の秒座標へシフトと除数を適用して描画座標へ変換する。"""
        return (seconds - self.time_shift_sec) / self.divisor

    def _event_color(self, event: str) -> str:
        """イベント名に対応する色または既定色を返す。"""
        return self.config.colors.get(event, self.COLOR_EVENT_DEFAULT)

    def _draw_spans(self, spans: Sequence[EventSpan]) -> list[LabelItem]:
        """期間イベントを描画し、配置対象ラベルを返す。"""
        labels: list[LabelItem] = []

        for span in spans:
            color = self._event_color(span.event)
            start_x = self._shift_time(span.start)
            end_x = self._shift_time(span.end)

            if end_x <= 0:
                continue

            # 表示開始前から続く期間は、描画領域の開始位置で切り詰める。
            start_x = max(0.0, start_x)
            self.builder.ax1.axvspan(
                start_x,
                end_x,
                color=color,
                alpha=self.ALPHA_EVENT_SPAN,
            )

            if span.label is None:
                continue

            label_x = ((start_x + end_x) / 2.0) + (span.dx / self.divisor)
            labels.append(
                LabelItem(
                    event=span.event,
                    label=span.label,
                    color=color,
                    priority=LabelPriority.SPAN,
                    target_x=label_x,
                    x_bounds=(start_x, end_x),
                    y_hint=span.y,
                )
            )

        return labels

    def _draw_points(self) -> list[LabelItem]:
        """時点イベントを描画し、配置対象ラベルを返す。"""
        labels: list[LabelItem] = []

        for point in self.config.points:
            color = self._event_color(point.event)
            time_x = self._shift_time(point.time)

            if time_x < 0:
                continue

            self.builder.ax1.axvline(
                time_x,
                color=color,
                linestyle=self.STYLE_EVENT_POINT,
                alpha=self.ALPHA_EVENT_POINT,
            )

            if point.label is None:
                continue

            labels.append(
                LabelItem(
                    event=point.event,
                    label=point.label,
                    color=color,
                    priority=LabelPriority.POINT,
                    target_x=time_x + (point.dx / self.divisor),
                    y_hint=point.y,
                )
            )

        return labels

    def _collect_vertical_lines(self, spans: Sequence[EventSpan]) -> list[float]:
        """ラベル配置で避ける時点線と期間境界のX座標を返す。"""
        vertical_lines: list[float] = []

        for point in self.config.points:
            shifted = self._shift_time(point.time)
            if shifted >= 0:
                vertical_lines.append(shifted)

        for span in spans:
            start_x = self._shift_time(span.start)
            end_x = self._shift_time(span.end)

            if end_x <= 0:
                continue

            vertical_lines.extend((max(0.0, start_x), end_x))

        # 同じ境界を重複評価しないため、描画順に影響しない座標集合へまとめる。
        return list(set(vertical_lines))

    def _get_legend_obstacle(self) -> Bounds | None:
        """凡例が占有する領域をラベル配置用の座標系で返す。"""
        if not self.builder.labels or not self.builder.style.legend.visible:
            return None

        existing_legend = self.builder.ax1.get_legend()
        legend = existing_legend or self.builder.create_legend()
        if legend is None:
            msg = "legend could not be created from labeled plot lines"
            raise RuntimeError(msg)

        # window extent確定にはdrawが必要で、Xはdata座標、YはAxes座標へ別々に変換する。
        self.builder.fig.canvas.draw()
        display_bounds = legend.get_window_extent()
        axes_bounds = display_bounds.transformed(self.builder.ax1.transAxes.inverted())
        data_bounds = display_bounds.transformed(self.builder.ax1.transData.inverted())

        if existing_legend is None:
            legend.remove()

        return Bounds(
            left=data_bounds.x0,
            right=data_bounds.x1,
            bottom=axes_bounds.y0,
            top=axes_bounds.y1,
        )

    def _draw_labels(self, labels: list[LabelItem]) -> None:
        """決定済み座標へイベントラベルを描画する。"""
        for item in labels:
            display_label = item.label.replace("\\n", "\n")
            self.builder.add_safe_text(
                item.final_x,
                item.final_y,
                display_label,
                color=item.color,
                fontsize=self.FONTSIZE_EVENT_LABEL,
                ha=item.horizontal_alignment,
                va=item.vertical_alignment,
                transform=self.builder.ax1.get_xaxis_transform(),
            )

    def draw_events(
        self,
        layout_data: EventLayoutData,
        extra_spans: Sequence[EventSpan] | None = None,
    ) -> None:
        """イベントを描画し、系列と重ならない候補位置へラベルを配置する。"""
        spans = [*self.config.spans, *(extra_spans or [])]
        labels = self._draw_spans(spans)
        labels.extend(self._draw_points())

        if not labels:
            return

        initial_obstacles: list[Bounds] = []
        legend_obstacle = self._get_legend_obstacle()
        if legend_obstacle is not None:
            initial_obstacles.append(legend_obstacle)

        engine = LabelLayoutEngine(
            builder=self.builder,
            layout_data=layout_data,
            vertical_lines=self._collect_vertical_lines(spans),
            fontsize=self.FONTSIZE_EVENT_LABEL,
            initial_obstacles=initial_obstacles,
        )
        engine.compute_layout(labels)
        self._draw_labels(labels)


__all__ = [
    "EventDrawer",
    "EventLayoutData",
    "EventPlotConfig",
    "EventPoint",
    "EventSpan",
]
