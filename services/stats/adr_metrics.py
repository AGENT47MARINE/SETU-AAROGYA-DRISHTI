import math


def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def compute_prr_ror_ic(a: int, b: int, c: int, d: int) -> dict:
    """
    2x2 contingency:
      a: drug + event
      b: drug + other events
      c: other drugs + event
      d: other drugs + other events
    """
    # Haldane-Anscombe correction for sparse counts
    a1, b1, c1, d1 = (a + 0.5, b + 0.5, c + 0.5, d + 0.5)

    prr = _safe_div(_safe_div(a1, a1 + b1), _safe_div(c1, c1 + d1))
    ror = _safe_div(a1 * d1, b1 * c1)
    ic = math.log2(_safe_div(a1 * (a1 + b1 + c1 + d1), (a1 + b1) * (a1 + c1)))

    return {
        "prr": round(prr, 6),
        "ror": round(ror, 6),
        "ic": round(ic, 6),
        "a": a,
        "b": b,
        "c": c,
        "d": d
    }

