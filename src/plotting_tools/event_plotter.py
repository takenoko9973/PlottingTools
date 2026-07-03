"""GraphBuilderへイベント範囲、時点、ラベルを追加する拡張機能。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, Any, ClassVar

import numpy as np

if TYPE_CHECKING:
    import pandas as pd

    from plotting_tools.plot_util import GraphBuilder


@dataclass
class EventPlotConfig:
    """イベントの色、期間、時点を保持する描画設定。"""

    colors: dict[str, str]
    spans: list[dict[str, Any]]
    points: list[dict[str, Any]]


class LabelPriority(IntEnum):
    """ラベルの描画・配置の優先度 (数値が大きいほど優先)"""

    LOG_EVENT = 1
    POINT = 2
    SPAN = 3


@dataclass
class LabelItem:
    """描画するラベルの情報を保持するデータクラス"""

    event: str
    label: str
    color: str
    priority: LabelPriority
    target_x: float
    x_bounds: tuple[float, float] | None = None  # (min_x, max_x) 制限範囲
    y_hint: float | None = None

    # 決定された描画座標・配置情報
    final_x: float = 0.0
    final_y: float = 0.0
    ha: str = "center"
    va: str = "center"


class LabelLayoutEngine:
    """ラベルの最適な配置座標を計算するレイアウトエンジン"""

    # ==========================================================
    # 調整用定数パラメータ群
    # ==========================================================

    # Y軸の探索候補 (0.0=下端, 1.0=上端)。上端、下端、中央から順に探索する
    DEFAULT_Y_CANDIDATES: ClassVar[list[float]] = [
        0.95,
        0.85,
        0.75,
        0.65,
        0.5,
        0.05,
        0.15,
        0.25,
        0.35,
    ]

    # X軸方向のシフト候補 (テキスト幅に対する倍率。0.0はシフトなし)
    X_SHIFT_MULTIPLIERS: ClassVar[list[float]] = [
        0.0,
        -0.3,
        0.3,
        -0.5,
        0.5,
    ]

    # グラフ端の余白係数 (テキスト幅に対する倍率)
    EDGE_MARGIN_RATIO = 0.05

    # 解決したと見なすペナルティの閾値 (他ラベル・データ線との被りがない状態)
    ACCEPTABLE_PENALTY = 100.0

    # 各種ペナルティの重み
    PENALTY_OVERLAP_BOX = 10000.0  # 他のラベルと被る
    PENALTY_OVERLAP_VLINE = 8000.0  # 他のイベントの縦線と被る
    PENALTY_MAIN_DATA_CRITICAL = 8000.0  # メインデータと激しく被る (距離 < 0.1)
    PENALTY_MAIN_DATA_HIGH = 5000.0  # メインデータとやや被る (距離 < 0.2)
    PENALTY_MAIN_DATA_SLOPE = 10.0  # メインデータとの距離に応じた基本ペナルティ
    PENALTY_SUB_DATA_CRITICAL = 1000.0  # サブデータと激しく被る
    PENALTY_SUB_DATA_HIGH = 100.0  # サブデータとやや被る
    PENALTY_SUB_DATA_SLOPE = 5.0  # サブデータとの距離に応じた基本ペナルティ
    PENALTY_X_SHIFT = 50.0  # X軸方向の移動距離ペナルティ (大きいほど動きにくくなる)
    MIN_TEXT_WIDTH = 1e-12

    # ==========================================================

    def __init__(
        self,
        builder: GraphBuilder,
        time_s: pd.Series,
        main_data_s: pd.Series,
        is_log_main: bool,
        pressure_data_s: pd.Series,
        is_log_press: bool,
        ylim_press: tuple[float, float],
        vertical_lines: list[float],
        fontsize: int,
        initial_obstacles: list[dict[str, float]] | None = None,
    ) -> None:
        self.builder = builder
        self.ax = builder.ax1
        self.time_arr = time_s.to_numpy()
        self.main_data_arr = main_data_s.to_numpy()
        self.pressure_data_arr = pressure_data_s.to_numpy()

        self.is_log_main = is_log_main
        self.is_log_press = is_log_press

        self.ylim_press = ylim_press
        self.vertical_lines = vertical_lines
        self.fontsize = fontsize

        self.xlim = self.ax.get_xlim()
        self.ylim_main = self.ax.get_ylim()

        # 凡例などの初期障害物を登録
        self.placed_boxes: list[dict[str, float]] = initial_obstacles or []

    def _get_exact_text_dimensions(self, text: str) -> tuple[float, float]:
        """Matplotlibのレンダラを利用して、LaTeXを含むテキストの正確な描画サイズを計算する"""
        return self.builder.get_safe_text_dimensions(text, self.fontsize)

    def _get_x_shift_candidates(
        self,
        item: LabelItem,
        text_width: float,
    ) -> list[float]:
        """元座標および左右への退避(シフト)候補を生成し、制限範囲内でフィルタリングする"""
        candidates = [item.target_x]

        for mult in self.X_SHIFT_MULTIPLIERS[1:]:
            test_x = item.target_x + (text_width * mult)
            if item.x_bounds and not (item.x_bounds[0] <= test_x <= item.x_bounds[1]):
                continue
            candidates.append(test_x)

        return candidates

    def _adjust_x_bounds(self, x: float, text_width: float) -> tuple[float, str]:
        """X座標がグラフ領域の端をはみ出さないように補正し、水平アライメントを返す"""
        margin = text_width * self.EDGE_MARGIN_RATIO
        if x - text_width / 2 < self.xlim[0]:
            return self.xlim[0] + margin, "left"
        if x + text_width / 2 > self.xlim[1]:
            return self.xlim[1] - margin, "right"
        return x, "center"

    def _get_horizontal_bounds(
        self, test_x: float, text_width: float, ha: str
    ) -> tuple[float, float]:
        """水平アライメントに基づく矩形の左右座標を返す"""
        if ha == "center":
            return test_x - text_width / 2, test_x + text_width / 2
        if ha == "left":
            return test_x, test_x + text_width
        return test_x - text_width, test_x

    def _get_y_bounds(self, ty: float, text_height: float) -> tuple[str, float, float]:
        """Y座標の高さに基づいて、垂直アライメントと矩形の上下座標を返す"""
        if ty > 0.6:  # noqa: PLR2004
            return "top", ty, ty - text_height
        if ty < 0.4:  # noqa: PLR2004
            return "bottom", ty + text_height, ty
        return "center", ty + text_height / 2, ty - text_height / 2

    def _calculate_data_penalty(  # noqa: C901, PLR0911, PLR0912
        self,
        left: float,
        right: float,
        top: float,
        bottom: float,
        data_arr: np.ndarray,
        ylim: tuple[float, float],
        is_log: bool,
        critical_weight: float,
        high_weight: float,
        slope_weight: float,
    ) -> float:
        """X軸の区間内のデータ線と、矩形枠との被りペナルティを計算する"""
        if data_arr.size == 0 or self.time_arr.size == 0:
            return 0.0

        idx_start = np.searchsorted(self.time_arr, left)
        idx_end = np.searchsorted(self.time_arr, right, side="right")

        if idx_start >= len(self.time_arr):
            idx_start = len(self.time_arr) - 1

        if idx_start == idx_end:
            # 指定区間内にデータ点がない場合は、最も近い1点を代表として計算
            idx = (np.abs(self.time_arr - (left + right) / 2.0)).argmin()
            if idx < data_arr.size:
                vals = np.array([data_arr[idx]])
            else:
                return 0.0
        else:
            vals = data_arr[idx_start:idx_end]

        if vals.size == 0:
            return 0.0

        ymin, ymax = ylim
        if is_log:
            valid_mask = (vals > 0) & np.isfinite(vals)
            if not np.any(valid_mask):
                return 0.0
            vals = vals[valid_mask]

            log_ymin = math.log10(ymin) if ymin > 0 else -15
            log_ymax = math.log10(ymax) if ymax > 0 else -14

            if log_ymax <= log_ymin:
                y_rels = np.full_like(vals, 0.5, dtype=float)
            else:
                y_rels = (np.log10(vals) - log_ymin) / (log_ymax - log_ymin)
        else:
            # データの有限な値のみを対象にする
            valid_mask = np.isfinite(vals)
            if not np.any(valid_mask):
                return 0.0
            vals = vals[valid_mask]

            if ymax <= ymin:
                y_rels = np.full_like(vals, 0.5, dtype=float)
            else:
                y_rels = (vals - ymin) / (ymax - ymin)

        # 矩形領域 [bottom, top] と各データポイントとのY方向の最短距離を計算
        dists = np.where(
            (y_rels >= bottom) & (y_rels <= top),
            0.0,
            np.where(y_rels > top, y_rels - top, bottom - y_rels),
        )

        min_dist = np.min(dists)

        if min_dist <= 0.0:
            return critical_weight  # データ線が矩形を完全に横切っている
        if min_dist < 0.05:  # noqa: PLR2004
            return high_weight  # データ線が矩形に極めて近い
        return (1.0 - min_dist) * slope_weight

    def _calculate_penalty(
        self,
        item: LabelItem,
        test_x: float,  # noqa: ARG002
        ty: float,  # noqa: ARG002
        dx: float,
        text_width: float,
        bbox: dict[str, float],
        check_vline: bool,
    ) -> float:
        """指定された座標・矩形におけるペナルティスコアを計算する"""
        penalty = 0.0

        # 1. 既存ラベルとの重なり判定
        for pbox in self.placed_boxes:
            if not (
                bbox["right"] < pbox["left"]
                or bbox["left"] > pbox["right"]
                or bbox["top"] < pbox["bottom"]
                or bbox["bottom"] > pbox["top"]
            ):
                penalty += self.PENALTY_OVERLAP_BOX
                break

        # 2. 縦線(イベントライン)との重なり判定
        # x軸方向にシフトしていなければ考慮しない
        if check_vline:
            for vline_x in self.vertical_lines:
                if bbox["left"] < vline_x < bbox["right"]:
                    if abs(vline_x - item.target_x) < 1e-6 and abs(dx) < 1e-6:  # noqa: PLR2004
                        continue
                    penalty += self.PENALTY_OVERLAP_VLINE

        # 3. メインデータ線 (区間全体) との被り判定
        penalty += self._calculate_data_penalty(
            bbox["left"],
            bbox["right"],
            bbox["top"],
            bbox["bottom"],
            self.main_data_arr,
            self.ylim_main,
            self.is_log_main,
            self.PENALTY_MAIN_DATA_CRITICAL,
            self.PENALTY_MAIN_DATA_HIGH,
            self.PENALTY_MAIN_DATA_SLOPE,
        )

        # 4. サブデータ線 (区間全体) との被り判定
        penalty += self._calculate_data_penalty(
            bbox["left"],
            bbox["right"],
            bbox["top"],
            bbox["bottom"],
            self.pressure_data_arr,
            self.ylim_press,
            self.is_log_press,
            self.PENALTY_SUB_DATA_CRITICAL,
            self.PENALTY_SUB_DATA_HIGH,
            self.PENALTY_SUB_DATA_SLOPE,
        )

        # 5. 元のX座標からの移動距離に対するペナルティ
        if (
            math.isfinite(dx)
            and math.isfinite(text_width)
            and abs(text_width) > self.MIN_TEXT_WIDTH
        ):
            penalty += (abs(dx) / abs(text_width)) * self.PENALTY_X_SHIFT

        return penalty

    def compute_layout(self, labels: list[LabelItem]) -> None:  # noqa: C901
        """ルールに基づき、各ラベルの最適な描画座標を決定する"""
        labels.sort(key=lambda x: (-x.priority.value, x.target_x))

        for item in labels:
            text_width, text_height = self._get_exact_text_dimensions(item.label)
            y_candidates = [item.y_hint] if item.y_hint is not None else self.DEFAULT_Y_CANDIDATES

            best_penalty = float("inf")
            best_pos = None
            solved = False

            # フェーズ1: Y軸のみの移動 (イベントラインとの被りを無視)
            test_x, ha = self._adjust_x_bounds(item.target_x, text_width)
            left, right = self._get_horizontal_bounds(test_x, text_width, ha)

            for ty in y_candidates:
                va, top, bottom = self._get_y_bounds(ty, text_height)
                bbox = {"left": left, "right": right, "bottom": bottom, "top": top}

                penalty = self._calculate_penalty(
                    item, test_x, ty, 0.0, text_width, bbox, check_vline=False
                )

                if penalty < best_penalty:
                    best_penalty = penalty
                    best_pos = (test_x, ty, ha, va, bbox)

                if penalty < self.ACCEPTABLE_PENALTY:
                    solved = True
                    break

            # フェーズ2: Y軸の移動で解決しない場合、X軸の移動を試行
            # イベントラインとの被りも考慮する
            if not solved:
                x_shifts = self._get_x_shift_candidates(item, text_width)
                for test_x_raw in x_shifts:
                    test_x, ha = self._adjust_x_bounds(test_x_raw, text_width)
                    left, right = self._get_horizontal_bounds(test_x, text_width, ha)

                    for ty in y_candidates:
                        va, top, bottom = self._get_y_bounds(ty, text_height)
                        bbox = {
                            "left": left,
                            "right": right,
                            "bottom": bottom,
                            "top": top,
                        }

                        dx = test_x - item.target_x
                        penalty = self._calculate_penalty(
                            item, test_x, ty, dx, text_width, bbox, check_vline=True
                        )

                        if penalty < best_penalty:
                            best_penalty = penalty
                            best_pos = (test_x, ty, ha, va, bbox)

                        if penalty < self.ACCEPTABLE_PENALTY:
                            solved = True
                            break
                    if solved:
                        break

            # フェーズ3: 決定された座標(最良の妥協点)の保存
            if best_pos:
                test_x, ty, ha, va, bbox = best_pos
                self.placed_boxes.append(bbox)
                item.final_x = test_x
                item.final_y = ty
                item.ha = ha
                item.va = va


class EventDrawer:
    """イベントの抽出およびグラフへの描画を担当する共通クラス"""

    COLOR_EVENT_DEFAULT = "green"
    ALPHA_EVENT_SPAN = 0.1
    STYLE_EVENT_POINT = ":"
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

    @staticmethod
    def _optional_float(value: object, default: float = 0.0) -> float:
        """任意値をfloatへ変換し、変換不能なら既定値を返す。"""
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        if not isinstance(value, str):
            return default
        if value == "":
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _optional_float_or_none(value: object) -> float | None:
        """任意値をfloatへ変換し、変換不能ならNoneを返す。"""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if not isinstance(value, str):
            return None
        if value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _extract_span_labels(
        self, extra_spans: list[dict[str, Any]] | None = None
    ) -> list[LabelItem]:
        items = []
        all_spans = self.config.spans + (extra_spans or [])
        ax = self.builder.ax1
        for span in all_spans:
            event = span["event"]
            color = self.config.colors.get(event, self.COLOR_EVENT_DEFAULT)
            start_x = self._shift_time(float(span["start"]))
            end_x = self._shift_time(float(span["end"]))
            if end_x <= 0:
                continue
            start_x = max(0.0, start_x)
            ax.axvspan(start_x, end_x, color=color, alpha=self.ALPHA_EVENT_SPAN)

            if "label" in span:
                dx_scaled = self._optional_float(span.get("dx")) / self.divisor
                items.append(
                    LabelItem(
                        event=event,
                        label=span["label"],
                        color=color,
                        priority=LabelPriority.SPAN,
                        target_x=((start_x + end_x) / 2.0) + dx_scaled,
                        x_bounds=(start_x, end_x),
                        y_hint=self._optional_float_or_none(span.get("y")),
                    )
                )
        return items

    def _extract_point_labels(self) -> list[LabelItem]:
        items = []
        ax = self.builder.ax1
        for pt in self.config.points:
            event = pt["event"]
            color = self.config.colors.get(event, self.COLOR_EVENT_DEFAULT)
            time_x = self._shift_time(float(pt["time"]))
            if time_x < 0:
                continue
            dx_scaled = self._optional_float(pt.get("dx")) / self.divisor
            ax.axvline(time_x, color=color, linestyle=self.STYLE_EVENT_POINT, alpha=0.8)

            if "label" in pt:
                items.append(
                    LabelItem(
                        event=event,
                        label=pt["label"],
                        color=color,
                        priority=LabelPriority.POINT,
                        target_x=time_x + dx_scaled,
                        y_hint=self._optional_float_or_none(pt.get("y")),
                    )
                )
        return items

    def draw_events(
        self,
        time_s: pd.Series,
        main_data_s: pd.Series,
        is_log_main: bool,
        pressure_data_s: pd.Series,
        is_log_press: bool,
        ylim_press: tuple[float, float],
        extra_spans: list[dict[str, Any]] | None = None,
    ) -> None:
        """グラフにイベントとラベルを描画する"""
        ax = self.builder.ax1

        labels_to_draw = self._extract_span_labels(extra_spans) + self._extract_point_labels()

        if not labels_to_draw:
            return

        # 縦線の位置を収集
        vertical_lines = []
        for pt in self.config.points:
            shifted = self._shift_time(float(pt["time"]))
            if shifted >= 0:
                vertical_lines.append(shifted)

        all_spans = self.config.spans + (extra_spans or [])
        for span in all_spans:
            start_x = self._shift_time(float(span["start"]))
            end_x = self._shift_time(float(span["end"]))
            if end_x <= 0:
                continue
            vertical_lines.extend([max(0.0, start_x), end_x])

        vertical_lines = list(set(vertical_lines))

        # 凡例の事前レンダリングと障害物の生成
        initial_obstacles = []
        if self.builder.labels and self.builder.style.legend.visible:
            existing_legend = ax.get_legend()
            leg = existing_legend or self.builder.create_legend()
            if leg is None:
                msg = "legend could not be created from labeled plot lines"
                raise RuntimeError(msg)
            self.builder.fig.canvas.draw()
            bbox_disp = leg.get_window_extent()
            bbox_axes = bbox_disp.transformed(ax.transAxes.inverted())
            bbox_data = bbox_disp.transformed(ax.transData.inverted())
            initial_obstacles.append(
                {
                    "left": bbox_data.x0,
                    "right": bbox_data.x1,
                    "bottom": bbox_axes.y0,
                    "top": bbox_axes.y1,
                }
            )
            if existing_legend is None:
                leg.remove()

        engine = LabelLayoutEngine(
            builder=self.builder,
            time_s=time_s,
            main_data_s=main_data_s,
            is_log_main=is_log_main,
            pressure_data_s=pressure_data_s,
            is_log_press=is_log_press,
            ylim_press=ylim_press,
            vertical_lines=vertical_lines,
            fontsize=self.FONTSIZE_EVENT_LABEL,
            initial_obstacles=initial_obstacles,
        )
        engine.compute_layout(labels_to_draw)

        for item in labels_to_draw:
            raw_label = item.label or ""
            display_label = raw_label.replace("\\n", "\n")
            self.builder.add_safe_text(
                item.final_x,
                item.final_y,
                display_label,
                color=item.color,
                fontsize=self.FONTSIZE_EVENT_LABEL,
                ha=item.ha,
                va=item.va,
                transform=ax.get_xaxis_transform(),
            )
