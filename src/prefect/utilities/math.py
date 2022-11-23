import math
import random


def poisson_interval(average_interval):
    return -math.log(1 - random.random()) * average_interval


def clamped_poisson_interval(average_interval, clamping_factor=0.3):
    interval = poisson_interval(average_interval)
    while not (
        average_interval * (1 - clamping_factor)
        < interval
        < average_interval * (1 + clamping_factor)
    ):
        interval = poisson_interval(average_interval)
    return interval
