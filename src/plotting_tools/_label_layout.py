"""イベントラベルの衝突回避レイアウトを内部実装として提供する。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, ClassVar

import numpy as np
from matplotlib.lines import Line2D
from matplotlib.path import Path
from matplotlib.transforms import Bbox

if TYPE_CHECKING:
    from plotting_tools.graph_builder import GraphBuilder


class LabelPriority(IntEnum):
    """数値が大きいラベルほど先に配置する優先度を表す。"""

    POINT = 2
    SPAN = 3


@dataclass
class LabelItem:
    """配置前後のイベントラベル情報を保持する。"""

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
    """Axes相対X/Y座標で表したラベル矩形。"""

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

    # Axes相対Y座標で、上側から下側へ試すラベル位置の候補。
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

    # ラベル幅に対するX移動量の倍率。0を先に試して元イベントとの対応を保つ。
    X_SHIFT_MULTIPLIERS: ClassVar[tuple[float, ...]] = (
        0.0,
        -0.3,
        0.3,
        -0.5,
        0.5,
    )

    # Axes端から確保する余白をラベル幅に対する比率で指定する (単位なし)。
    EDGE_MARGIN_RATIO = 0.05
    # この値未満の総ペナルティ (単位なし) なら、残りの候補探索を打ち切る。
    ACCEPTABLE_PENALTY = 100.0
    # 正規化Y距離がこの値未満なら、データ線に近い候補として扱う (単位なし)。
    NEAR_DATA_THRESHOLD = 0.05
    # 文字幅が極端に小さいときのX移動量の相対評価を避ける下限 (Axes相対X座標)。
    MIN_TEXT_WIDTH = 1e-12
    # イベント線とラベル位置が同一とみなせるX座標差の許容値 (Axes相対X座標)。
    SAME_LINE_TOLERANCE = 1e-6

    # ラベル矩形が重なる場合の大きなペナルティ (単位なし)。
    PENALTY_OVERLAP_LABEL = 10_000.0
    # 別イベントの縦線がラベル矩形を横切る場合のペナルティ (単位なし)。
    PENALTY_OVERLAP_EVENT_LINE = 8_000.0
    # X移動量に比例して加える、衝突回避より小さいペナルティ (単位なし)。
    PENALTY_X_SHIFT = 50.0

    # 左Y軸データ用の重み (単位なし)。重なり、近接、距離の順に優先度を下げて評価する。
    PRIMARY_DATA_WEIGHTS = DataPenaltyWeights(
        overlap=8_000.0,
        near=5_000.0,
        distance=10.0,
    )
    # 右Y軸データ用の重み (単位なし)。左Y軸より相対的に小さい重みで候補を評価する。
    SECONDARY_DATA_WEIGHTS = DataPenaltyWeights(
        overlap=1_000.0,
        near=100.0,
        distance=5.0,
    )

    def __init__(
        self,
        builder: GraphBuilder,
        vertical_lines: list[float],
        fontsize: float,
        initial_obstacles: list[Bounds] | None = None,
    ) -> None:
        """各Artistの最新データを自身の座標変換でAxes相対座標へ写す。"""
        self.builder = builder
        self.axis = builder.ax1
        self.vertical_lines = vertical_lines
        self.fontsize = fontsize
        self.xlim = (0.0, 1.0)
        self.placed_bounds = list(initial_obstacles or [])
        self.series: list[tuple[Path, bool, DataPenaltyWeights]] = []
        for artist in builder._legend_handles:  # noqa: SLF001
            axis = artist.axes
            if axis is None or not artist.get_visible():
                continue
            if isinstance(artist, Line2D):
                path = artist.get_path()
                values = np.asarray(path.vertices).copy()
                transform = artist.get_transform()
                connected = artist.get_linestyle() not in {"None", "", " "}
                if not connected and artist.get_marker() in {"None", "", " "}:
                    continue
            else:
                values = np.ma.filled(artist.get_offsets(), np.nan).copy()
                path = Path(values)
                transform = artist.get_offset_transform()
                connected = False
            # logの非正値を巨大な負座標として線で結ばない。欠損は線分を分断する。
            invalid = ~np.isfinite(values).all(axis=1)
            if axis.get_xscale() == "log":
                invalid |= values[:, 0] <= 0
            if axis.get_yscale() == "log":
                invalid |= values[:, 1] <= 0
            values[invalid] = np.nan
            transformed = (transform - self.axis.transAxes).transform_path(Path(values, path.codes))
            weights = (
                self.PRIMARY_DATA_WEIGHTS if axis is self.axis else self.SECONDARY_DATA_WEIGHTS
            )
            self.series.append((transformed, connected, weights))

    def _measure_text(self, text: str) -> tuple[float, float]:
        """実際の描画文字列を同じフォントで計測し、Axes相対寸法を返す。"""
        artist = self.axis.text(0, 0, text, fontsize=self.fontsize)
        try:
            bounds = artist.get_window_extent().transformed(self.axis.transAxes.inverted())
            return bounds.width, bounds.height
        finally:
            artist.remove()

    def _get_x_candidates(self, item: LabelItem, text_width: float) -> list[float]:
        """ラベルの制限範囲内に収まるX移動候補を返す。"""
        candidates: list[float] = []

        for multiplier in self.X_SHIFT_MULTIPLIERS:
            candidate = item.target_x + (text_width * multiplier)
            if item.x_bounds is not None and not item.x_bounds[0] <= candidate <= item.x_bounds[1]:
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

    def _data_penalty(self, bounds: Bounds) -> float:
        """疎な線分も表示座標で判定し、系列ごとに独立した重みを加える。"""
        box = Bbox.from_extents(bounds.left, bounds.bottom, bounds.right, bounds.top)
        near_box = Bbox.from_extents(
            bounds.left,
            bounds.bottom - self.NEAR_DATA_THRESHOLD,
            bounds.right,
            bounds.top + self.NEAR_DATA_THRESHOLD,
        )
        penalty = 0.0
        for path, connected, weights in self.series:
            values = np.asarray(path.vertices)
            finite = np.isfinite(values).all(axis=1)
            in_window = finite & (values[:, 0] >= bounds.left) & (values[:, 0] <= bounds.right)
            window_y = values[in_window, 1]
            overlaps = np.any((window_y >= bounds.bottom) & (window_y <= bounds.top))
            if overlaps or (connected and path.intersects_bbox(box, filled=False)):
                penalty += weights.overlap
                continue
            near = np.any((window_y >= near_box.y0) & (window_y <= near_box.y1))
            if near or (connected and path.intersects_bbox(near_box, filled=False)):
                penalty += weights.near
                continue
            if window_y.size:
                distances = np.maximum(bounds.bottom - window_y, window_y - bounds.top)
                penalty += max(0.0, 1.0 - float(np.min(distances))) * weights.distance
        return penalty

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

        penalty += self._data_penalty(placement.bounds)

        if abs(text_width) > self.MIN_TEXT_WIDTH:
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

    def _find_best_placement(self, item: LabelItem) -> Placement:
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
        # 最初の探索はX/Y候補が必ず非空なので、少なくとも1つの配置が確定する。
        assert best is not None
        return best.placement

    def compute_layout(self, labels: list[LabelItem]) -> None:
        """優先度順に各ラベルの描画座標を決定する。"""
        to_data = self.axis.transAxes - self.axis.get_xaxis_transform()
        ordered_labels = sorted(
            labels,
            key=lambda item: (-item.priority.value, to_data.transform((item.target_x, 0))[0]),
        )

        for item in ordered_labels:
            placement = self._find_best_placement(item)
            self.placed_bounds.append(placement.bounds)
            item.final_x = placement.x
            item.final_y = placement.y
            item.horizontal_alignment = placement.horizontal_alignment
            item.vertical_alignment = placement.vertical_alignment
