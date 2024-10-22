"""This is a regression test for https://github.com/PrefectHQ/prefect/issues/15747"""

from typing import Tuple

from prefect import flow, task
from prefect.client.schemas.objects import FlowRun
from prefect.context import get_run_context
from prefect.runtime import task_run


def generate_task_run_name(parameters: dict) -> str:
    return f'{task_run.task_name} - input: {parameters["input"]["number"]}'


@task(log_prints=True, task_run_name=generate_task_run_name)
def increment_number(input: dict) -> dict:
    input["number"] += 1
    input["name"] = get_run_context().task_run.name
    print(f"increment_number - result: {input['number']}")
    return input


@flow
def double_increment_flow() -> Tuple[list, FlowRun]:
    inputs = [
        {"number": 1, "is_even": False},
        {"number": 2, "is_even": True},
    ]

    first_increment = increment_number.map(input=inputs)
    second_increment = increment_number.map(input=first_increment)
    final_results = second_increment.result()
    print(f"Final results: {final_results}")
    return final_results


async def test_flow_with_mapped_tasks():
    results = double_increment_flow()
    assert results == [
        {"number": 3, "is_even": False, "name": "increment_number - input: 2"},
        {"number": 4, "is_even": True, "name": "increment_number - input: 3"},
    ]
