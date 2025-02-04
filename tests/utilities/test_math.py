import pytest

from prefect.utilities.math import clamped_poisson_interval, poisson_interval


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
