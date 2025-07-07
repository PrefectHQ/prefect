from prefect import flow

child_flow_run_count = 0
flow_run_count = 0


@flow
def child_flow():
    global child_flow_run_count
    child_flow_run_count += 1
    if flow_run_count < 2:
        raise ValueError()
    return "hello"


@flow(retries=10)
def parent_flow():
    global flow_run_count
    flow_run_count += 1
    result = child_flow()
    if flow_run_count < 3:
        raise ValueError()
    return result


def test_flow_retries_with_subflows():
    """Test for flow_retries_with_subflows."""
    result = parent_flow()
    assert result == "hello", f"Got {result}"
    assert flow_run_count == 3, f"Got {flow_run_count}"
    assert child_flow_run_count == 3, f"Got {child_flow_run_count}"
