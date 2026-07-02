"""GUIに依存せず描画テストを実行するためのpytest設定。"""

import matplotlib  # noqa: ICN001

# backendはpyplotがimportされる前に固定する必要がある。
matplotlib.use("Agg")
