"""
This is a simple flow that takes in a required parameter `value` and determines if it is even or odd.

This utilizes one of the control flow tasks from the Prefect task library for evaluating
the conditional returned from the `check_if_even` task.
"""
from prefect import Flow, Parameter, task
from prefect.tasks.control_flow import ifelse


@task
def check_if_even(value):
    return value % 2 == 0


@task
def print_odd(value):
    print("{} is odd!".format(value))


@task
def print_even(value):
    print("{} is even!".format(value))


with Flow("Check Even/Odd") as f:
    value = Parameter("value")
    is_even = check_if_even(value)

    even = print_even(value)
    odd = print_odd(value)

    ifelse(is_even, even, odd)


# Prints '2 is even!'
f.run(value=2)


# Prints '1 is odd!'
f.run(value=1)
