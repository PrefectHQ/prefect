from prefect.utilities.math import clamped_poisson_interval, poisson_interval


def test_poisson_intervals():
    expected_average = 42
    bunch_of_intervals = [poisson_interval(expected_average) for _ in range(100_000)]
    observed_average = sum(bunch_of_intervals) / len(bunch_of_intervals)
    assert expected_average * 0.95 < observed_average < expected_average * 1.05


def test_clamped_poisson_intervals():
    expected_average = 42
    bunch_of_intervals = [
        clamped_poisson_interval(expected_average, clamping_factor=0.3)
        for _ in range(100_000)
    ]
    observed_average = sum(bunch_of_intervals) / len(bunch_of_intervals)

    assert expected_average * 0.9 < observed_average < expected_average * 1.1

    assert max(bunch_of_intervals) < expected_average * (
        1 + 0.3
    ), "no intervals should exceed the upper clamp limit"

    assert min(bunch_of_intervals) > expected_average * (
        1 - 0.3
    ), "no intervals should be smaller than the lower clamp limit"
