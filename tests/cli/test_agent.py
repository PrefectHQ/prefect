from prefect.testing.cli import invoke_and_assert


def test_start_agent_with_no_args():
    invoke_and_assert(
        command=["agent", "start"],
        expected_output="No work queue provided!",
        expected_code=1,
    )


def test_start_agent_with_work_queue_and_tags():
    invoke_and_assert(
        command=["agent", "start", "hello", "-t", "blue"],
        expected_output="Only one of `work_queue` or `tags` can be provided.",
        expected_code=1,
    )
