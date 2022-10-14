from prefect import flow, task

flow_run_count = 0
task_run_count = 0


@task
def happy_task():
    global task_run_count
    task_run_count += 1
    return 1


@flow(retries=10)
def hello():
    global flow_run_count
    flow_run_count += 1

    first = happy_task()
    if flow_run_count < 3:
        raise ValueError("Retry me please!")

    return first + 1


if __name__ == "__main__":
    result = hello()
    assert result == 2, f"Got {result}"
    assert flow_run_count == 3, f"Got {flow_run_count}"
    assert task_run_count == 1, f"Got {task_run_count}"
