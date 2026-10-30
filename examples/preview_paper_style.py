"""paper.mplstyleを確認するSVGプレビューを生成する。"""

from pathlib import Path

import numpy as np

from plotting_tools import Plot


def main() -> None:
    """paperスタイルで決定的なサンプルデータを描画し、SVGを保存する。"""
    time = np.linspace(0.0, 10.0, 201)
    signal_a = 1e-6 * np.exp(-time / 8.0) * np.sin(2.0 * np.pi * time / 5.0)
    signal_b = 1e-6 * np.exp(-time / 10.0) * np.cos(2.0 * np.pi * time / 5.0)
    sample_indices = np.arange(0, time.size, 20)
    output_path = Path(__file__).resolve().parent / "output" / "paper_style.svg"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with Plot(style="paper") as plot:
        plot.line(time, signal_a, label="Measurement A")
        plot.line(time, signal_b, label="Measurement B")
        plot.scatter(time[sample_indices], signal_a[sample_indices], label="Samples")
        plot.set_title("Signal response")
        plot.set_labels("Time (s)", "Signal (A)")
        plot.save(output_path)


if __name__ == "__main__":
    main()
