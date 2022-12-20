import math
import random


def poisson_interval(average_interval, lower=0, upper=1):
    """
    Generates an "inter-arrival time" for a Poisson process.

    Draws a random variable from an exponential distribution using the inverse-CDF
    method. Can optionally be passed a lower and upper bound between (0, 1] to clamp
    the potential output values.
    """

    # note that we ensure the argument to the logarithm is stabilized to prevent
    # calling log(0), which results in a DomainError
    return -math.log(max(1 - random.uniform(lower, upper), 1e-10)) * average_interval


def exponential_cdf(x, average_interval):
    ld = 1 / average_interval
    return 1 - math.exp(-ld * x)


def lower_clamping_factor(k):
    """
    Computes a lower clamping factor that can be used to bound a random variate drawn
    from an exponential distribution.

    Given an upper clamping factor `k` (and corresponding upper bound k * average_interval),
    this function computes a lower clamping factor `c` (corresponding to a lower bound
    c * average_interval) where the probability mass between the lower bound and the
    median is equal to the probability mass between the median and the upper bound.
    """

    return math.log(max(2**k / (2**k - 1), 1e-10), 2)


def clamped_poisson_interval(average_interval, clamping_factor=0.3):
    """
    Bounds Poisson "inter-arrival times" to a range defined by the clamping factor.

    The upper bound for this random variate is: average_interval * (1 + clamping_factor).
    A lower bound is picked so that the average interval remains fixed.
    """
    k = 1 + clamping_factor
    upper_bound = average_interval * k
    lower_bound = max(0, average_interval * lower_clamping_factor(k))

    upper_rv = exponential_cdf(upper_bound, average_interval)
    lower_rv = exponential_cdf(lower_bound, average_interval)
    return poisson_interval(average_interval, lower_rv, upper_rv)
