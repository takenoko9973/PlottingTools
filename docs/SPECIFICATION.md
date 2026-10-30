# PlottingTools 公開仕様書

この文書は、`plotting_tools` package root から公開する描画 API の入力条件、返却値、描画・保存時の振る舞いを定めます。外観や描画形式のうち Matplotlib に委ねる部分は、使用する Matplotlib backend と設定に従います。

## 1. 目的と適用範囲

PlottingTools は、数値系列や時間系列を Matplotlib の Figure と Axes に描き、軸、スタイル、凡例、イベント注釈、出力をまとめて扱う Python ライブラリです。データの読み込み、単位変換、保存先の決定、GUI は行いません。

本書は package root から import できるクラス、関数、および `GraphBuilder` の利用者向け動作を扱います。描画結果の細部のうち Matplotlib に委ねるものは、Matplotlib のバージョン、backend、フォント、Locator、Formatter により変わることがあります。

## 2. 公開 API と基本利用

`Plot` は `GraphBuilder` の同一クラス別名です。どちらの名前で生成しても同じ API と動作になります。コンストラクターは `Plot(*, style=None, fig_size=None, axes_size=None, strict_mathtext=False)` で、すべての引数がキーワード専用です。

```python
from plotting_tools import Plot

with Plot(style="paper") as plot:
    plot.line([0, 1, 2], [1.0, 2.5, 1.5], label="Sample")
    plot.set_labels("Time (s)", "Voltage (V)")
    plot.save("result.svg")
```

package root は `AxisSide`、`EventDrawer`、`EventLayoutData`、`EventPlotConfig`、`EventPoint`、`EventSpan`、`GraphBuilder`、`Plot`、`PlotInfo`、`ScaleEnum`、`format_sci_mathtext` を公開します。

## 3. データ型と入力条件

系列追加 API は X と Y の1次元データを受け取り、長さが等しくない場合や2次元データの場合は `ValueError` を送出します。DataFrame 全体は渡せません。DataFrame の列を使う場合は、`frame["column"]` のように列を選択します。

| データ | 受け付ける型 |
|---|---|
| X | Python の数値または文字列の sequence、NumPy の数値または `datetime64` 配列、Pandas Series / Index |
| Y | Python の数値 sequence、NumPy の数値配列、Pandas Series / Index |

PlottingTools は、全値の有限性、空系列、Y の対数軸に対する正値性を追加検証しません。これらを含む値の描画・除外・警告は Matplotlib の動作に従います。

## 4. Line 系列

`line(x, y, *, label="", color=None, linestyle=None, linewidth=None, marker=None, markersize=None, side=AxisSide.LEFT, scale=None)` は `Line2D` を返します。返された artist は Matplotlib の setter で直接編集できます。

`side` は `AxisSide.LEFT` / `AxisSide.RIGHT` または `"left"` / `"right"`、`scale` は `ScaleEnum.LINEAR` / `ScaleEnum.LOG` または `"linear"` / `"log"` を受け取ります。`scale=None` は指定軸の現在のスケールを保持します。

`color`、`linestyle`、`linewidth`、`marker`、`markersize` を省略した場合は Matplotlib の色サイクルと style の値が使われます。明示した値は style より優先されます。`linewidth` は明示した `PlotInfo.linewidth`、次に Matplotlib style の `lines.linewidth` の順に決まります。`PlotInfo.linewidth` は正値が必要です。`marker` と `markersize` の省略値はそれぞれ style の `lines.marker` と `lines.markersize` に従います。線幅とマーカーサイズの単位はポイントです。

## 5. Scatter 系列

`scatter(x, y, *, color=None, marker=None, s=None, label="", side=AxisSide.LEFT, scale=None)` は `PathCollection` を返します。返された collection は Matplotlib の API で直接編集できます。`side` と `scale` の値、および省略時のスケールは `line()` と同じです。

`s` は Matplotlib の散布図と同じポイントの二乗単位で、スカラーまたは各点に対応する配列を渡します。`s=None`、marker、色サイクル、edge color などの既定値は Matplotlib と適用中の style に従います。

Line と Scatter は凡例候補に追加順で記録されます。空の `label` は凡例に表示されません。Scatter は `lines` 属性には入りません。`lines` は引き続き `Line2D` だけを保持します。

## 6. Figure と描画領域の寸法

コンストラクターの `fig_size=(width, height)` と `axes_size=(width, height)` はインチ指定で、同時には指定できません。どちらも正の有限数2つが必要です。不正値または同時指定では `ValueError` を送出します。

| 指定 | 固定する寸法 | Figure 寸法の決定 |
|---|---|---|
| `fig_size` | Figure 全体 | 指定された幅・高さを保つ |
| `axes_size` | 描画領域（Axes） | Axes の実寸を保ち、目盛・ラベル・タイトル・指数表示・通常の外側凡例などの余白を含めて Figure を拡大する |
| どちらも省略 | なし | style の `figure.figsize` を使う |

既定の `paper` style は Figure を 8 × 5.5 inch、100 dpi にします。明示された `fig_size` または `axes_size` が style の `figure.figsize` より優先されます。Figure の DPI は style の `figure.dpi` で指定し、保存時の解像度は Matplotlib の `savefig` 引数と設定に従います。

`axes_size` は左右の Y 軸に同じ Axes 寸法を保ちます。通常の SVG 保存では clip 領域も指定した Axes の実寸になります。目盛、軸ラベル、タイトル、Axes に属する通常の外側凡例などに必要な余白は Figure 側に確保します。Figure-level artist（例: `fig.suptitle()`）や任意の Figure 位置・layout 変更による外側領域はこの寸法保証の対象ではなく、見切れないことを保証しません。装飾が変われば Figure の外寸は変わり得ますが、繰り返しの `finalize()` / `save()` で余白が累積することはありません。`axes_size` 使用時に利用者が `fig.tight_layout()` を直接呼ぶと Matplotlib の警告が出ますが、固定 Axes 寸法は保たれます。`axes_size` を省略した場合は `tight_layout` が適用されます。

通常の `save()` は指定 Figure 寸法を出力します。`save(..., bbox_inches="tight")` など出力領域を変更する Matplotlib 引数を指定すると、出力キャンバスが crop され、Figure の外寸保証とは異なる結果になります。

## 7. 軸範囲とスケール

X 軸と左右の Y 軸はそれぞれ独立して扱います。範囲とスケールは操作メソッドで設定します。

- `set_xlim(xmin, xmax)` は X 軸範囲を設定します。両端の差の絶対値が `1e-9` 未満なら、各端を 0.5 ずつ広げます。
- `set_ylim(side, ymin, ymax)` は指定した Y 軸の範囲を固定します。`ymin >= ymax` は `ValueError` です。
- `expand_ylim_to_include(side, ymin, ymax)` は `finalize()` 時に自動範囲を指定範囲まで包含するよう拡張します。範囲の大小が逆または等しい場合は `ValueError` です。
- `set_yscale(side, scale)`、`line()`、`scatter()`、`PlotInfo.scale` は左右の Y 軸に `linear` または `log` を設定します。スケールを省略した系列追加は現在のスケールを維持します。

対数軸に不適切な値や範囲を渡した場合の描画結果・警告は Matplotlib に従います。Locator / Formatter を明示した場合、指定したスケールに適合する設定を選ぶ責任は利用者にあります。

## 8. グループ別の表示設定

`plot.x` は X 軸、`plot.y` は左 Y 軸、`plot.right_y` は右 Y 軸を表します。グループへのアクセスだけでは右 Axes を生成せず、右軸の設定や描画に必要になった時点で `twinx()` により生成します。

各軸の `style()` は次のキーワード専用引数を受け取ります。すべての既定値は `None`（変更しない）です。

| 引数 | 値と適用先 |
|---|---|
| `label_size` / `label_color` | 軸ラベルの文字サイズ（pt）/ Matplotlib の色 |
| `tick_label_size` | 主目盛・補助目盛のラベル文字サイズ（pt） |
| `tick_direction` | 主目盛・補助目盛の方向（`"in"` / `"out"` / `"inout"`） |
| `tick_length` / `tick_width` | 主目盛線の長さ / 幅（pt） |
| `major_locator` / `minor_locator` | 主目盛 / 補助目盛の Matplotlib `Locator` |
| `major_formatter` / `minor_formatter` | 主目盛 / 補助目盛の Matplotlib `Formatter` |
| `grid` | 対象軸の主目盛グリッドの表示有無（bool） |

明示した Locator と Formatter は、後続の系列追加、`finalize()`、builder によるスケール変更後も保持します。style の minor tick 表示、分割数、formatter の Mathtext 設定は尊重します。目盛位置や科学表記への切り替え閾値は固定しません。

`plot.title.style(*, font_size=None, color=None)` はタイトルの文字サイズ（pt）と色だけを変更します。`set_title()` は文字列を変更し、style の `axes.titlelocation` に従うタイトルを使います。`set_labels()` も文字列だけを変更します。これらの文字列設定の前後どちらで `style()` を呼んでも、指定した外観は維持します。同じ属性を再度明示すると後の指定が優先されます。

軸範囲・スケール・ラベル文字列は `style()` の対象に含めません。特殊な grid 属性やフォントなど頻出引数以外は `get_axis()` などから Matplotlib の標準 API を使います。設定先の逆引きは[設定ガイド](CUSTOMIZATION.md)を参照してください。

## 9. Style と設定の優先順位

style の適用順は Matplotlib 標準値、同梱 `paper`、`style=` に指定した style（リストなら指定順）、明示的なグループの `style()` または描画引数です。`style` は Matplotlib style 名、style ファイルの path、またはそれらのリストを受け取ります。未指定時も `paper` を適用します。

グループの `style()` は指定属性だけを既存の Matplotlib オブジェクトへ適用し、未指定の属性を初期化しません。共通の DPI、色、フォント、目盛などは `.mplstyle` で設定します。凡例については Artist 生成前の呼び出しと再生成に備え、明示した値だけを保持します。

選択された style の値はグラフごとに保持され、別の PlottingTools グラフや無関係な Matplotlib 操作へ設定が漏れないように適用されます。直接取得した Figure / Axes の操作は Matplotlib の規則に従います。

## 10. 科学表記と Mathtext

線形軸では Matplotlib の `ScalarFormatter` を使います。必要な値域では各目盛を個別に変換せず、軸共通の指数を Mathtext で表示します。対数軸は Matplotlib の標準 formatter を使います。`axes.formatter.use_mathtext: False` を指定した style では通常の formatter 表示になります。表示閾値や tick 座標は固定しません。

`format_sci_mathtext(x, pos=None, *, precision=1)` は有限値を係数と指数の Mathtext（例: `"$1.25 \\times 10^{3}$"`）に変換し、`FuncFormatter` などへ明示的に渡して使う関数です。`precision` は係数の小数桁数で、負値は `ValueError` です。`pos` は `FuncFormatter` との接続用で、値の変換には使いません。正負のゼロは `"0"`、NaN は `"$\\mathrm{NaN}$"`、正負の無限大は `"$\\infty$"` または `"$-\\infty$"` を返します。丸めによって指数が繰り上がる値も正規化します。この関数は全軸目盛へ自動適用されません。

PlottingTools が受け取る系列 label、軸 label、title、および `add_safe_text()` の文字列は Mathtext を検証します。不正な文字列は通常 `UserWarning` を出して `[Label Error]` に置き換え、`Plot(strict_mathtext=True)` では `ValueError` にします。不正文字列を `add_safe_text()` が置き換える場合は赤で表示します。取得した Axes へ直接追加した任意の Text は一括検証しません。

`add_safe_text(x, y, text, ax_side=AxisSide.LEFT, **kwargs)` は編集可能な `Text` を返します。`get_safe_text_dimensions(text, fontsize, ax_side=AxisSide.LEFT)` は文字列の幅を data 座標、文字列の高さを Axes 相対座標で返します。

## 11. 凡例

`plot.legend.style(*, visible=None, loc=None, font_size=None, frame=None, ncols=None)` は凡例の表示有無、位置、文字サイズ（pt）、枠の表示有無、列数を変更します。省略または `None` の属性は変更しません。`loc` は Matplotlib の位置名・コード・座標を受け取り、`ncols` は正の整数が必要です。生成前でも呼び出すことができ、生成時に明示値を適用します。既定は表示あり、1列で、その他の外観は style に従います。

生成済みの場合は既存の `Legend` を更新します。`visible=False` は既存 Artist を非表示にし、`visible=True` は再表示します。表示状態はイベント注釈の凡例衝突回避にも反映します。列数や文字サイズの変更も既存 Legend に適用され、未指定の文字色・タイトル・枠の属性などは維持します。

`create_legend()` は現在の系列から凡例を生成し、編集可能な `Legend` を返します。表示対象ラベルがない場合、または凡例が非表示設定の場合は `None` です。Line / Scatter の項目は追加順で、空ラベルは含めません。再度呼ぶと現在の系列と明示設定で凡例を作り直します。Matplotlib で直接加えた編集を保持するには既存 Legend を操作してください。

`finalize()` は凡例がまだなければ生成します。事前に生成して利用者が編集した既存凡例は保持します。凡例生成後に系列を追加しても、既存凡例を自動更新しません。項目を更新するには `create_legend()` を再度呼びます。イベント注釈の配置測定用に一時生成した凡例は除去され、その後の確定時には最新の系列から生成します。

## 12. イベント注釈

`EventSpan` は `event`, `start`, `end`, `label=None`, `dx=0.0`, `y=None` を持つ期間モデルです。`start >= end` は `ValueError` です。`EventPoint` は同じ共通フィールドに `time` を持つ時点モデルです。両者は frozen dataclass です。`EventPlotConfig` はイベント色辞書 `colors`、期間一覧 `spans`、時点一覧 `points` を持ちます。

`EventLayoutData` には描画済みの X、左 Y、右 Y の系列、`secondary_ylim`、`primary_scale`、`secondary_scale` を渡します。`secondary_ylim` は必須で、scale の既定値は左右とも `ScaleEnum.LINEAR` です。3系列は1次元で長さが等しく、`secondary_ylim` は昇順である必要があります。これらの値と scale は利用者が描画済み系列・軸に合わせます。ラベル配置は渡された系列や凡例との衝突を減らす候補を選びますが、完全な非重複や最適配置は保証しません。

`EventDrawer(builder, config, time_shift_sec=0.0, divisor=1.0).draw_events(layout_data, extra_spans=None)` は期間を塗りつぶし、時点に縦線を加えます。イベント時刻は `(seconds - time_shift_sec) / divisor`、`dx` は `dx / divisor` に変換されます。`divisor=0` は `ValueError` です。変換後 X が 0 以下で終了する期間と、変換後 X が負の時点は描画しません。変換後 X が負の位置から続く期間は X=0 から描きます。イベントに label がなければ図形だけを描きます。イベント名に色が設定されていない場合の図形色は緑です。ラベルの `y` は Axes 相対位置です。label 中の文字列 `\n` は改行として描画されます。

## 13. Figure の確定と保存

`finalize()` は Y 軸包含範囲、凡例、layout を適用し、Matplotlib `Figure` を返します。Figure を直接扱う場合は `plot.finalize().savefig(path)` を使えます。保存時にも選択した style を適用するには `save(path, **kwargs)` を使います。`save()` は `finalize()` の後に Matplotlib の `savefig()` を呼び出し、保存結果を返しません。

PNG、SVG、PDF など Matplotlib backend が扱う形式に保存できます。拡張子に対応する backend 機能、フォント、保存引数の制約は Matplotlib に従います。たとえば SVG で `svg.fonttype: none` を使っても、Mathtext の一部が path になり得るため、すべての文字が編集可能なテキストになることは保証しません。layout または保存の例外はそのまま送出します。

`close()` は Figure 内の artist を破棄します。context manager は `with` の正常終了・例外終了のどちらでも同じ cleanup を実行し、処理中の例外を抑制しません。`close()` 後に同じ builder を再利用する動作は保証しません。

## 14. 公開 API の一覧

| 公開要素 | 契約 |
|---|---|
| `GraphBuilder` / `Plot` | 同一クラス。constructor は `style`、`fig_size`、`axes_size`、`strict_mathtext` のキーワード専用引数 |
| `PlotInfo` | 必須の `data` と `axis=AxisSide.LEFT`、`label=""`、`color=None`、`style=None`、`linewidth=None`、`scale=None`。`style` は line format string、`linewidth` は正値、`scale=None` は現在の軸スケールを保持 |
| `AxisSide` / `ScaleEnum` | `LEFT="left"`, `RIGHT="right"` / `LINEAR="linear"`, `LOG="log"` |
| `x.style()` / `y.style()` / `right_y.style()` | 対象軸の外観と主目盛・補助目盛の Locator / Formatter |
| `title.style()` / `legend.style()` | タイトルの外観 / 凡例の表示・配置・外観 |
| `line()` / `scatter()` / `add_plot()` | `Line2D` / `PathCollection` / `None` を返す。`lines` は `Line2D` のみ |
| `set_labels()` / `set_title()` | 軸ラベル / タイトルの文字列を設定 |
| `set_xlim()` / `set_ylim()` / `expand_ylim_to_include()` / `set_yscale()` | 軸範囲・包含範囲・Y軸スケールの操作 |
| `create_legend()` | 編集可能な `Legend`、または生成対象がないとき `None` |
| `finalize()` / `save()` | `Figure` を返す / Matplotlib 保存を実行し戻り値なし |
| `get_axis(side=AxisSide.LEFT)` / `get_ax2()` | 指定側 / 右の Axes を返し、右が未生成なら作成 |
| `add_safe_text()` / `get_safe_text_dimensions()` / `format_sci_mathtext()` | 検証済み注釈・文字寸法計測・科学表記 |
| `EventDrawer` とイベントモデル | `EventLayoutData`、`EventPlotConfig`、`EventPoint`、`EventSpan` に基づく注釈 |
| context manager / `close()` | Figure の Artist を終了時に破棄し、例外は抑制しない |

設定データクラス、`style_config` 引数、`set_x_locator()` / `set_y_locator()` / `set_x_formatter()` / `set_y_formatter()` は公開しません。互換エイリアスや旧引数の受理機構は提供しません。

## 15. 仕様変更の扱い

公開動作を変更するときは、変更対象、入力条件、返却値、例外、保存形式、互換性への影響を確認し、実装・振る舞いを検証するテスト・本仕様書を同じ変更単位で整合させます。テストは利用者から見える動作を検証し、内部 helper や探索順を公開契約として固定しません。以前の仕様と現行実装が食い違う場合は、本書を曖昧なまま残さず、変更の理由と新しい契約に合わせて更新します。
