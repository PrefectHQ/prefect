from prefect.testing.cli import invoke_and_assert


def test_start_agent_with_no_args():
    invoke_and_assert(
        command=["agent", "start"],
        expected_output="No work queues provided!",
        expected_code=1,
    )


def test_start_agent_with_work_queue_and_tags():
    invoke_and_assert(
        command=["agent", "start", "hello", "-t", "blue"],
        expected_output_contains="Only one of `work_queues`, `regex`, or `tags` can be provided.",
        expected_code=1,
    )

    invoke_and_assert(
        command=["agent", "start", "-q", "hello", "-t", "blue"],
        expected_output_contains="Only one of `work_queues`, `regex`, or `tags` can be provided.",
        expected_code=1,
    )


def test_start_agent_with_regex_and_work_queue():
    invoke_and_assert(
        command=["agent", "start", "hello", "-r", "blue"],
        expected_output_contains="Only one of `work_queues`, `regex`, or `tags` can be provided.",
        expected_code=1,
    )

    invoke_and_assert(
        command=["agent", "start", "-q", "hello", "-r", "blue"],
        expected_output_contains="Only one of `work_queues`, `regex`, or `tags` can be provided.",
        expected_code=1,
    )
