from prefect import flow, task

run_count = 0


@task(retries=10)
def sad_task():
    global run_count
    run_count += 1
    if run_count < 3:
        raise ValueError()
    return 1


@flow
def hello():
    return sad_task()


if __name__ == "__main__":
    result = hello()
    assert result == 1, f"Got {result}"
    assert run_count == 3, f"Got {run_count}"
