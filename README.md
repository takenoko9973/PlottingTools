# PlottingTools

PlottingTools は、研究データ描画でよく使う matplotlib の処理を簡潔に扱うための
軽量 wrapper です。`GraphBuilder` を中心に、Figure / Axes の生成からグラフの
仕上げまでを一貫した API で扱えます。

## 主な機能

- `GraphBuilder` による折れ線グラフの作成
- 左右 Y 軸のサポート
- linear / log scale の設定
- 軸ラベル、タイトル、凡例の設定
- 不正な mathtext 風ラベルによる描画エラーの回避
- `EventDrawer` と `EventPlotConfig` によるイベント注釈とラベル配置

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

`EventPlotConfig.spans` で期間、`EventPlotConfig.points` で時点を指定し、
`EventDrawer` を使って既存の `GraphBuilder` に注釈を追加できます。

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
