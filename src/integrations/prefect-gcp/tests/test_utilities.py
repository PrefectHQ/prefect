from unittest.mock import Mock

from pydantic import VERSION as PYDANTIC_VERSION

if PYDANTIC_VERSION.startswith("2."):
    pass
else:
    pass

import pytest
from prefect_gcp.utilities import Execution, Job

executions_return_value = {
    "metadata": {"name": "test-name", "namespace": "test-namespace"},
    "spec": {"MySpec": "spec"},
    "status": {"logUri": "test-log-uri"},
}

jobs_return_value = {
    "metadata": {"name": "Test", "namespace": "test-namespace"},
    "spec": {"MySpec": "spec"},
    "status": {
        "conditions": [{"type": "Ready", "dog": "cat"}],
        "latestCreatedExecution": {"puppy": "kitty"},
    },
}


class MockExecution(Mock):
    call_count = 0

    def __init__(self, succeeded=False, *args, **kwargs):
        super().__init__()
        self.log_uri = "test_uri"
        self._succeeded = succeeded

    def is_running(self):
        MockExecution.call_count += 1

        if self.call_count > 2:
            return False
        return True

    def condition_after_completion(self):
        return {"message": "test"}

    def succeeded(self):
        return self._succeeded

    @classmethod
    def get(cls, *args, **kwargs):
        return cls()


class TestJob:
    @pytest.mark.parametrize(
        "ready_condition,expected_value",
        [({"status": "True"}, True), ({"status": "False"}, False), ({}, False)],
    )
    def test_is_ready(self, ready_condition, expected_value):
        job = Job(
            metadata={},
            spec={},
            status={},
            name="test",
            ready_condition=ready_condition,
            execution_status={},
        )
        assert job.is_ready() == expected_value

    @pytest.mark.parametrize(
        "status,expected_value",
        [
            ({}, {}),
            ({"conditions": []}, {}),
            ({"conditions": [{"type": "Dog", "val": "value"}]}, {}),
            (
                {"conditions": [{"type": "Ready", "val": "value"}]},
                {"type": "Ready", "val": "value"},
            ),
            (
                {
                    "conditions": [
                        {"type": "Dog", "val": "value"},
                        {"type": "Ready", "val": "value"},
                    ]
                },
                {"type": "Ready", "val": "value"},
            ),
        ],
    )
    def test_get_ready_condition(self, status, expected_value):
        assert Job._get_ready_condition({"status": status}) == expected_value

    @pytest.mark.parametrize(
        "status,expected_value",
        [
            ({}, {}),
            ({"latestCreatedExecution": {}}, {}),
            ({"latestCreatedExecution": {"some": "val"}}, {"some": "val"}),
        ],
    )
    def test_get_execution_status(self, status, expected_value):
        assert Job._get_execution_status({"status": status}) == expected_value

    @pytest.mark.parametrize(
        "execution_status,expected_value",
        [
            ({}, True),  # Has no execution
            (
                {"completionTimestamp": None},
                True,
            ),  # Has an execution with no completion timestamp
            (
                {"completionTimestamp": "Exists"},
                False,
            ),  # Has an execution and it has a completion timestamp
        ],
    )
    def test_has_execution_in_progress(self, execution_status, expected_value):
        job = Job(
            metadata={},
            spec={},
            status={},
            name="test",
            ready_condition={},
            execution_status=execution_status,
        )
        assert job.has_execution_in_progress() == expected_value


class TestExecution:
    def test_succeeded_responds_true(self):
        """Desired behavior: `succeeded()` should return true if execution.status
        contains a list element that is a dict with a key "type" and a value of
        "Completed" and a key "status" and a value of "True"
        """
        execution = Execution(
            name="Test",
            namespace="test-namespace",
            metadata={},
            spec={},
            status={"conditions": [{"type": "Completed", "status": "True"}]},
            log_uri="",
        )
        assert execution.succeeded()

    @pytest.mark.parametrize(
        "conditions",
        [
            [],
            [{"type": "Dog", "status": "True"}],
            [{"type": "Completed", "status": "False"}],
            [{"type": "Completed", "status": "Dog"}],
        ],
    )
    def test_succeeded_responds_false(self, conditions):
        """Desired behavior: `succeeded()` should return False if execution.status
        lacks a list element that is a dict with a key "type" and a value of
        "Completed" and a key "status" and a value of "True".

        This could be a situation where there is no element containing the key, or
        the element with the key has a status that is not "True".
        """
        execution = Execution(
            name="Test",
            namespace="test-namespace",
            metadata={},
            spec={},
            status={"conditions": conditions},
            log_uri="",
        )
        assert not execution.succeeded()

    @pytest.mark.parametrize(
        "status,expected_value", [({}, True), ({"completionTime": "xyz"}, False)]
    )
    def test_is_running(self, status, expected_value):
        """Desired behavior: `is_running()` should return True if there if
        execution.status lack a key "completionTime", otherwise return False
        """
        execution = Execution(
            name="Test",
            namespace="test-namespace",
            metadata={},
            spec={},
            status=status,
            log_uri="",
        )
        assert execution.is_running() == expected_value

    @pytest.mark.parametrize(
        "conditions, expected_value",
        [
            ([], None),
            ([{"type": "Dog", "status": "True"}], None),
            (
                [{"type": "Completed", "status": "False"}],
                {"type": "Completed", "status": "False"},
            ),
            (
                [
                    {"type": "Dog", "status": "True"},
                    {"type": "Completed", "status": "False"},
                ],
                {"type": "Completed", "status": "False"},
            ),
        ],
    )
    def test_condition_after_completion_returns_correct_condition(
        self, conditions, expected_value
    ):
        """Desired behavior: `condition_after_completion()`
        should return the list element from execution.status that contains a dict
        with a key "type" and a value of "Completed" if it exists, else None
        """
        execution = Execution(
            name="Test",
            namespace="test-namespace",
            metadata={},
            spec={},
            status={"conditions": conditions},
            log_uri="",
        )
        assert execution.condition_after_completion() == expected_value
