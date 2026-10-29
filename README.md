# PlottingTools

PlottingTools は、研究用グラフを少ないコードで作成する Matplotlib ラッパーです。
X/Y データと必要な属性だけを指定し、共通の外観を `.mplstyle` で管理します。
左右 Y 軸、対数軸、Mathtext、イベント注釈、SVG 保存、headless 描画に対応します。

## Windows の共通 Python 環境

このリポジトリのルートで、共通環境を一度作成してインストールします。
`uv` がインストール済みであることが前提です。

```powershell
$sharedEnv = Join-Path $HOME ".venvs\plotting-tools"
uv venv $sharedEnv --python 3.12
$pythonPath = Join-Path $sharedEnv "Scripts\python.exe"
uv pip install --python $pythonPath .
```

以後は、任意の作業ディレクトリに保存したスクリプトを同じ Python で実行できます。
スクリプトごとの `# /// script` 宣言や環境の作り直しは不要です。

```powershell
$pythonPath = Join-Path $HOME ".venvs\plotting-tools\Scripts\python.exe"
& $pythonPath "E:\Measurements\run\plot_result.py"
```

ソースを変更した後は、リポジトリのルートでインストールのコマンドを再実行します。
PlottingTools は通常の Python ライブラリであり、独自ランチャーや CLI は提供しません。

## 最小の描画と SVG 保存

```python
from plotting_tools import Plot

with Plot(style="paper") as plot:
    plot.line(x=[0, 1, 2], y=[1.0, 2.5, 1.5], color="blue", label="Sample A")
    plot.set_labels("Time (s)", "Voltage (V)")
    plot.save("result.svg")
```

`Plot` は `GraphBuilder` の別名です。両者は同じ描画処理を使います。
`set_labels()` は既存 API を維持しており、系列の凡例ラベル一覧 `plot.labels` と区別します。
`line()` は編集可能な Matplotlib の `Line2D` を返します。

`save(path, **kwargs)` は layout と保存時にもスタイルを適用します。拡張子に応じて PNG、PDF
などの Matplotlib 対応形式も利用でき、`dpi` などの保存引数も渡せます。
context manager は正常終了・例外終了のどちらでも Figure の内容を破棄します。
手動で管理する場合は保存後に `close()` を呼びます。GUI や `pyplot` の起動は不要です。

## 複数系列とデータ形式

Python のリスト、NumPy 配列、Pandas Series / Index をそのまま渡せます。
DataFrame の列を使う場合も、通常の列選択で指定します。

```python
import numpy as np
import pandas as pd
from plotting_tools import Plot

samples = pd.DataFrame({"time": [0, 1, 2], "voltage": [1.0, 2.0, 1.5]})
with Plot() as plot:
    plot.line(samples["time"], samples["voltage"], color="tab:blue", label="Sample A")
    plot.line(np.array([0, 1, 2]), np.array([1.5, 2.5, 2.0]),
              color="tab:red", label="Sample B", linestyle="dashed", linewidth=2.5)
    plot.set_labels("Time (s)", "Voltage (V)")
    plot.save("samples.svg")
```

色を省略すると、Matplotlib の色サイクルを使います。線種・線幅を省略するとテンプレートに従います。
`linestyle` は `"--"` などの記号と `"dashed"` などの Matplotlib の線種名を受け取ります。
X/Y は同じ長さの1次元データとし、読み込みや単位変換は利用側で行います。

## 左右 Y 軸と対数軸

```python
from plotting_tools import Plot

with Plot() as plot:
    plot.line([0, 1, 2], [1.0, 2.0, 1.5], label="Voltage", color="tab:blue")
    plot.line([0, 1, 2], [1e-6, 1e-5, 1e-4], label="Pressure", color="tab:red",
              side="right", scale="log")
    plot.line([0, 1, 2], [2e-6, 2e-5, 2e-4], side="right", linestyle=":")
    plot.set_labels("Time (s)", "Voltage (V)", "Pressure (Pa)")
    plot.save("dual-axis.svg")
```

`side` は `"left"`（既定）/ `"right"` または `AxisSide`、`scale` は `"linear"` / `"log"`
または `ScaleEnum` を受け取ります。スケールを省略すると現在の設定を保持し、新しい軸は線形です。
同じ軸への系列追加で対数軸が線形に戻ることはありません。

## `.mplstyle` と個別の上書き

設定の優先順位は、Matplotlib 標準設定 → 同梱 `paper` → 選択したスタイル → 明示設定です。
既定の `Plot()` は `Plot(style="paper")` と同じです。Matplotlib のスタイル名、外部ファイルの
パス、これらを順番に適用するリストを指定できます。存在しないスタイルはエラーになります。

次の例はテンプレートを作成し、そのグラフだけに適用します。

```python
from pathlib import Path
from plotting_tools import Plot

Path("lab.mplstyle").write_text(
    "font.family: DejaVu Sans\n"
    "font.size: 14\n"
    "axes.labelsize: 16\n"
    "lines.linewidth: 1.5\n"
    "axes.grid: True\n"
    "svg.fonttype: none\n",
    encoding="utf-8",
)
with Plot(style=["paper", "lab.mplstyle"]) as plot:
    plot.line([0, 1, 2], [1, 3, 2], label="Template width")
    plot.line([0, 1, 2], [2, 2, 3], label="Explicit width", linewidth=2.5)
    plot.set_labels("Time (s)", "Voltage (V)")
    plot.save("styled.svg")
```

省略した属性はテンプレートの値を使います。Figure の大きさ・DPI、フォント、軸・目盛、grid、
凡例の外観も Matplotlib の rcParams で設定できます。minor tick の表示・分割数には
`xtick.minor.visible` / `ndivs` と `ytick.minor.visible` / `ndivs` を使います。

スタイルは各描画操作の間だけ有効で、異なるグラフや無関係な Matplotlib コードへ漏れません。
生の Figure / Axes を直接操作するときは通常の Matplotlib の設定規則に従います。
`finalize().savefig(...)` も利用できますが、保存時のテンプレート設定を適用するには `save()` を使います。

`svg.fonttype: none` は通常の文字を SVG のテキストとして保持します。Mathtext やフォント処理により
一部がパスになる場合があり、すべての文字の編集可能性は保証しません。

## 軸範囲・目盛・凡例・高度な編集

```python
from matplotlib.ticker import MultipleLocator
from plotting_tools import AxisSide, LegendStyleConfig, Plot, PlotStyleConfig

config = PlotStyleConfig(legend=LegendStyleConfig(loc="upper left", frameon=False))
with Plot(config) as plot:
    plot.line([0, 1, 2], [1, 2, 1.5], label="Sample")
    plot.set_xlim(0, 3)
    plot.set_ylim(AxisSide.LEFT, 0, 4)
    plot.set_x_locator(MultipleLocator(1))
    plot.set_y_locator(AxisSide.LEFT, MultipleLocator(1))
    plot.set_title(r"Signal $\alpha$")
    plot.set_labels("Time (s)", "Voltage (V)")
    legend = plot.create_legend()
    if legend is not None:
        legend.set_title("Measurement")
    plot.get_axis().axhline(3, color="gray", linestyle=":")
    plot.save("configured.svg")
```

`set_ylim()` は固定範囲を設定します。自動範囲を最低限指定範囲まで広げる場合は
`expand_ylim_to_include(side, ymin, ymax)` を使います。`LegendStyleConfig(visible=False)` で凡例を
非表示にできます。`get_axis(AxisSide.RIGHT)` で右軸、`fig` で Figure にアクセスできます。
`finalize()` は凡例と layout を確定して Figure を返し、明示的に調整済みの凡例を保持します。
layout や保存のエラーはそのまま送出します。

## 科学表記と Mathtext

線形軸の既定は Matplotlib の `ScalarFormatter` です。通常の値域では通常表記を使い、
科学表記が必要な値域では軸全体の共通指数を Mathtext で表示します。対数軸には Matplotlib
標準の Mathtext Formatter を使います。テンプレートの `axes.formatter.use_mathtext: False` も尊重します。

各目盛を個別の科学表記にする場合は、`FuncFormatter` と既存の設定 API を使います。

```python
from functools import partial
from matplotlib.ticker import FuncFormatter
from plotting_tools import AxisSide, Plot, format_sci_mathtext

with Plot() as plot:
    plot.line([0, 1, 2], [1e-8, 2e-8, 3e-8])
    formatter = FuncFormatter(partial(format_sci_mathtext, precision=3))
    plot.set_y_formatter(AxisSide.LEFT, formatter)
    plot.set_labels("Time (s)", "Current (A)")
    plot.save("scientific.svg")
```

X 軸には `set_x_formatter()`、右 Y 軸には `AxisSide.RIGHT` を指定します。major / minor は
`which="major"` / `"minor"` で選択でき、Locator も別々に設定できます。明示した Locator / Formatter は
後の系列追加、`finalize()`、builder によるスケール変更でも保持します。指定した設定が変更後の
スケールに適していることは利用側で確認してください。

`format_sci_mathtext(x, pos=None, *, precision=1)` の `precision` は係数の小数桁数です。
丸めで指数が繰り上がる場合も正規化し、最小 subnormal から最大有限値まで扱います。
ゼロは `0`、非有限値は NaN・符号付き無限大として表示します。`pos` は `FuncFormatter` 用です。
不正な Mathtext ラベルは警告とともに `[Label Error]` に置換します。
`PlotStyleConfig(strict_mathtext=True)` では `ValueError` になります。

## イベント期間・時点の注釈

```python
from plotting_tools import (
    AxisSide, EventDrawer, EventLayoutData, EventPlotConfig, EventPoint, EventSpan,
    Plot, ScaleEnum,
)

x = [0, 1, 2, 3]
voltage = [1.0, 2.0, 1.5, 3.0]
pressure = [1e-6, 2e-6, 1e-5, 2e-5]
with Plot() as plot:
    plot.line(x, voltage, label="Voltage")
    plot.line(x, pressure, side="right", scale="log", label="Pressure")
    plot.set_labels("Time (s)", "Voltage (V)", "Pressure (Pa)")
    plot.set_ylim(AxisSide.RIGHT, 1e-7, 1e-4)
    events = EventPlotConfig(
        colors={"process": "tab:green"},
        spans=[EventSpan(event="process", start=0.5, end=1.5, label="Heating")],
        points=[EventPoint(event="process", time=2, label="Measurement")],
    )
    layout = EventLayoutData(
        x=x, primary_y=voltage, secondary_y=pressure,
        secondary_scale=ScaleEnum.LOG, secondary_ylim=(1e-7, 1e-4),
    )
    EventDrawer(plot, events).draw_events(layout)
    plot.save("events.svg")
```

ラベル配置は系列、凡例、イベント境界との衝突を避ける候補を評価します。描画した軸と同じ
系列・スケール・右軸範囲を `EventLayoutData` に渡してください。イベントラベルの計測と描画は
同じテンプレートのフォントを使います。

## 既存 API と移行点

`GraphBuilder`、`PlotInfo`、各 `*StyleConfig` は引き続き package root から import できます。
`style_config` は第1位置引数、テンプレート選択は keyword-only の `style=` です。

```python
from plotting_tools import GraphBuilder, PlotInfo

with GraphBuilder() as builder:
    builder.add_plot([0, 1, 2], PlotInfo(data=[1, 3, 2], label="Sample", style="--"))
    builder.set_labels("Time (s)", "Voltage (V)")
    builder.save("existing-api.svg")
```

- rcParams 対応の外観設定と `PlotInfo.style` の既定値は `None`（指定なし）になりました。
  明示した値はテンプレートより優先されます。`FigureStyleConfig.size` の明示指定は従来どおりピクセル単位です。
- `PlotInfo.scale` の既定値は `None`（現在の軸スケールを保持）になりました。
- 軸範囲、左右の割り当て、凡例の表示有無・列数、イベント情報は個別の設定・操作として維持しています。
- 旧 `plotting_tools.plot_util` ではなく package root から import してください。

## 開発

```powershell
uv run --locked python -m pytest
uv run --locked python -m ruff check src tests
uv run --locked python -m ruff format --check src tests
uv run --locked python -m ty check
```

データの読み込み・変換、保存先の自動決定、GUI はこのライブラリの対象外です。
