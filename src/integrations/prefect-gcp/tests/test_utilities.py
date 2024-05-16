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


def list_mock_calls(mock_client, assigned_calls=0):
    calls = []
    for call in mock_client.mock_calls:
        # mock `call.jobs().get()` results in two calls: `call.jobs()` and
        # `call.jobs().get()`, so we want to remove the first, smaller
        # call.
        if len(str(call).split(".")) > 2:
            calls.append(str(call))
    # assigning a return value to a call results in initial
    # mock calls which are not actually made
    actual_calls = calls[assigned_calls:]

    return actual_calls


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

    def test_get_calls_correct_methods(self, mock_client):
        """Desired behavior: should call jobs().get().execute() with correct
        job name and namespace
        """
        mock_client.jobs().get().execute.return_value = jobs_return_value
        Job.get(client=mock_client, namespace="my-project-id", job_name="my-job-name")
        desired_calls = [
            "call.jobs().get()",  # Used to setup mock return
            "call.jobs().get(name='namespaces/my-project-id/jobs/my-job-name')",
            "call.jobs().get().execute()",
        ]
        actual_calls = list_mock_calls(mock_client=mock_client)
        assert actual_calls == desired_calls

    def test_return_value_for_get(self, mock_client):
        """Desired behavior: should return a Job object populated with values from
        `jobs_return_value` test object
        """
        mock_client.jobs().get().execute.return_value = jobs_return_value
        res = Job.get(
            client=mock_client, namespace="my-project-id", job_name="my-job-name"
        )

        assert res.name == jobs_return_value["metadata"]["name"]
        assert res.metadata == jobs_return_value["metadata"]
        assert res.spec == jobs_return_value["spec"]
        assert res.status == jobs_return_value["status"]
        assert res.ready_condition == jobs_return_value["status"]["conditions"][0]
        assert (
            res.execution_status
            == jobs_return_value["status"]["latestCreatedExecution"]
        )

    def test_delete_job(self, mock_client):
        """
        Desired behavior: should call jobs().delete().execute() with correct
        job name and namespace
        """
        Job.delete(
            client=mock_client, namespace="my-project-id", job_name="my-job-name"
        )
        desired_calls = [
            "call.jobs().delete(name='namespaces/my-project-id/jobs/my-job-name')",
            "call.jobs().delete().execute()",
        ]
        actual_calls = list_mock_calls(mock_client=mock_client)
        assert actual_calls == desired_calls

    def test_run_job(self, mock_client):
        """
        Desired behavior: should call jobs().run().execute() with correct
        job name and namespace
        """
        Job.run(client=mock_client, namespace="my-project-id", job_name="my-job-name")
        desired_calls = [
            "call.jobs().run(name='namespaces/my-project-id/jobs/my-job-name')",
            "call.jobs().run().execute()",
        ]
        actual_calls = list_mock_calls(mock_client=mock_client)
        assert actual_calls == desired_calls

    def test_create_job(self, mock_client):
        """
        Desired behavior: should call jobs().create().execute() with correct
        namespace and body
        """
        Job.create(client=mock_client, namespace="my-project-id", body={"dog": "cat"})
        desired_calls_v1 = [
            "call.jobs().create(parent='namespaces/my-project-id', body={'dog': 'cat'})",  # noqa
            "call.jobs().create().execute()",
        ]
        # ordering is non-deterministic
        desired_calls_v2 = [
            "call.jobs().create(body={'dog': 'cat'}, parent='namespaces/my-project-id')",  # noqa
            "call.jobs().create().execute()",
        ]
        actual_calls = list_mock_calls(mock_client=mock_client)
        try:
            assert actual_calls == desired_calls_v1
        except AssertionError:
            assert actual_calls == desired_calls_v2


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

    def test_return_value_for_get(self, mock_client):
        """Desired behavior: should return an Execution object populated with values from
        `executions_return_value` test object
        """
        mock_client.executions().get().execute.return_value = executions_return_value
        res = Execution.get(
            client=mock_client,
            namespace="my-project-id",
            execution_name="test-execution-name",
        )

        assert res.name == executions_return_value["metadata"]["name"]
        assert res.namespace == executions_return_value["metadata"]["namespace"]
        assert res.metadata == executions_return_value["metadata"]
        assert res.spec == executions_return_value["spec"]
        assert res.status == executions_return_value["status"]
        assert res.log_uri == executions_return_value["status"]["logUri"]

    def test_get_calls_correct_methods(self, mock_client):
        """
        Desired behavior: should call executions().get().execute() with correct
        job name and namespace
        """
        mock_client.executions().get().execute.return_value = executions_return_value
        Execution.get(
            client=mock_client,
            namespace="my-project-id",
            execution_name="my-execution-name",
        )
        desired_calls = [
            "call.executions().get()",  # Used to setup mock return
            "call.executions().get(name='namespaces/my-project-id/executions/my-execution-name')",  # noqa
            "call.executions().get().execute()",
        ]
        actual_calls = list_mock_calls(mock_client=mock_client)
        assert actual_calls == desired_calls
