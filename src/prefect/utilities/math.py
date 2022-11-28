import math
import random


def poisson_interval(average_interval):
    # note that we ensure the argument to the logarithm is stabilized to prevent
    # calling log(0), which results in a DomainError
    return -math.log(max(1 - random.random(), 1e-10)) * average_interval


def clamped_poisson_interval(average_interval, clamping_factor=0.3):
    """
    Clamps Poisson intervals to a range defined by the clamping_factor

    Note that because the distribution of Poisson intervals is not symmetric around the
    average interval, a symmetric clamp with slightly skew the mean interval.
    """

    interval = poisson_interval(average_interval)
    while not (
        average_interval * (1 - clamping_factor)
        < interval
        < average_interval * (1 + clamping_factor)
    ):
        interval = poisson_interval(average_interval)
    return interval
