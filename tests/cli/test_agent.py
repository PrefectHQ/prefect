from uuid import UUID

import pytest

import prefect.exceptions
from prefect.orion import models
from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncutils import sync_compatible


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


def test_start_agent_with_tags():
    invoke_and_assert(
        command=["agent", "start", "-t", "blue"],
        expected_output="`tags` are deprecated. For backwards-compatibility with older versions of Prefect, this agent will target a work queue called `Agent queue blue`.",
        expected_code=1,
    )


def test_start_agent_with_multiple_tags():
    invoke_and_assert(
        command=["agent", "start", "-t", "red", "-t", "blue"],
        expected_output="`tags` are deprecated. For backwards-compatibility with older versions of Prefect, this agent will target a work queue called `Agent queue blue-red`.",
        expected_code=1,
    )
