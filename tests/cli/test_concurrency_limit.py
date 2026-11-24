import pytest

from prefect.testing.cli import invoke_and_assert

pytestmark = pytest.mark.clear_db


def test_create_concurrency_limit():
    invoke_and_assert(
        command=["concurrency-limit", "create", "my-tag", "3"],
        expected_output_contains="Created concurrency limit with properties:",
        expected_code=0,
    )

    invoke_and_assert(
        command=["concurrency-limit", "inspect", "my-tag"],
        expected_output_contains="my-tag",
        expected_code=0,
    )


def test_create_concurrency_limit_rejects_negative_limit():
    invoke_and_assert(
        command=["concurrency-limit", "create", "my-tag", "-1"],
        expected_output_contains="The concurrency limit must be 0 or greater.",
        expected_code=1,
    )

    invoke_and_assert(
        command=["concurrency-limit", "inspect", "my-tag"],
        expected_output_contains="No concurrency limit found for the tag: my-tag",
        expected_code=1,
    )
