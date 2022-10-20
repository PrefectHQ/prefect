from prefect import flow

child_flow_run_count = 0
flow_run_count = 0


@flow
def child_flow():
    global child_flow_run_count
    child_flow_run_count += 1

    # Fail on the first flow run but not the retry
    if flow_run_count < 2:
        raise ValueError()

    return "hello"


@flow(retries=10)
def parent_flow():
    global flow_run_count
    flow_run_count += 1

    result = child_flow()

    # It is important that the flow run fails after the child flow run is created
    if flow_run_count < 3:
        raise ValueError()

    return result


if __name__ == "__main__":
    result = parent_flow()
    assert result == "hello", f"Got {result}"
    assert flow_run_count == 3, f"Got {flow_run_count}"
    assert child_flow_run_count == 2, f"Got {child_flow_run_count}"
