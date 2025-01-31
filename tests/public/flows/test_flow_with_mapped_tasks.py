"""This is a regression test for https://github.com/PrefectHQ/prefect/issues/15747"""

from typing import Any

from prefect import flow, task
from prefect.context import TaskRunContext
from prefect.runtime import task_run

names = []


def generate_task_run_name(parameters: dict) -> str:
    names.append(f"{task_run.task_name} - input: {parameters['input']['number']}")
    return names[-1]


def alternate_task_run_name() -> str:
    names.append("wildcard!")
    return names[-1]


@task(task_run_name="other {input[number]}")
def other_task(input: dict) -> dict:
    names.append(TaskRunContext.get().task_run.name)
    return input


@task(log_prints=True, task_run_name=generate_task_run_name)
def increment_number(input: dict) -> dict:
    input["number"] += 1
    return input


@flow
def double_increment_flow() -> list[dict[str, Any]]:
    inputs = [
        {"number": 1, "is_even": False},
        {"number": 2, "is_even": True},
    ]

    first_increment = increment_number.map(input=inputs)
    second_increment = increment_number.with_options(
        task_run_name=alternate_task_run_name
    ).map(input=first_increment)
    final_results = second_increment.result()

    other_task.map(inputs).wait()

    print(f"Final results: {final_results}")
    return final_results


async def test_flow_with_mapped_tasks():
    results = double_increment_flow()
    assert results == [
        {"number": 3, "is_even": False},
        {"number": 4, "is_even": True},
    ]
    assert set(names) == {
        "increment_number - input: 1",
        "increment_number - input: 2",
        "wildcard!",
        "wildcard!",
        "other 3",
        "other 4",
    }
