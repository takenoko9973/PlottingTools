"""イベントラベルの衝突回避レイアウトを内部実装として提供する。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, ClassVar

import numpy as np

from plotting_tools.models import ScaleEnum

if TYPE_CHECKING:
    from plotting_tools.event_models import EventLayoutData
    from plotting_tools.graph_builder import GraphBuilder


class LabelPriority(IntEnum):
    """数値が大きいラベルほど先に配置する優先度を表す。"""

    LOG_EVENT = 1
    POINT = 2
    SPAN = 3


@dataclass
class LabelItem:
    """配置前後のイベントラベル情報を保持する。"""

    event: str
    label: str
    color: str
    priority: LabelPriority
    target_x: float
    x_bounds: tuple[float, float] | None = None
    y_hint: float | None = None

    final_x: float = 0.0
    final_y: float = 0.0
    horizontal_alignment: str = "center"
    vertical_alignment: str = "center"


@dataclass(frozen=True)
class Bounds:
    """データX座標とAxes相対Y座標で表したラベル矩形。"""

    left: float
    right: float
    bottom: float
    top: float

    def overlaps(self, other: Bounds) -> bool:
        """2つの矩形が辺を含めて重なるかを返す。"""
        separated = (
            self.right < other.left
            or self.left > other.right
            or self.top < other.bottom
            or self.bottom > other.top
        )
        return not separated


@dataclass(frozen=True)
class Placement:
    """1つの候補位置と描画時のalignmentを保持する。"""

    x: float
    y: float
    horizontal_alignment: str
    vertical_alignment: str
    bounds: Bounds
    x_shift: float


@dataclass(frozen=True)
class ScoredPlacement:
    """候補位置と衝突ペナルティをまとめる。"""

    placement: Placement
    penalty: float


@dataclass(frozen=True)
class DataPenaltyWeights:
    """データ線との距離に応じて加えるペナルティ重み。"""

    overlap: float
    near: float
    distance: float


class LabelLayoutEngine:
    """ラベルのY移動を優先し、必要な場合だけX移動を試す。"""

    # 候補順が描画結果を決めるため、上側、下側、中央付近の順序を固定する。
    DEFAULT_Y_CANDIDATES: ClassVar[tuple[float, ...]] = (
        0.95,
        0.85,
        0.75,
        0.65,
        0.5,
        0.05,
        0.15,
        0.25,
        0.35,
    )

    # ラベル幅を基準に小さい移動から試し、元イベントとの対応を保つ。
    X_SHIFT_MULTIPLIERS: ClassVar[tuple[float, ...]] = (
        0.0,
        -0.3,
        0.3,
        -0.5,
        0.5,
    )

    EDGE_MARGIN_RATIO = 0.05
    ACCEPTABLE_PENALTY = 100.0
    NEAR_DATA_THRESHOLD = 0.05
    MIN_TEXT_WIDTH = 1e-12
    SAME_LINE_TOLERANCE = 1e-6

    PENALTY_OVERLAP_LABEL = 10_000.0
    PENALTY_OVERLAP_EVENT_LINE = 8_000.0
    PENALTY_X_SHIFT = 50.0

    PRIMARY_DATA_WEIGHTS = DataPenaltyWeights(
        overlap=8_000.0,
        near=5_000.0,
        distance=10.0,
    )
    SECONDARY_DATA_WEIGHTS = DataPenaltyWeights(
        overlap=1_000.0,
        near=100.0,
        distance=5.0,
    )

    # log軸範囲が非正の場合も正規化計算を継続できるよう1 decadeを仮定する。
    LOG_FALLBACK_MIN = -15.0
    LOG_FALLBACK_MAX = -14.0

    def __init__(
        self,
        builder: GraphBuilder,
        layout_data: EventLayoutData,
        vertical_lines: list[float],
        fontsize: int,
        initial_obstacles: list[Bounds] | None = None,
    ) -> None:
        """描画済み系列と探索条件をNumPy配列として保持する。"""
        self.builder = builder
        self.axis = builder.ax1
        self.time_values = np.asarray(layout_data.x)
        self.primary_values = np.asarray(layout_data.primary_y)
        self.secondary_values = np.asarray(layout_data.secondary_y)

        self.primary_is_log = layout_data.primary_scale is ScaleEnum.LOG
        self.secondary_is_log = layout_data.secondary_scale is ScaleEnum.LOG
        self.secondary_ylim = layout_data.secondary_ylim

        self.vertical_lines = vertical_lines
        self.fontsize = fontsize
        self.xlim = self.axis.get_xlim()
        self.primary_ylim = self.axis.get_ylim()
        self.placed_bounds = list(initial_obstacles or [])

    def _measure_text(self, text: str) -> tuple[float, float]:
        """rendererを使ってmathtextを含む文字列の描画寸法を返す。"""
        return self.builder.get_safe_text_dimensions(text, self.fontsize)

    def _get_x_candidates(self, item: LabelItem, text_width: float) -> list[float]:
        """ラベルの制限範囲内に収まるX移動候補を返す。"""
        candidates: list[float] = []

        for multiplier in self.X_SHIFT_MULTIPLIERS:
            candidate = item.target_x + (text_width * multiplier)
            if item.x_bounds is not None:
                xmin, xmax = item.x_bounds
                if not xmin <= candidate <= xmax:
                    continue
            candidates.append(candidate)

        return candidates

    def _fit_x_to_axes(self, x: float, text_width: float) -> tuple[float, str]:
        """ラベルが左右端を越えないX座標と水平alignmentを返す。"""
        margin = text_width * self.EDGE_MARGIN_RATIO

        if x - text_width / 2 < self.xlim[0]:
            return self.xlim[0] + margin, "left"

        if x + text_width / 2 > self.xlim[1]:
            return self.xlim[1] - margin, "right"

        return x, "center"

    @staticmethod
    def _horizontal_bounds(
        x: float,
        text_width: float,
        alignment: str,
    ) -> tuple[float, float]:
        """水平alignmentから矩形の左右座標を求める。"""
        if alignment == "center":
            return x - text_width / 2, x + text_width / 2

        if alignment == "left":
            return x, x + text_width

        return x - text_width, x

    @staticmethod
    def _vertical_bounds(y: float, text_height: float) -> tuple[str, float, float]:
        """Axes内の高さから垂直alignmentと矩形の上下座標を求める。"""
        # 上下40%では端側へ伸びないalignmentを使い、Axes外へのはみ出しを抑える。
        if y > 0.6:  # noqa: PLR2004
            return "top", y, y - text_height

        if y < 0.4:  # noqa: PLR2004
            return "bottom", y + text_height, y

        return "center", y + text_height / 2, y - text_height / 2

    def _create_placement(
        self,
        item: LabelItem,
        raw_x: float,
        y: float,
        text_width: float,
        text_height: float,
        *,
        track_x_shift: bool,
    ) -> Placement:
        """探索用の生座標をAxes内に収まる候補位置へ変換する。"""
        x, horizontal_alignment = self._fit_x_to_axes(raw_x, text_width)
        left, right = self._horizontal_bounds(x, text_width, horizontal_alignment)
        vertical_alignment, top, bottom = self._vertical_bounds(y, text_height)
        x_shift = x - item.target_x if track_x_shift else 0.0

        return Placement(
            x=x,
            y=y,
            horizontal_alignment=horizontal_alignment,
            vertical_alignment=vertical_alignment,
            bounds=Bounds(left=left, right=right, bottom=bottom, top=top),
            x_shift=x_shift,
        )

    def _values_in_horizontal_window(
        self,
        bounds: Bounds,
        data_values: np.ndarray,
    ) -> np.ndarray:
        """ラベルと同じX区間にあるデータ点を返す。"""
        start = int(np.searchsorted(self.time_values, bounds.left))
        end = int(np.searchsorted(self.time_values, bounds.right, side="right"))

        if start >= len(self.time_values):
            start = len(self.time_values) - 1

        if start != end:
            return data_values[start:end]

        # 区間内に点がない場合は、ラベル中心に最も近い1点で距離を評価する。
        center = (bounds.left + bounds.right) / 2.0
        nearest_index = int(np.abs(self.time_values - center).argmin())
        if nearest_index >= data_values.size:
            return np.array([])

        return np.array([data_values[nearest_index]])

    def _normalize_y_values(
        self,
        values: np.ndarray,
        ylim: tuple[float, float],
        *,
        is_log: bool,
    ) -> np.ndarray:
        """データ値をAxes下端0、上端1の相対Y座標へ変換する。"""
        finite_values = values[np.isfinite(values)]
        if not is_log:
            return self._normalize_linear_values(finite_values, ylim)

        positive_values = finite_values[finite_values > 0]
        if positive_values.size == 0:
            return np.array([])

        ymin, ymax = ylim
        log_ymin = math.log10(ymin) if ymin > 0 else self.LOG_FALLBACK_MIN
        log_ymax = math.log10(ymax) if ymax > 0 else self.LOG_FALLBACK_MAX

        if log_ymax <= log_ymin:
            return np.full_like(positive_values, 0.5, dtype=float)

        return (np.log10(positive_values) - log_ymin) / (log_ymax - log_ymin)

    @staticmethod
    def _normalize_linear_values(
        values: np.ndarray,
        ylim: tuple[float, float],
    ) -> np.ndarray:
        """線形軸のデータ値をAxes相対Y座標へ変換する。"""
        if values.size == 0:
            return np.array([])

        ymin, ymax = ylim
        if ymax <= ymin:
            return np.full_like(values, 0.5, dtype=float)

        return (values - ymin) / (ymax - ymin)

    @staticmethod
    def _minimum_vertical_distance(bounds: Bounds, y_values: np.ndarray) -> float:
        """ラベル矩形と正規化済みデータ点の最短Y距離を返す。"""
        distances = np.where(
            (y_values >= bounds.bottom) & (y_values <= bounds.top),
            0.0,
            np.where(
                y_values > bounds.top,
                y_values - bounds.top,
                bounds.bottom - y_values,
            ),
        )
        return float(np.min(distances))

    def _data_penalty(
        self,
        bounds: Bounds,
        data_values: np.ndarray,
        ylim: tuple[float, float],
        *,
        is_log: bool,
        weights: DataPenaltyWeights,
    ) -> float:
        """データ線とラベル矩形の最短距離からペナルティを計算する。"""
        if data_values.size == 0 or self.time_values.size == 0:
            return 0.0

        window_values = self._values_in_horizontal_window(bounds, data_values)
        if window_values.size == 0:
            return 0.0

        normalized_values = self._normalize_y_values(window_values, ylim, is_log=is_log)
        if normalized_values.size == 0:
            return 0.0

        minimum_distance = self._minimum_vertical_distance(bounds, normalized_values)
        if minimum_distance <= 0.0:
            return weights.overlap

        if minimum_distance < self.NEAR_DATA_THRESHOLD:
            return weights.near

        return (1.0 - minimum_distance) * weights.distance

    def _label_overlap_penalty(self, bounds: Bounds) -> float:
        """配置済みラベルと重なる場合のペナルティを返す。"""
        if any(bounds.overlaps(placed) for placed in self.placed_bounds):
            return self.PENALTY_OVERLAP_LABEL

        return 0.0

    def _event_line_penalty(self, item: LabelItem, placement: Placement) -> float:
        """別イベントの縦線がラベルを横切る場合のペナルティを返す。"""
        penalty = 0.0

        for line_x in self.vertical_lines:
            if not placement.bounds.left < line_x < placement.bounds.right:
                continue

            is_own_unshifted_line = (
                abs(line_x - item.target_x) < self.SAME_LINE_TOLERANCE
                and abs(placement.x_shift) < self.SAME_LINE_TOLERANCE
            )
            if not is_own_unshifted_line:
                penalty += self.PENALTY_OVERLAP_EVENT_LINE

        return penalty

    def _placement_penalty(
        self,
        item: LabelItem,
        placement: Placement,
        text_width: float,
        *,
        check_event_lines: bool,
    ) -> float:
        """候補位置の重なり、データ距離、X移動量を1つの値へ集約する。"""
        penalty = self._label_overlap_penalty(placement.bounds)

        if check_event_lines:
            penalty += self._event_line_penalty(item, placement)

        penalty += self._data_penalty(
            placement.bounds,
            self.primary_values,
            self.primary_ylim,
            is_log=self.primary_is_log,
            weights=self.PRIMARY_DATA_WEIGHTS,
        )
        penalty += self._data_penalty(
            placement.bounds,
            self.secondary_values,
            self.secondary_ylim,
            is_log=self.secondary_is_log,
            weights=self.SECONDARY_DATA_WEIGHTS,
        )

        if math.isfinite(placement.x_shift) and abs(text_width) > self.MIN_TEXT_WIDTH:
            relative_shift = abs(placement.x_shift) / abs(text_width)
            penalty += relative_shift * self.PENALTY_X_SHIFT

        return penalty

    def _search(
        self,
        item: LabelItem,
        x_candidates: list[float],
        y_candidates: list[float],
        text_width: float,
        text_height: float,
        previous_best: ScoredPlacement | None,
        *,
        check_event_lines: bool,
        track_x_shift: bool,
    ) -> tuple[ScoredPlacement | None, bool]:
        """候補を順に評価し、最良候補と許容値到達の有無を返す。"""
        best = previous_best

        for raw_x in x_candidates:
            for y in y_candidates:
                placement = self._create_placement(
                    item,
                    raw_x,
                    y,
                    text_width,
                    text_height,
                    track_x_shift=track_x_shift,
                )
                penalty = self._placement_penalty(
                    item,
                    placement,
                    text_width,
                    check_event_lines=check_event_lines,
                )

                if best is None or penalty < best.penalty:
                    best = ScoredPlacement(placement=placement, penalty=penalty)

                if penalty < self.ACCEPTABLE_PENALTY:
                    return best, True

        return best, False

    def _find_best_placement(self, item: LabelItem) -> Placement | None:
        """Y移動を先に試し、未解決の場合のみX移動を含めて探索する。"""
        text_width, text_height = self._measure_text(item.label)
        y_candidates = [item.y_hint] if item.y_hint is not None else list(self.DEFAULT_Y_CANDIDATES)

        best, solved = self._search(
            item,
            [item.target_x],
            y_candidates,
            text_width,
            text_height,
            None,
            check_event_lines=False,
            track_x_shift=False,
        )
        if solved and best is not None:
            return best.placement

        best, _ = self._search(
            item,
            self._get_x_candidates(item, text_width),
            y_candidates,
            text_width,
            text_height,
            best,
            check_event_lines=True,
            track_x_shift=True,
        )
        return best.placement if best is not None else None

    def compute_layout(self, labels: list[LabelItem]) -> None:
        """優先度順に各ラベルの描画座標を決定する。"""
        ordered_labels = sorted(
            labels,
            key=lambda item: (-item.priority.value, item.target_x),
        )

        for item in ordered_labels:
            placement = self._find_best_placement(item)
            if placement is None:
                continue

            self.placed_bounds.append(placement.bounds)
            item.final_x = placement.x
            item.final_y = placement.y
            item.horizontal_alignment = placement.horizontal_alignment
            item.vertical_alignment = placement.vertical_alignment
