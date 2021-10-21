"""
This Flow uses Prefect's Task Looping feature for computing
the largest Fibonacci number less than a given number M. Each
Fibonacci number is computed using a black-box external API.
"""
from datetime import timedelta

import requests

import prefect
from prefect import Flow, Parameter, task
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


with Flow("fibonacci") as flow:
    M = Parameter("M")
    fib_num = compute_large_fibonacci(M)


flow_state = flow.run(M=100)
print(flow_state.result[fib_num].result)  # 89
