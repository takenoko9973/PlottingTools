"""matplotlibの目盛表示に利用するformatter関数を提供する。"""

import math


def format_sci_mathtext(
    x: float,
    pos: object = None,  # noqa: ARG001
    *,
    precision: int = 1,
) -> str:
    """数値を係数の小数桁数を指定したMathtext科学表記へ変換する。"""
    if precision < 0:
        msg = "precision must be non-negative"
        raise ValueError(msg)

    if x == 0:
        return "0"

    if math.isnan(x):
        return r"$\mathrm{NaN}$"
    if math.isinf(x):
        return r"$-\infty$" if x < 0 else r"$\infty$"

    # Python標準の指数書式で丸めと繰り上がりを一緒に行う。
    # 10**exponentを計算しないため、subnormalでもゼロ除算を起こさない。
    coefficient, exponent = f"{x:.{precision}e}".split("e")
    return f"${coefficient} \\times 10^{{{int(exponent)}}}$"
