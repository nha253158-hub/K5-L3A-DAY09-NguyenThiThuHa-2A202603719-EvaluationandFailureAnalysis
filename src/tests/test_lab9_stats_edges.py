"""Edge cases of the M2 helpers (zero denominators) and M6 input validation."""
import pytest

pytestmark = pytest.mark.student


@pytest.fixture(scope="module")
def stats():
    from lab9 import stats

    return stats


def test_precision_recall_zero_denominator_is_zero(stats):
    assert stats.precision_recall(["PASS"] * 3, ["PASS"] * 3) == (0.0, 0.0)   # no FAIL anywhere
    assert stats.precision_recall(["PASS"] * 3, ["FAIL", "PASS", "PASS"]) == (0.0, 0.0)  # judge flags a non-failure


def test_kappa_and_rogan_gladen_undefined_raise_value_error(stats):
    with pytest.raises(ValueError):
        stats.cohen_kappa([], [])
    with pytest.raises(ValueError):
        stats.rogan_gladen(0.3, 0.5, 0.5)  # sensitivity + specificity == 1: no signal


@pytest.mark.parametrize("n, c, k", [(5, 3, 6), (5, 6, 1), (5, -1, 1), (0, 0, 1), (5, 3, 0)])
def test_pass_k_rejects_bad_arguments(stats, n, c, k):
    with pytest.raises(ValueError):
        stats.pass_at_k(n, c, k)
    with pytest.raises(ValueError):
        stats.pass_hat_k(n, c, k)
