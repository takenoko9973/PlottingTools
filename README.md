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

`PlotStyleConfig` は責務別の設定をまとめます。次の例では、フォント、軸範囲、grid、線幅、
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
