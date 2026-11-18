"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from collections.abc import Sequence
import numpy as np
from scipy.stats import bootstrap
POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human, judge):
    tp = sum(h == POS and j == POS for h, j in zip(human, judge))
    fp = sum(h != POS and j == POS for h, j in zip(human, judge))
    fn = sum(h == POS and j != POS for h, j in zip(human, judge))
    return {"tp": tp, "fp": fp, "fn": fn, "tn": len(human) - tp - fp - fn}


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    c = confusion(human, judge)
    tp, fp, fn = c["tp"], c["fp"], c["fn"]
    precision = tp / (tp + fp) if tp + fp else 0.0   # no predicted FAIL -> 0.0 (starter spec)
    recall = tp / (tp + fn) if tp + fn else 0.0      # no real FAIL -> 0.0
    return precision, recall


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    tp = sum(h == POS and j == POS for h, j in zip(human, judge))
    tn = sum(h != POS and j!=POS for h,j in zip(human,judge))
    fp = sum(h != POS and j == POS for h, j in zip(human, judge))
    fn = sum(h == POS and j != POS for h, j in zip(human, judge))
    n = len(human)
    if n == 0:
        raise ValueError("kappa undefined: empty input")
    po = (tn + tp)/n
    p_human_fail = human.count(POS)/n
    p_judge_fail = judge.count(POS)/n
    pe = p_human_fail*p_judge_fail +(1-p_human_fail)*(1-p_judge_fail)
    if pe == 1:                                    # thêm
        raise ValueError("kappa undefined")        # thêm
    return (po-pe)/(1-pe)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    denom = sensitivity + specificity - 1
    if abs(denom) < 1e-12:
        raise ValueError("sensitivity + specificity == 1: the judge carries no signal")
    return min(1,max(0,(observed_rate+specificity-1)/denom))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
        

    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if np.array_equal(a, b):
        return 0.0, 0.0, 0.0
    res = bootstrap((a, b), lambda x, y, axis: np.mean(x, axis=axis) - np.mean(y, axis=axis),
                    paired=True, vectorized=True, method="percentile", n_resamples=n_resamples,
                    confidence_level=confidence, rng=np.random.default_rng(rng))
    ci = res.confidence_interval
    return float(a.mean() - b.mean()), float(ci.low), float(ci.high)


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    from math import comb

    if not (n >= 1 and 0 <= c <= n and 1 <= k <= n):
        raise ValueError(f"bad (n, c, k) = ({n}, {c}, {k})")
    return 1 - comb(n - c, k) / comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    from math import comb

    if not (n >= 1 and 0 <= c <= n and 1 <= k <= n):
        raise ValueError(f"bad (n, c, k) = ({n}, {c}, {k})")
    return comb(c, k) / comb(n, k)
