# plotting-tools

`plotting-tools` は、研究データの描画で頻出する matplotlib の処理を
再利用しやすくする軽量 wrapper パッケージです。既存の `plot_util.py` の
系譜を引き継ぎ、Figure/Axes、左右 Y 軸、スケール、凡例などを扱う
`GraphBuilder` を中心にしています。`event_plotter.py` はイベント注釈と
ラベル配置を追加する拡張です。

ログの読み込み、保存先の決定、ファイル名生成、特定の列名を前提とする処理は
含みません。それらは利用側のプロジェクトで実装してください。

## 使用例

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

## 開発

```powershell
uv run ruff format .
uv run ruff check .
uv run ty check
```

lint には `ruff`、型チェックには `ty` を使用します。
