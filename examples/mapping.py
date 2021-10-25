"""
# Mapping

[Mapping](/core/concepts/mapping.md) in Prefect can be used to apply the same
task (or tasks) to multiple inputs. To map a task, use its `.map` method
instead of calling the task itself.

```python
from prefect import task

@task
def add(x, y):
    return x + y

add(1, 2)  # 3
add.map([1, 10], [2, 3])  # [3, 13]
```

By default all arguments to `.map` expect iterables that can be mapped over. If
you want to pass in a non-iterable argument to be used by all branches in a
mapped task, you can wrap that argument in `unmapped`
([docs](/core/concepts/mapping.md#unmapped-inputs)).

```python
from prefect import unmapped

add.map([1, 10], unmapped(2))  # [3, 12]
```

In this example we build a flow with 4 stages:

- `get_numbers` returns a list of `n` numbers
- `inc` maps across this list, running once per input
- `add` maps across the output of `inc`, running once per input. `unmapped` is
  used to pass `2` as a second "unmapped" argument.
- The total list is then passed to `compute_sum` to calculate a total.

```
             ┌── inc ── add(2) ──┐
             │                   │
get_numbers ─┼── inc ── add(2) ──┼─ compute_sum
             │                   │
             ⋮                   ⋮
             └── inc ── add(2) ──┘
```

Note that the number of inputs to a mapped task doesn't need to be known until
runtime. By default this flow will run with `3` mapped branches - try
providing different values for the parameter `n` to see how it affects
execution.

See the [mapping docs](/core/concepts/mapping.md) for more information.
"""

from prefect import Flow, Parameter, task, unmapped


@task
def get_numbers(n):
    return range(1, n + 1)


@task
def inc(x):
    return x + 1


@task
def add(x, y):
    return x + y


@task(log_stdout=True)
def compute_sum(nums):
    total = sum(nums)
    print(f"total = {total}")
    return total


with Flow("Example: Mapping") as flow:
    # The number of branches in the mapped pipeline
    n = Parameter("n", default=3)

    # Generate the initial items to map over
    nums = get_numbers(n)  # [1, 2, 3]

    # Apply `inc` to every item in `nums`
    nums_2 = inc.map(nums)  # [2, 3, 4]

    # Apply `add` to every item in `nums_2`, with `2` as the second argument.
    nums_3 = add.map(nums_2, unmapped(2))  # [4, 5, 6]

    # Compute the sum of all items in `nums_3`
    total = compute_sum(nums_3)  # 15


if __name__ == "__main__":
    flow.run()
