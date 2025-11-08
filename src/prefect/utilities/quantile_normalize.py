from __future__ import annotations
from typing import Iterable, List, Optional
import math
from prefect import task

def _finite(vals):
    return [v for v in vals if isinstance(v, (int, float)) and not math.isnan(v)]

def _quantile(sorted_vals, q: float) -> float:
    if not sorted_vals:
        raise ValueError("Cannot compute quantile of empty data")
    if q <= 0.0:
        return sorted_vals[0]
    if q >= 1.0:
        return sorted_vals[-1]
    pos = q * (len(sorted_vals) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_vals[lo]
    frac = pos - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac

@task
def quantile_normalize(
    data: Iterable[Optional[float]],
    low_q: float = 0.01,
    high_q: float = 0.99,
    out_min: float = 0.0,
    out_max: float = 1.0,
) -> List[Optional[float]]:
    """
    Winsorize by quantiles, then scale to [out_min, out_max].
    None and NaN are preserved as None.
    """
    values = list(data)
    vec = _finite(values)
    if not vec:
        raise ValueError("No finite values to normalize")

    vec_sorted = sorted(vec)
    qlo = _quantile(vec_sorted, low_q)
    qhi = _quantile(vec_sorted, high_q)
    if qhi <= qlo:
        raise ValueError("Bad quantile range")

    in_rng = qhi - qlo
    out_rng = out_max - out_min
    if out_rng == 0:
        raise ValueError("Output range must be non zero")

    out: List[Optional[float]] = []
    for v in values:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            out.append(None)
        else:
            v2 = min(max(float(v), qlo), qhi)
            scaled = ((v2 - qlo) / in_rng) * out_rng + out_min
            out.append(scaled)
    return out
