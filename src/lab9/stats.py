"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import comb, isfinite

import numpy as np
from scipy.stats import bootstrap

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    if len(human) != len(judge) or len(human) == 0:
        raise ValueError("human and judge must be non-empty and have the same length")
    counts = dict.fromkeys(("tp", "fp", "fn", "tn"), 0)
    outcomes = {("FAIL", "FAIL"): "tp", ("PASS", "FAIL"): "fp",
                ("FAIL", "PASS"): "fn", ("PASS", "PASS"): "tn"}
    for actual, predicted in zip(human, judge):
        if actual not in {"PASS", "FAIL"} or predicted not in {"PASS", "FAIL"}:
            raise ValueError("labels must be PASS or FAIL")
        counts[outcomes[actual, predicted]] += 1
    return counts


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    cm = confusion(human, judge)
    predicted = cm["tp"] + cm["fp"]
    actual = cm["tp"] + cm["fn"]
    return (cm["tp"] / predicted if predicted else 0.0,
            cm["tp"] / actual if actual else 0.0)


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    cm = confusion(human, judge)
    n = len(human)
    observed = (cm["tp"] + cm["tn"]) / n
    actual_positive = (cm["tp"] + cm["fn"]) / n
    predicted_positive = (cm["tp"] + cm["fp"]) / n
    expected = actual_positive * predicted_positive + (1 - actual_positive) * (1 - predicted_positive)
    if expected == 1:
        raise ValueError("kappa is undefined when expected agreement is one")
    return (observed - expected) / (1 - expected)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    if not all(isfinite(v) and 0 <= v <= 1 for v in (observed_rate, sensitivity, specificity)):
        raise ValueError("rates must be finite probabilities")
    denominator = sensitivity + specificity - 1
    if denominator <= 0:
        raise ValueError("sensitivity + specificity must exceed one")
    return min(1.0, max(0.0, (observed_rate + specificity - 1) / denominator))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    left, right = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if left.ndim != 1 or right.ndim != 1 or left.size == 0 or left.size != right.size:
        raise ValueError("paired samples must be non-empty one-dimensional arrays of equal length")
    if not np.isfinite(left).all() or not np.isfinite(right).all():
        raise ValueError("paired samples must contain finite values")
    if not 0 < confidence < 1 or isinstance(n_resamples, bool) or not isinstance(n_resamples, int) or n_resamples < 1:
        raise ValueError("invalid bootstrap confidence or resample count")
    delta = float(np.mean(left - right))
    if np.array_equal(left, right):
        return 0.0, 0.0, 0.0
    if left.size == 1:
        return delta, delta, delta

    def difference(x, y, axis=-1):
        return np.mean(x - y, axis=axis)

    result = bootstrap((left, right), difference, paired=True, method="percentile",
                       n_resamples=n_resamples, confidence_level=confidence,
                       rng=np.random.default_rng(rng))
    return delta, float(result.confidence_interval.low), float(result.confidence_interval.high)


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    _validate_pass_k(n, c, k)
    return 1 - comb(n - c, k) / comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    _validate_pass_k(n, c, k)
    return comb(c, k) / comb(n, k)


def _validate_pass_k(n: int, c: int, k: int) -> None:
    if any(isinstance(v, bool) or not isinstance(v, int) for v in (n, c, k)):
        raise ValueError("n, c, k must be integers")
    if not (0 <= c <= n and 1 <= k <= n):
        raise ValueError("require 0 <= c <= n and 1 <= k <= n")
