"""左右軸・Mathtext・イベントを含むSVGとheadless描画を検証する。"""

from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np

from plotting_tools import (
    AxisSide,
    EventDrawer,
    EventLayoutData,
    EventPlotConfig,
    EventPoint,
    EventSpan,
    Plot,
    ScaleEnum,
)


def test_complete_svg_and_raster_render_preserve_content_and_layout(tmp_path: Path) -> None:
    event_fontsize = 13
    template = tmp_path / "export.mplstyle"
    template.write_text(
        f"font.family: DejaVu Sans\nfont.size: {event_fontsize}\nsvg.fonttype: none\n",
        encoding="utf-8",
    )
    x = np.linspace(0, 10, 51)
    signal = (2 + np.sin(x)) * 1e-3
    pressure = np.geomspace(1e-7, 1e-4, len(x))
    with Plot(style=template) as plot:
        left = plot.line(x, signal, color="tab:blue", label="Signal sample")
        right = plot.line(
            x, pressure, side="right", scale="log", color="tab:red", label="Pressure sample"
        )
        points = plot.scatter(
            x,
            pressure,
            side="right",
            scale="log",
            color="tab:orange",
            marker="o",
            s=12,
            label="Pressure points",
        )
        plot.set_title(r"Experiment $\alpha$")
        plot.set_labels("Time (s)", "Signal (V)", "Pressure (Pa)")
        plot.set_xlim(0, 10)
        plot.set_ylim(AxisSide.LEFT, 0, 4e-3)
        plot.set_ylim(AxisSide.RIGHT, 1e-8, 1e-3)
        config = EventPlotConfig(
            spans=[EventSpan(event="process", start=2, end=4, label="Heating")],
            points=[EventPoint(event="process", time=7, label=r"Measure $t_0$")],
        )
        EventDrawer(plot, config).draw_events(
            EventLayoutData(
                x=x,
                primary_y=signal,
                secondary_y=pressure,
                secondary_scale=ScaleEnum.LOG,
                secondary_ylim=(1e-8, 1e-3),
            )
        )
        output = tmp_path / "representative.svg"
        plot.save(output)
        plot.save(tmp_path / "representative.png")
        plot.fig.canvas.draw()
        legend = plot.ax1.get_legend()
        assert legend is not None
        artists = [
            plot.ax1.title,
            plot.ax1.xaxis.label,
            plot.ax1.yaxis.label,
            plot.get_ax2().yaxis.label,
            *legend.get_texts(),
            *plot.ax1.texts,
        ]
        renderer = plot.fig.canvas.get_renderer()
        for artist in artists:
            bounds = artist.get_window_extent(renderer)
            assert bounds.width > 0
            assert bounds.height > 0
            assert plot.fig.bbox.contains(bounds.x0, bounds.y0)
            assert plot.fig.bbox.contains(bounds.x1, bounds.y1)
        np.testing.assert_array_equal(left.get_xdata(), x)
        np.testing.assert_array_equal(left.get_ydata(), signal)
        np.testing.assert_array_equal(right.get_ydata(), pressure)
        np.testing.assert_array_equal(points.get_offsets(), np.column_stack((x, pressure)))
        assert plot.get_ax2().get_yscale() == "log"
        assert len(plot.ax1.patches) == 1
        assert plot.ax1.texts[0].get_fontsize() == event_fontsize
        assert plot.ax1.texts[0].get_fontfamily() == ["DejaVu Sans"]
        root = ET.parse(output).getroot()  # noqa: S314
        assert root.tag == "{http://www.w3.org/2000/svg}svg"
        texts = "".join(root.itertext())
        for expected in (
            "Time (s)",
            "Pressure (Pa)",
            "Signal sample",
            "Pressure sample",
            "Pressure points",
            "Heating",
        ):
            assert expected in texts
        # Mathtextは文字ごとのtspanになるため、SVGの整形用空白を除いて比較する。
        compact_text = "".join(texts.split())
        assert "Measure" in compact_text
        assert "Experiment" in compact_text
        assert "DejaVu Sans" in output.read_text(encoding="utf-8")
        assert root.findall(".//{http://www.w3.org/2000/svg}path")
        assert (tmp_path / "representative.png").stat().st_size > 0
    assert plot.fig.axes == []
