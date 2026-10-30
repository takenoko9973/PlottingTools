"""インチ指定のFigure/Axes寸法と出力時のレイアウトを検証する。"""

from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
import pytest

from plotting_tools import (
    EventDrawer,
    EventLayoutData,
    EventPlotConfig,
    EventPoint,
    Plot,
)


@pytest.mark.parametrize("name", ["fig_size", "axes_size"])
@pytest.mark.parametrize(
    "size",
    [(0, 2), (-1, 2), (1, float("inf")), (float("nan"), 2), (1,), (1, 2, 3), ("a", 2), 3],
)
def test_invalid_inch_sizes(name: str, size: object) -> None:
    """不正なインチ寸法を拒否することを確認する。"""
    with pytest.raises(ValueError, match=name):
        Plot(**{name: size})


def test_mutually_exclusive_sizes() -> None:
    """Figure寸法とAxes寸法の同時指定を拒否することを確認する。"""
    with pytest.raises(ValueError, match=r"fig_size.*axes_size"):
        Plot(fig_size=(4, 3), axes_size=(3, 2))


@pytest.mark.parametrize("dpi", [80, 160])
def test_size_precedence_and_dpi(tmp_path: Path, dpi: int) -> None:
    """寸法指定の優先順位とDPIに依存しないインチ出力を確認する。"""
    template = tmp_path / "size.mplstyle"
    template.write_text(f"figure.figsize: 7, 4\nfigure.dpi: {dpi}\n", encoding="utf-8")
    effective_dpi = dpi
    with Plot(style=template) as plot:
        plot.finalize()
        assert plot.fig.get_size_inches() == pytest.approx((7, 4))
    with Plot(style=template, fig_size=(5, 3)) as plot:
        plot.finalize()
        plot.fig.canvas.draw()
        assert plot.fig.bbox.size / effective_dpi == pytest.approx((5, 3))
        output = tmp_path / "figure.svg"
        plot.save(output)
        root = ET.parse(output).getroot()  # noqa: S314
        assert float(root.attrib["width"].removesuffix("pt")) / 72 == pytest.approx(5)
        assert float(root.attrib["height"].removesuffix("pt")) / 72 == pytest.approx(3)
    with Plot(style=template, axes_size=(3, 2)) as plot:
        plot.finalize()
        plot.fig.canvas.draw()
        assert plot.ax1.bbox.size / effective_dpi == pytest.approx((3, 2))


def test_fixed_axes_decorations_and_repeat_svg(tmp_path: Path) -> None:
    """固定Axes寸法と装飾の包含を繰り返し保存しても保持することを確認する。"""
    with Plot(axes_size=(3, 2)) as plot:
        plot.line([0, 1], [1e7, 2e7], label="Signal")
        plot.line([0, 1], [1e-5, 2e-5], side="right", label="Pressure")
        EventDrawer(
            plot, EventPlotConfig(points=[EventPoint(event="process", time=0.5, label="Measure")])
        ).draw_events(
            EventLayoutData(
                x=[0, 1],
                primary_y=[1e7, 2e7],
                secondary_y=[1e-5, 2e-5],
                secondary_ylim=(0, 3e-5),
            )
        )
        plot.set_labels("Time (s)", "Signal (V)", "Pressure (Pa)")
        plot.set_title("Experiment title")
        legend = plot.create_legend()
        assert legend is not None
        legend.set_loc("center left")
        legend.set_bbox_to_anchor((1.3, 0.5))
        plot.finalize()
        first_size = plot.fig.get_size_inches().copy()
        # 確定後の装飾変更でも、Axesを縮めずFigureを拡張する。
        plot.x.style(label_size=28)
        plot.y.style(label_size=28)
        plot.title.style(font_size=24)
        plot.finalize()
        assert plot.fig.get_size_inches()[1] > first_size[1]
        size = plot.fig.get_size_inches().copy()
        for index in range(3):
            output = tmp_path / f"fixed-{index}.svg"
            plot.save(output)
            plot.fig.canvas.draw()
            assert plot.ax1.bbox.size / plot.fig.dpi == pytest.approx((3, 2))
            assert plot.get_ax2().bbox.bounds == pytest.approx(plot.ax1.bbox.bounds)
            assert plot.fig.get_size_inches() == pytest.approx(size)
            renderer = plot.fig.canvas.get_renderer()
            for artist in (legend, *plot.ax1.texts):
                bounds = artist.get_window_extent(renderer)
                assert plot.fig.bbox.contains(bounds.x0, bounds.y0)
                assert plot.fig.bbox.contains(bounds.x1, bounds.y1)
            for axis in (plot.ax1, plot.get_ax2()):
                bounds = axis.get_tightbbox(renderer)
                assert bounds is not None
                assert plot.fig.bbox.contains(bounds.x0, bounds.y0)
                assert plot.fig.bbox.contains(bounds.x1, bounds.y1)
            root = ET.parse(output).getroot()  # noqa: S314
            assert float(root.attrib["width"].removesuffix("pt")) / 72 == pytest.approx(size[0])
            assert float(root.attrib["height"].removesuffix("pt")) / 72 == pytest.approx(size[1])
            rectangles = root.findall(
                ".//{http://www.w3.org/2000/svg}clipPath/{http://www.w3.org/2000/svg}rect"
            )
            assert rectangles
            for rectangle in rectangles:
                assert float(rectangle.attrib["width"]) / 72 == pytest.approx(3)
                assert float(rectangle.attrib["height"]) / 72 == pytest.approx(2)
        # 外部のtight_layoutも描画時の固定寸法を変更しない。
        with pytest.warns(UserWarning, match="not compatible with tight_layout"):
            plot.fig.tight_layout()
        plot.fig.canvas.draw()
        np.testing.assert_allclose(plot.ax1.bbox.size / plot.fig.dpi, (3, 2))
