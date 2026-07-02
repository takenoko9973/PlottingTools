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

builder = GraphBuilder()
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

fig = builder.finalize()
fig.savefig("example.svg")
```

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
