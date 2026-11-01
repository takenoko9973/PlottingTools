# 設定ガイド

共通の外観は `.mplstyle`、グラフごとの調整はグループの `style()`、描画内容や座標系は操作 API で設定します。高度な調整には返された Matplotlib オブジェクトを使います。引数と振る舞いの詳細は[公開仕様書](SPECIFICATION.md)を参照してください。

## 変更したい項目から探す

| 変更したい項目 | 設定先 | 例・単位 |
|---|---|---|
| Figure 全体の大きさ | constructor | `Plot(fig_size=(6, 4))`、inch |
| 描画領域（Axes）の大きさ | constructor | `Plot(axes_size=(5, 3))`、inch。装飾の余白は Figure に追加 |
| 共通の Figure 寸法・解像度 | `.mplstyle` | `figure.figsize: 6, 4`、`figure.dpi: 100` |
| X 軸ラベルの文字サイズ・色 | `plot.x.style()` | `label_size=10, label_color="blue"`、文字サイズは pt |
| 左・右 Y 軸ラベルの文字サイズ | `plot.y.style()` / `plot.right_y.style()` | `label_size=14`、pt |
| X・Y 軸の目盛文字サイズ | 対象軸の `style()` | `tick_label_size=9`、pt。主目盛と補助目盛に適用 |
| 目盛方向 | 対象軸の `style()` | `tick_direction="in"` / `"out"` / `"inout"` |
| 主目盛線の長さ・幅 | 対象軸の `style()` | `tick_length=5, tick_width=1`、pt |
| 主目盛・補助目盛の位置 | 対象軸の `style()` | `major_locator=MultipleLocator(2)` / `minor_locator=MultipleLocator(0.5)` |
| 主目盛・補助目盛の数値書式 | 対象軸の `style()` | `major_formatter=FuncFormatter(...)` / `minor_formatter=...` |
| 対象軸の主目盛グリッドの表示 | 対象軸の `style()` | `grid=True` / `False` |
| グリッドの色・線種・補助目盛側の設定 | `.mplstyle` または Matplotlib | `grid.color`、`grid.linestyle`、`plot.get_axis().grid(..., which="minor")` |
| 線幅・線種 | `line()` / `.mplstyle` | `linewidth=2, linestyle="--"` / `lines.linewidth`、`lines.linestyle` |
| マーカーの形状・大きさ | `line()` / `scatter()` | `marker="o", markersize=5`（pt）/ `marker="s", s=25`（pt²） |
| 共通のマーカー | `.mplstyle` | `lines.marker`、`lines.markersize`（Line の既定値） |
| 凡例の位置・文字サイズ・枠・列数 | `plot.legend.style()` | `loc="upper right", font_size=10, frame=False, ncols=2` |
| 凡例の表示有無 | `plot.legend.style()` | `visible=False` / `True` |
| 凡例のタイトルなど | Matplotlib | `legend = plot.create_legend()` の戻り値を編集 |
| タイトル文字列 | 操作 API | `plot.set_title("Experiment")` |
| タイトルの文字サイズ・色 | `plot.title.style()` | `font_size=12, color="black"` |
| 軸ラベル文字列 | 操作 API | `plot.set_labels("Time (s)", "Signal", "Pressure")` |
| 軸範囲・Y 軸スケール | 操作 API | `set_xlim()`、`set_ylim()`、`expand_ylim_to_include()`、`set_yscale()` |
| 共通の色・フォント | `.mplstyle` | `axes.prop_cycle`、`font.family`、`font.size`、`axes.labelsize`、`axes.titlesize` |
| 個々の Artist の詳細属性 | Matplotlib | `get_axis()` / `get_ax2()`、`line()` / `scatter()` の戻り値の setter |

`plot.y` は左 Y 軸です。`plot.right_y` は設定が必要になるまで右 Axes を生成しません。各 `style()` の引数は型付きのキーワード引数で、IDE の補完から探せます。省略した属性と `None` を渡した属性は変更しません。

## グラフごとに必要な項目だけ変える

```python
from matplotlib.ticker import MultipleLocator
from plotting_tools import Plot

with Plot(style="paper", axes_size=(5, 3)) as plot:
    plot.line([0, 1, 2], [1, 3, 2], marker="o", label="Measurement")
    plot.set_labels("Time (s)", "Pressure (Pa)")
    plot.set_xlim(0, 10)
    plot.x.style(label_size=10, tick_label_size=9, major_locator=MultipleLocator(2))
    plot.y.style(label_size=14, tick_label_size=12)
    plot.set_title("Experiment")
    plot.title.style(font_size=12)
    plot.legend.style(font_size=10, frame=False)
    plot.save("customized.svg")
```

`style()` と `set_labels()` / `set_title()` の呼び出し順序で、明示した文字サイズや色が初期化されることはありません。同じ属性を再度指定すると後の変更が優先されます。

凡例の設定は生成前でも指定できます。生成後の `legend.style()` は既存の凡例を更新し、`finalize()` もその凡例を保持します。系列を追加して凡例の項目を作り直すときは `create_legend()` を再度呼びます。その場合、凡例へ直接加えた編集は再設定してください。イベント注釈は `finalize()` / `save()` 時点の凡例を避けます。

## 共通設定をファイルへ置く

例えば `lab.mplstyle` を次の内容で用意します。

```ini
font.family: DejaVu Sans
font.size: 12
axes.labelsize: 14
axes.titlesize: 16
xtick.labelsize: 10
ytick.labelsize: 10
lines.linewidth: 1.5
legend.frameon: False
```

`Plot(style="lab.mplstyle")` で使います。適用順は Matplotlib 標準値 → 同梱 `paper` → 利用者の style → 明示的な `style()`・描画引数です。利用者の style が省略した項目は `paper` の既定値を使います。複数ファイルは `style=["lab.mplstyle", "presentation.mplstyle"]` のように指定順に重ねられます。

## イベントの色と透明度

```python
plot.events.style(span_alpha=0.5, point_alpha=1.0, default_color="green")
plot.events.add_span(10, 20, label="Heating", color="red")
plot.events.add_point(25, label="Measurement")
```

`style()` は指定した項目だけを変更し、生成済みのイベントにも反映します。個別の `color` は共通色より優先します。期間・時点の既定透明度はそれぞれ0.1・0.8、既定色はgreenです。透明度は0〜1、ラベルの透明度は変更しません。

共通設定を `.mplstyle` に置く場合、次のコメントdirectiveを使います。

```ini
# plotting_tools.events.span_alpha: 0.5
# plotting_tools.events.point_alpha: 1.0
# plotting_tools.events.default_color: green
```

`# ` で始まる上記3項目だけをPlottingToolsがファイルから読み取ります。Matplotlib単体で使うと通常のコメントとして無視されます。通常のrcParamsキーとしては登録しないため、グローバル設定を汚染しません。コメントを外して独自キーを記述すると、Matplotlibは未知のキーとして破棄します。

適用順はイベントの既定値 → 指定ファイルの順序による上書き → `events.style()` → 個別 `color` です。通常のMatplotlibスタイル名とファイルパスは混在でき、標準部分は従来のMatplotlib読み込みに委ねます。イベントdirectiveはローカルファイルパス指定時に読み取ります。Matplotlibの登録済みスタイル名やURLからの独自設定読込みは対象外です。Plot間で設定を共有しません。

投影環境で背景領域が薄く見える場合は `span_alpha` を上げて調整できます。プロジェクターのHSL変換を仮定した自動補正は行いません。既存SVGはイベントの `opacity` / `stroke-opacity` を編集できますが、同じ値を使う別の図形まで置換しないよう対象を確認してください。既存SVGの一括変換機能は提供しません。
