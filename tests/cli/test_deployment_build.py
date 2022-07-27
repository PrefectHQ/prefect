from prefect.testing.cli import invoke_and_assert


def test_useful_message_when_flow_name_skipped():
    invoke_and_assert(
        ["deployment", "build", "./dog.py", "-n", "dog-deployment"],
        expected_output_contains=[
            "Your flow path must include the name of the function that is the entrypoint to your flow.",
            "Try ./dog.py:<flow_name> for your flow path.",
        ],
        expected_code=1,
    )
