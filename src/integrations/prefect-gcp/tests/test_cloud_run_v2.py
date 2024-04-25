import pytest
from prefect_gcp.models.cloud_run_v2 import JobV2

jobs_return_value = {
    "name": "test-job-name",
    "uid": "uid-123",
    "generation": "1",
    "labels": {},
    "createTime": "create-time",
    "updateTime": "update-time",
    "deleteTime": "delete-time",
    "expireTime": "expire-time",
    "creator": "creator",
    "lastModifier": "last-modifier",
    "client": "client",
    "clientVersion": "client-version",
    "launchStage": "BETA",
    "binaryAuthorization": {},
    "template": {},
    "observedGeneration": "1",
    "terminalCondition": {},
    "conditions": [],
    "executionCount": 1,
    "latestCreatedExecution": {},
    "reconciling": True,
    "satisfiesPzs": False,
    "etag": "etag-123",
}


class TestJobV2:
    @pytest.mark.parametrize(
        "state,expected",
        [("CONDITION_SUCCEEDED", True), ("CONDITION_FAILED", False)],
    )
    def test_is_ready(self, state, expected):
        job = JobV2(
            name="test-job",
            uid="12345",
            generation="2",
            labels={},
            annotations={},
            createTime="2021-08-31T18:00:00Z",
            updateTime="2021-08-31T18:00:00Z",
            launchStage="BETA",
            binaryAuthorization={},
            template={},
            terminalCondition={
                "type": "Ready",
                "state": state,
            },
            conditions=[],
            executionCount=1,
            latestCreatedExecution={},
            reconciling=False,
            satisfiesPzs=False,
            etag="etag-12345",
        )

        assert job.is_ready() == expected

    def test_is_ready_raises_exception(self):
        job = JobV2(
            name="test-job",
            uid="12345",
            generation="2",
            labels={},
            annotations={},
            createTime="2021-08-31T18:00:00Z",
            updateTime="2021-08-31T18:00:00Z",
            launchStage="BETA",
            binaryAuthorization={},
            template={},
            terminalCondition={
                "type": "Ready",
                "state": "CONTAINER_FAILED",
                "reason": "ContainerMissing",
            },
            conditions=[],
            executionCount=1,
            latestCreatedExecution={},
            reconciling=False,
            satisfiesPzs=False,
            etag="etag-12345",
        )

        with pytest.raises(Exception):
            job.is_ready()

    @pytest.mark.parametrize(
        "terminal_condition,expected",
        [
            (
                {
                    "type": "Ready",
                    "state": "CONDITION_SUCCEEDED",
                },
                {
                    "type": "Ready",
                    "state": "CONDITION_SUCCEEDED",
                },
            ),
            (
                {
                    "type": "Failed",
                    "state": "CONDITION_FAILED",
                },
                {},
            ),
        ],
    )
    def test_get_ready_condition(self, terminal_condition, expected):
        job = JobV2(
            name="test-job",
            uid="12345",
            generation="2",
            labels={},
            annotations={},
            createTime="2021-08-31T18:00:00Z",
            updateTime="2021-08-31T18:00:00Z",
            launchStage="BETA",
            binaryAuthorization={},
            template={},
            terminalCondition=terminal_condition,
            conditions=[],
            executionCount=1,
            latestCreatedExecution={},
            reconciling=False,
            satisfiesPzs=False,
            etag="etag-12345",
        )

        assert job.get_ready_condition() == expected

    @pytest.mark.parametrize(
        "ready_condition,expected",
        [
            (
                {
                    "state": "CONTAINER_FAILED",
                    "reason": "ContainerMissing",
                },
                True,
            ),
            (
                {
                    "state": "CONDITION_SUCCEEDED",
                },
                False,
            ),
        ],
    )
    def test_is_missing_container(self, ready_condition, expected):
        job = JobV2(
            name="test-job",
            uid="12345",
            generation="2",
            labels={},
            annotations={},
            createTime="2021-08-31T18:00:00Z",
            updateTime="2021-08-31T18:00:00Z",
            launchStage="BETA",
            binaryAuthorization={},
            template={},
            terminalCondition={},
            conditions=[],
            executionCount=1,
            latestCreatedExecution={},
            reconciling=False,
            satisfiesPzs=False,
            etag="etag-12345",
        )

        assert job._is_missing_container(ready_condition=ready_condition) == expected


def remove_server_url_from_env(env):
    """
    For convenience since the testing database URL is non-deterministic.
    """
    return [
        env_var
        for env_var in env
        if env_var["name"]
        not in [
            "PREFECT_API_DATABASE_CONNECTION_URL",
            "PREFECT_ORION_DATABASE_CONNECTION_URL",
            "PREFECT_SERVER_DATABASE_CONNECTION_URL",
        ]
    ]
