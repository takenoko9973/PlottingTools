# PlottingTools

PlottingTools は、研究データ描画でよく使う matplotlib の処理を簡潔に扱うための
軽量 wrapper です。`GraphBuilder` を中心に、Figure / Axes の生成からグラフの
仕上げまでを一貫した API で扱えます。

公開 API は用途ごとに次の3グループへ分けています。利用側では内部モジュールではなく、
`plotting_tools` package root から import してください。

| 用途 | 主な API |
| --- | --- |
| 折れ線描画 | `GraphBuilder`, `PlotInfo`, `AxisSide`, `ScaleEnum` |
| 描画スタイル | `PlotStyleConfig` と責務別の `*StyleConfig` |
| イベント注釈 | `EventDrawer`, `EventPlotConfig`, `EventSpan`, `EventPoint`, `EventLayoutData` |

## 主な機能

- `GraphBuilder` による折れ線グラフの作成
- 左右 Y 軸のサポート
- linear / log scale の設定
- 軸ラベル、タイトル、凡例の設定
- 不正な mathtext 風ラベルによる描画エラーの回避
- 型付きイベント設定によるイベント注釈と衝突回避ラベル配置

## インストール

```powershell
uv pip install -e .
```

## 基本的な使い方

```python
import pandas as pd

from plotting_tools import AxisSide, GraphBuilder, PlotInfo, ScaleEnum

df = pd.DataFrame({"x": [0, 1, 2, 3], "y": [1.0, 2.0, 1.5, 3.0]})

with GraphBuilder() as builder:
    builder.set_title("Example")
    builder.set_labels("x", "y")
    builder.add_plot(
        df["x"],
        PlotInfo(
            data=df["y"],
            axis=AxisSide.LEFT,
            label="sample",
            scale=ScaleEnum.LINEAR,
        ),
    )
    builder.finalize().savefig("example.svg")
```

`GraphBuilder` は `pyplot` やグローバルbackendに依存せずFigureを生成します。context managerを
使うと終了時にFigureの内容を破棄するため、batch処理での解放忘れを防げます。context managerを
使わない場合は、保存後に `builder.close()` を呼んでください。

## 描画設定

共通の外観は同梱の `paper.mplstyle` で管理します。`GraphBuilder(style="paper")` が既定です。
`style` には Matplotlib のスタイル名、外部 `.mplstyle` のパス、これらを順に適用するリストを
指定できます。設定の優先順位は Matplotlib 標準設定、`paper`、選択したスタイル、明示設定です。
存在しないファイルやスタイル名はエラーになります。

```python
from plotting_tools import GraphBuilder, PlotInfo

with GraphBuilder(style=["paper", "my_style.mplstyle"]) as builder:
    builder.add_plot([0, 1, 2], PlotInfo(data=[1, 3, 2], label="sample"))
    builder.add_plot([0, 1, 2], PlotInfo(data=[2, 2, 3], linewidth=2.5))
    builder.set_labels("Time (s)", "Voltage (V)")
    builder.save("result.svg")
```

省略した線幅・線種・フォントなどはテンプレートに従います。`PlotInfo.style` の既定値と
rcParams で表現できる `*StyleConfig` の外観設定の既定値は `None`（指定なし）になりました。
Figure の `size` を明示する場合は従来どおりピクセル単位です。軸範囲、凡例の表示有無・列数など、
グラフ固有の設定は引き続き設定クラスで指定します。

`builder.save(path, **kwargs)` は layout と保存時にもグラフのスタイルを有効にします。
SVG のテキスト保持にはテンプレートで `svg.fonttype: none` を指定できます。
Mathtext などの一部文字はパスになる場合があります。他の Matplotlib 保存形式も利用できます。
`finalize()` の Figure や `get_axis()` の Axes も従来どおり利用できますが、それらを直接操作する際は
通常の Matplotlib の設定規則に従います。テンプレートは builder の操作中だけ有効であり、
`with GraphBuilder(...)` のブロック全体でグローバル設定を変更するものではありません。

`PlotStyleConfig` は明示的な上書きとグラフ固有の設定をまとめます。次の例では、フォント、軸範囲、grid、線幅、
目盛方向、凡例を一括して指定しています。

```python
from plotting_tools import (
    AxisStyleConfig,
    GraphBuilder,
    LegendStyleConfig,
    LineStyleConfig,
    PlotStyleConfig,
    TextStyleConfig,
)

style = PlotStyleConfig(
    text=TextStyleConfig(
        font_family="Noto Sans CJK JP",
        title_options={"fontweight": "bold"},
        label_options={"color": "#333333"},
    ),
    axes=AxisStyleConfig(
        xlim=(0, 100),
        left_ylim=(0.05, 2e7),
        grid=True,
        tick_direction="inout",
    ),
    line=LineStyleConfig(width=2.0),
    legend=LegendStyleConfig(loc="upper left", ncols=2, frameon=False),
    strict_mathtext=True,
)
builder = GraphBuilder(style)
```

固定Y軸範囲は `set_ylim(side, ymin, ymax)`、自動範囲を最低限指定範囲まで広げる場合は
`expand_ylim_to_include(side, ymin, ymax)` を使います。locator / formatterは
`set_x_locator()`、`set_y_locator()`、`set_x_formatter()`、`set_y_formatter()` から設定できます。

凡例は `finalize()` 前でも `create_legend()` で生成して調整できます。設定で
`LegendStyleConfig(visible=False)` とすると表示しません。不正なmathtextは標準ではwarningを
出して `[Label Error]` に置換し、`strict_mathtext=True` では `ValueError` を送出します。

`finalize()` は凡例生成や `tight_layout()` の例外をそのまま送出します。

## 科学表記と軸スケール

既定の線形軸は Matplotlib の `ScalarFormatter` により、値域に応じて通常表記と
共通指数付きの Mathtext 表記を使い分けます。対数軸は Matplotlib 標準の Mathtext
Formatter を使います。テンプレートの `axes.formatter.use_mathtext: False` も尊重します。

各目盛を個別の科学表記にしたい場合は、既存の Formatter 設定 API を使えます。

```python
from functools import partial
from matplotlib.ticker import FuncFormatter
from plotting_tools import AxisSide, format_sci_mathtext

formatter = FuncFormatter(partial(format_sci_mathtext, precision=3))
builder.set_y_formatter(AxisSide.LEFT, formatter)
# X軸は set_x_formatter()、右Y軸は AxisSide.RIGHT を指定します。
```

`precision` は係数の小数桁数で、既定は従来どおり1桁です。丸めで指数が繰り上がる場合も
係数を正規化します。ゼロは `0`、非有限値は NaN・符号付き無限大として表示します。
第2位置引数 `pos` は `FuncFormatter` 用に維持しています。

`PlotInfo.scale` の既定値は `None`（現在のスケールを保持）です。新しい軸は線形になります。
系列追加で対数軸が線形へ戻ることはありません。明示した Locator / Formatter は、後の
系列追加、`finalize()`、builder によるスケール変更でも保持します。スケールを変更する場合は、
指定した Locator / Formatter がそのスケールに適したものであることを確認してください。
minor tick の表示と分割数もテンプレートの `xtick.minor.*` / `ytick.minor.*` に従います。

## イベント注釈

期間は `EventSpan`、時点は `EventPoint` で表します。辞書のキーを実行時に解釈せず、
必要な値を生成時に確認できる形です。`EventLayoutData` はラベルが左右の系列を避けるために
必要なデータと軸条件をまとめます。

```python
from plotting_tools import (
    EventDrawer,
    EventLayoutData,
    EventPlotConfig,
    EventPoint,
    EventSpan,
    ScaleEnum,
)

events = EventPlotConfig(
    colors={"process": "tab:green"},
    spans=[
        EventSpan(
            event="process",
            start=0.5,
            end=1.5,
            label="heating",
        ),
    ],
    points=[
        EventPoint(
            event="process",
            time=2.0,
            label="measurement",
        ),
    ],
)
layout_data = EventLayoutData(
    x=df["x"],
    primary_y=df["y"],
    secondary_y=[1e-4, 2e-4, 1.5e-4, 3e-4],
    primary_scale=ScaleEnum.LINEAR,
    secondary_scale=ScaleEnum.LOG,
    secondary_ylim=(1e-5, 1e-3),
)

EventDrawer(builder, events).draw_events(layout_data)
```

## API整理に伴う変更

- `PlotInfo` と `PlotInfo.style` は従来どおり利用できます。
- `EventPlotConfig.spans` / `points` は辞書ではなく `EventSpan` / `EventPoint` を受け取ります。
- `EventDrawer.draw_events()` の系列情報は個別引数ではなく `EventLayoutData` にまとめました。
- `LabelItem`、`LabelLayoutEngine`、`LabelPriority` は内部実装となり、package root からは公開しません。
- `PlotConfig`、`PlotXData`、`PlotYData` は利用者が直接操作するAPIではないため、package root からは公開しません。
- 旧 `plotting_tools.plot_util` は責務別モジュールへ分割しました。公開 API は package root から import してください。

## このパッケージに含めないもの

PlottingTools は描画処理を補助するライブラリです。次の処理は含みません。

- ログファイルの読み込みやデータ形式の変換
- 保存先やファイル名の自動決定
- 特定プロジェクトの列名やファイル構造に依存する処理
- CLI
- GUI

データの読み込み方法や保存ルールは、利用側のプロジェクトで実装してください。

## 開発

```powershell
uv run ruff format .
uv run ruff check .
uv run pytest
uv run ty check
```

テストには `pytest`、lint には `ruff`、型チェックには `ty` を使用します。
