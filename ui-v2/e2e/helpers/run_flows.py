import argparse
import asyncio
import json
import sys
from uuid import uuid4

from prefect import flow, task
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import (
    FlowRunFilter,
    FlowRunFilterId,
    FlowRunFilterParentTaskRunId,
)


async def get_task_runs_for_flow(flow_run_id, expected_count=1):
    """Query task runs for a flow, retrying until they are persisted.

    After a flow completes, task run data may not be immediately visible
    in the API due to async persistence. This polls until the expected
    number of task runs appear.
    """
    async with get_client() as client:
        for _ in range(20):
            task_runs = await client.read_task_runs(
                flow_run_filter=FlowRunFilter(id=FlowRunFilterId(any_=[flow_run_id]))
            )
            if len(task_runs) >= expected_count:
                return task_runs
            await asyncio.sleep(0.5)
        return task_runs


def run_simple_task(prefix):
    suffix = uuid4().hex[:8]

    @task(task_run_name=f"{prefix}task-{suffix}")
    def simple_task():
        return "done"

    @flow(flow_run_name=f"{prefix}flow-{suffix}")
    def simple_flow():
        simple_task()

    state = simple_flow(return_state=True)
    flow_run_id = state.state_details.flow_run_id

    task_runs = asyncio.run(get_task_runs_for_flow(flow_run_id))

    return {
        "flow_run_id": str(flow_run_id),
        "flow_run_name": f"{prefix}flow-{suffix}",
        "task_run_ids": [str(tr.id) for tr in task_runs],
        "task_run_names": [tr.name for tr in task_runs],
    }


def run_parent_child(prefix):
    suffix = uuid4().hex[:8]

    @flow(flow_run_name=f"{prefix}child-flow-{suffix}")
    def child_flow():
        return "child done"

    @task(task_run_name=f"{prefix}trigger-task-{suffix}")
    def trigger_task():
        return child_flow()

    @flow(flow_run_name=f"{prefix}parent-flow-{suffix}")
    def parent_flow():
        trigger_task()

    state = parent_flow(return_state=True)
    parent_flow_run_id = state.state_details.flow_run_id

    async def get_data():
        async with get_client() as client:
            # Wait for task runs to be persisted before querying child flows
            task_runs = []
            for _ in range(20):
                task_runs = await client.read_task_runs(
                    flow_run_filter=FlowRunFilter(
                        id=FlowRunFilterId(any_=[parent_flow_run_id])
                    )
                )
                if task_runs:
                    break
                await asyncio.sleep(0.5)
            flow_runs = (
                await client.read_flow_runs(
                    flow_run_filter=FlowRunFilter(
                        parent_task_run_id=FlowRunFilterParentTaskRunId(
                            any_=[tr.id for tr in task_runs]
                        )
                    )
                )
                if task_runs
                else []
            )
            return task_runs, flow_runs

    task_runs, child_flow_runs = asyncio.run(get_data())

    child_flow_run = child_flow_runs[0] if child_flow_runs else None

    return {
        "parent_flow_run_id": str(parent_flow_run_id),
        "parent_flow_run_name": f"{prefix}parent-flow-{suffix}",
        "child_flow_run_id": str(child_flow_run.id) if child_flow_run else None,
        "child_flow_run_name": (child_flow_run.name if child_flow_run else None),
        "task_run_ids": [str(tr.id) for tr in task_runs],
        "task_run_names": [tr.name for tr in task_runs],
    }


def run_flow_with_tasks(prefix):
    suffix = uuid4().hex[:8]

    @task(task_run_name=f"{prefix}task-a-{suffix}")
    def task_a():
        return "a"

    @task(task_run_name=f"{prefix}task-b-{suffix}")
    def task_b():
        return "b"

    @flow(flow_run_name=f"{prefix}graph-flow-{suffix}")
    def graph_flow():
        task_a()
        task_b()

    state = graph_flow(return_state=True)
    flow_run_id = state.state_details.flow_run_id

    task_runs = asyncio.run(get_task_runs_for_flow(flow_run_id, expected_count=2))

    return {
        "flow_run_id": str(flow_run_id),
        "flow_run_name": f"{prefix}graph-flow-{suffix}",
        "task_run_ids": [str(tr.id) for tr in task_runs],
        "task_run_names": [tr.name for tr in task_runs],
    }


SCENARIOS = {
    "simple-task": run_simple_task,
    "parent-child": run_parent_child,
    "flow-with-tasks": run_flow_with_tasks,
}


def main():
    parser = argparse.ArgumentParser(
        description="Run Prefect flow scenarios for E2E tests"
    )
    parser.add_argument(
        "--scenario",
        required=True,
        choices=SCENARIOS.keys(),
        help="Scenario to run",
    )
    parser.add_argument(
        "--prefix",
        required=True,
        help="Prefix for run names (for test isolation)",
    )
    args = parser.parse_args()

    scenario_fn = SCENARIOS[args.scenario]
    try:
        result = scenario_fn(args.prefix)
    except Exception as e:
        print(f"Error running scenario '{args.scenario}': {e}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result))


if __name__ == "__main__":
    main()
