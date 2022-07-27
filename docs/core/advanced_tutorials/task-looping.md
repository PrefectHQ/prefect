---
sidebarDepth: 0
---
# Dynamic DAGs: Task Looping

Prefect's rich state system allows for unique forms of workflow dynamicism that alter the underlying DAG structure at runtime, while still providing all of the underlying workflow guarantees: individual tasks can have custom retry settings, exchange data, activate notifications, etc.

Previously, [task mapping](/core/concepts/mapping.html) allowed users to elevate parallelizable for-loops into first class parallel pipelines at runtime. Task looping offers much the same benefit, but for situations that require a while-loop pattern.

## An example: large Fibonacci numbers

As a motivating example, let's implement a Prefect Flow which computes the largest [Fibonacci number](https://en.wikipedia.org/wiki/Fibonacci_number) less than a given number **M**.  For the sake of this example, we are going to consider the computation of Fibonacci numbers a complete black box that is only accessible [via API](https://stdlib.com/@nemo/lib/fibonacci/).  Our implementation will proceed by iteratively querying for the next number until we reach one that is larger than **M**.  This presents a unique problem for expressing this pattern as a workflow, as we don't know how many tasks will be required prior to runtime. To illustrate, consider this implementation of our Fibonacci task:

```python
import requests
from prefect import task


@task
def compute_large_fibonacci(M):
    n = 1
    fib = 1

    while True:
        next_fib = requests.post(
            "https://nemo.api.stdlib.com/fibonacci@0.0.1/", data={"nth": n}
        ).json()
        if next_fib > M:
            break
        else:
            fib = next_fib
            n += 1

    return fib
```

Suppose our internet connection goes bad for a short instant and this task fails. What value of **n** caused the failure and how can we restart from **n**? To capture such intermittent issues, we might consider providing this task with retry settings, but that would result in the _entire loop_ rerunning. Wouldn't it be ideal if each individual value of **n** was treated as its own Prefect Task, with its own settings (retry, notifications, etc.)?

### Introducing: Task Looping

The goal is to elevate each individual iteration of the above while loop to its own Prefect Task, which can be retried and handled on its own. A priori we don't know how many iterations will be required. Lucky for us, Prefect supports such _dynamic_ patterns in a first-class way.

There are two pieces of information that need to be conveyed from one iteration to the next: the loop count, as well as the loop payload (which can accumulate or change across iterations). To communicate this information, we will use the Prefect [`LOOP` signal](/api/latest/engine/signals.html#loop) as follows:

```python
import requests
from datetime import timedelta

import prefect
from prefect import task
from prefect.engine.signals import LOOP


@task(max_retries=5, retry_delay=timedelta(seconds=2))
def compute_large_fibonacci(M):
    # we extract the accumulated task loop result from context
    loop_payload = prefect.context.get("task_loop_result", {})

    n = loop_payload.get("n", 1)
    fib = loop_payload.get("fib", 1)

    next_fib = requests.post(
        "https://nemo.api.stdlib.com/fibonacci@0.0.1/", data={"nth": n}
    ).json()

    if next_fib > M:
        return fib  # return statements end the loop

    raise LOOP(message=f"Fib {n}={next_fib}", result=dict(n=n + 1, fib=next_fib))
```

Like all Prefect signals, the `LOOP` signal accepts both `message` and `result` keywords. In this case, however, the result will be included in context under the `task_loop_result` key and is available on the next loop iteration (`task_loop_count` is also available, but we don't need that information here).

### Putting the pieces together

Let's take what we just learned and put the pieces together into an actual Prefect Flow.

```python
from prefect import Flow, Parameter

with Flow("fibonacci") as flow:
    M = Parameter("M")
    fib_num = compute_large_fibonacci(M)
```

As a matter of best practice, we opted to elevate `M` to a [Prefect Parameter](/core/concepts/parameters.html) instead of hardcoding its value.  This way we can experiment with small values and eventually increase the value without recompiling our Flow.

With our Flow built, let's compute the largest Fibonacci number less than 100 and then 1000!

```python
flow_state = flow.run(M=100)
print(flow_state.result[fib_num].result) # 89

flow_state = flow.run(M=1000)
print(flow_state.result[fib_num].result) # 987
```

If you run this Flow locally, you will see a large number of logs corresponding to each iteration of the `compute_large_fibonacci` task - if any one of these individual iterations were to fail, after a 2 second delay the task would retry _without rerunning previously successful iterations_!

## Taking it one step further

Looping in Prefect is a first-class operation - as such, it can be combined with mapping for a truly dynamic workflow!

```python
with Flow("mapped-fibonacci") as mapped_flow:
    ms = Parameter("ms")
    fib_nums = compute_large_fibonacci.map(ms)
```

To be clear - our Flow as written _appears_ to have only two tasks, and has no idea how many values of `M` we might provide nor how many iterations might be needed for each `M`!

```python
flow_state = mapped_flow.run(ms=[10, 100, 1000, 1500])
print(flow_state.result[fib_nums].result) # [8, 89, 987, 987]
```
