import math

import pytest

from prefect.utilities.math import (
    bounded_poisson_interval,
    clamped_poisson_interval,
    exponential_cdf,
    lower_clamp_multiple,
    poisson_interval,
)


def test_poisson_intervals():
    expected_average = 42
    bunch_of_intervals = [poisson_interval(expected_average) for _ in range(100_000)]
    observed_average = sum(bunch_of_intervals) / len(bunch_of_intervals)
    assert expected_average * 0.97 < observed_average < expected_average * 1.03


@pytest.mark.parametrize("clamping_factor", [0.1, 0.2, 0.5, 1, 10, 100])
def test_clamped_poisson_intervals(clamping_factor):
    expected_average = 42
    bunch_of_intervals = [
        clamped_poisson_interval(expected_average, clamping_factor=clamping_factor)
        for _ in range(100_000)
    ]
    observed_average = sum(bunch_of_intervals) / len(bunch_of_intervals)

    assert expected_average * 0.97 < observed_average < expected_average * 1.03

    assert max(bunch_of_intervals) < expected_average * (1 + clamping_factor), (
        "no intervals should exceed the upper clamp limit"
    )


def test_exponential_cdf_at_zero_is_zero():
    assert exponential_cdf(0, 42) == 0.0


def test_exponential_cdf_at_average_interval():
    # For an exponential distribution, F(mean) == 1 - 1/e.
    assert exponential_cdf(42, 42) == pytest.approx(1 - 1 / math.e)


def test_exponential_cdf_is_monotonic_and_bounded():
    values = [exponential_cdf(x, 42) for x in range(0, 500, 10)]
    assert values == sorted(values)
    assert all(0 <= v < 1 for v in values)
    assert exponential_cdf(10_000, 42) == pytest.approx(1.0)


def test_lower_clamp_multiple_known_values():
    assert lower_clamp_multiple(1) == pytest.approx(1.0)
    assert lower_clamp_multiple(2) == pytest.approx(math.log2(4 / 3))


def test_lower_clamp_multiple_is_positive_and_decreasing():
    values = [lower_clamp_multiple(k) for k in range(1, 10)]
    assert all(v > 0 for v in values)
    assert values == sorted(values, reverse=True)


@pytest.mark.parametrize("k", [50, 100, 1000])
def test_lower_clamp_multiple_large_k_short_circuits_to_zero(k):
    # Large k returns 0 to avoid numerical overflow in 2**k.
    assert lower_clamp_multiple(k) == 0.0


@pytest.mark.parametrize("clamping_factor", [0, -0.1, -1])
def test_clamped_poisson_interval_rejects_nonpositive_clamping_factor(clamping_factor):
    with pytest.raises(ValueError, match="clamping_factor"):
        clamped_poisson_interval(42, clamping_factor=clamping_factor)


def test_bounded_poisson_interval_stays_within_bounds():
    lower, upper = 10, 20
    intervals = [bounded_poisson_interval(lower, upper) for _ in range(10_000)]
    assert all(lower - 1e-9 <= i <= upper + 1e-9 for i in intervals)
    average = sum(intervals) / len(intervals)
    assert lower < average < upper
