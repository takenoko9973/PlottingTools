"""利用側へ公開するimport経路のsmoke test。"""

import plotting_tools


def test_internal_implementation_is_not_exported() -> None:
    """内部モデルとレイアウト実装が公開APIへ混在しないことを確認する。"""
    internal_names = {
        "LabelItem",
        "LabelLayoutEngine",
        "LabelPriority",
        "PlotConfig",
        "PlotXData",
        "PlotYData",
    }

    assert internal_names.isdisjoint(plotting_tools.__all__)
