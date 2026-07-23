"""matplotlibの目盛表示に利用するformatter関数を提供する。"""

import math


def format_sci_mathtext(x: float, pos: object = None) -> str:  # noqa: ARG001
    """数値をmathtextで表示可能な科学表記へ変換する。"""
    if x == 0:
        return "0"

    exponent = math.floor(math.log10(abs(x)))
    coefficient = x / (10**exponent)
    return f"${coefficient:.1f} \\times 10^{{{exponent}}}$"
