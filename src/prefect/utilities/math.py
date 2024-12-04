import math
import random


def poisson_interval(
    average_interval: float, lower: float = 0, upper: float = 1
) -> float:
    """
    Generates an "inter-arrival time" for a Poisson process.

    Draws a random variable from an exponential distribution using the inverse-CDF
    method. Can optionally be passed a lower and upper bound between (0, 1] to clamp
    the potential output values.
    """

    # note that we ensure the argument to the logarithm is stabilized to prevent
    # calling log(0), which results in a DomainError
    return -math.log(max(1 - random.uniform(lower, upper), 1e-10)) * average_interval


def exponential_cdf(x: float, average_interval: float) -> float:
    ld = 1 / average_interval
    return 1 - math.exp(-ld * x)


def lower_clamp_multiple(k: float) -> float:
    """
    Computes a lower clamp multiple that can be used to bound a random variate drawn
    from an exponential distribution.

    Given an upper clamp multiple `k` (and corresponding upper bound k * average_interval),
    this function computes a lower clamp multiple `c` (corresponding to a lower bound
    c * average_interval) where the probability mass between the lower bound and the
    median is equal to the probability mass between the median and the upper bound.
    """
    if k >= 50:
        # return 0 for large values of `k` to prevent numerical overflow
        return 0.0

    return math.log(max(2**k / (2**k - 1), 1e-10), 2)


def clamped_poisson_interval(
    average_interval: float, clamping_factor: float = 0.3
) -> float:
    """
    Bounds Poisson "inter-arrival times" to a range defined by the clamping factor.

    The upper bound for this random variate is: average_interval * (1 + clamping_factor).
    A lower bound is picked so that the average interval remains approximately fixed.
    """
    if clamping_factor <= 0:
        raise ValueError("`clamping_factor` must be >= 0.")

    upper_clamp_multiple = 1 + clamping_factor
    upper_bound = average_interval * upper_clamp_multiple
    lower_bound = max(0, average_interval * lower_clamp_multiple(upper_clamp_multiple))

    upper_rv = exponential_cdf(upper_bound, average_interval)
    lower_rv = exponential_cdf(lower_bound, average_interval)
    return poisson_interval(average_interval, lower_rv, upper_rv)


def bounded_poisson_interval(lower_bound: float, upper_bound: float) -> float:
    """
    Bounds Poisson "inter-arrival times" to a range.

    Unlike `clamped_poisson_interval` this does not take a target average interval.
    Instead, the interval is predetermined and the average is calculated as their
    midpoint. This allows Poisson intervals to be used in cases where a lower bound
    must be enforced.
    """
    average = (float(lower_bound) + float(upper_bound)) / 2.0
    upper_rv = exponential_cdf(upper_bound, average)
    lower_rv = exponential_cdf(lower_bound, average)
    return poisson_interval(average, lower_rv, upper_rv)
