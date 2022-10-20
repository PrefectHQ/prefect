from uuid import uuid4

import pendulum
import pydantic
import pytest

from prefect.orion import schemas
from prefect.orion.utilities.schemas import PrefectBaseModel


@pytest.mark.parametrize(
    "name",
    [
        "my-object",
        "my object",
        "my:object",
        "my;object",
        r"my\object",
        "my|object",
        "my⁉️object",
    ],
)
async def test_valid_names(name):
    assert schemas.core.Flow(name=name)
    assert schemas.core.Deployment(
        name=name,
        flow_id=uuid4(),
        manifest_path="file.json",
    )
    assert schemas.core.BlockDocument(
        name=name, block_schema_id=uuid4(), block_type_id=uuid4()
    )


@pytest.mark.parametrize(
    "name",
    [
        "my/object",
        r"my%object",
    ],
)
async def test_invalid_names(name):
    with pytest.raises(pydantic.ValidationError, match="contains an invalid character"):
        assert schemas.core.Flow(name=name)
    with pytest.raises(pydantic.ValidationError, match="contains an invalid character"):
        assert schemas.core.Deployment(
            name=name,
            flow_id=uuid4(),
            manifest_path="file.json",
        )
    with pytest.raises(pydantic.ValidationError, match="contains an invalid character"):
        assert schemas.core.BlockDocument(
            name=name, block_schema_id=uuid4(), block_type_id=uuid4()
        )


class TestBlockDocument:
    async def test_block_document_requires_name(self):
        with pytest.raises(
            ValueError, match="(Names must be provided for block documents.)"
        ):
            schemas.core.BlockDocument(block_schema_id=uuid4(), block_type_id=uuid4())

    async def test_anonymous_block_document_does_not_require_name(self):
        assert schemas.core.BlockDocument(
            block_schema_id=uuid4(), block_type_id=uuid4(), is_anonymous=True
        )


class TestFlowRunNotificationPolicy:
    async def test_message_template_variables_are_validated(self):
        with pytest.raises(
            pydantic.ValidationError,
            match="(Invalid template variable provided: 'bad_variable')",
        ):
            schemas.core.FlowRunNotificationPolicy(
                name="test",
                state_names=[],
                tags=[],
                block_document_id=uuid4(),
                message_template="This uses a {bad_variable}",
            )

    async def test_multiple_message_template_variables_are_validated(self):
        with pytest.raises(
            pydantic.ValidationError,
            match="(Invalid template variable provided: 'bad_variable')",
        ):
            schemas.core.FlowRunNotificationPolicy(
                name="test",
                state_names=[],
                tags=[],
                block_document_id=uuid4(),
                message_template="This contains {flow_run_id} and {bad_variable} and {another_bad_variable}",
            )


class TestFlowRunPolicy:
    class OldFlowRunPolicy(PrefectBaseModel):
        # Schemas ignore extras during normal execution, but raise errors during tests if not explicitly ignored.
        class Config:
            extra = "ignore"

        max_retries: int = 0
        retry_delay_seconds: float = 0

    async def test_flow_run_policy_is_backwards_compatible(self):
        """
        In version 2.1.1 and prior, the FlowRunPolicy schema required two properties,
        `max_retries` and `retry_delay_seconds`. These properties are deprecated.

        This test ensures old clients can load new FlowRunPolicySchemas. It can be removed
        when the corresponding properties are removed.
        """

        empty_new_policy = schemas.core.FlowRunPolicy()

        # should not raise an error
        self.OldFlowRunPolicy(**empty_new_policy.dict())

    async def test_flow_run_policy_populates_new_properties_from_deprecated(self):
        """
        In version 2.1.1 and prior, the FlowRunPolicy schema required two properties,
        `max_retries` and `retry_delay_seconds`. These properties are deprecated.

        This test ensures new servers correctly parse old FlowRunPolicySchemas. It can be removed
        when the corresponding properties are removed.
        """
        old_policy = self.OldFlowRunPolicy(max_retries=1, retry_delay_seconds=2)

        new_policy = schemas.core.FlowRunPolicy(**old_policy.dict())

        assert new_policy.retries == 1
        assert new_policy.retry_delay == 2


class TestTaskRunPolicy:
    class OldTaskRunPolicy(PrefectBaseModel):
        # Schemas ignore extras during normal execution, but raise errors during tests if not explicitly ignored.
        class Config:
            extra = "ignore"

        max_retries: int = 0
        retry_delay_seconds: float = 0

    async def test_task_run_policy_is_backwards_compatible(self):
        """
        In version 2.1.1 and prior, the TaskRunPolicy schema required two properties,
        `max_retries` and `retry_delay_seconds`. These properties are deprecated.

        This test ensures old clients can load new FlowRunPolicySchemas. It can be removed
        when the corresponding properties are removed.
        """
        empty_new_policy = schemas.core.TaskRunPolicy()
        # should not raise an error
        self.OldTaskRunPolicy(**empty_new_policy.dict())

    async def test_flow_run_policy_populates_new_properties_from_deprecated(self):
        """
        In version 2.1.1 and prior, the TaskRunPolicy schema required two properties,
        `max_retries` and `retry_delay_seconds`. These properties are deprecated.

        This test ensures new servers correctly parse old TaskRunPolicySchemas. It can be removed
        when the corresponding properties are removed.
        """
        old_policy = self.OldTaskRunPolicy(max_retries=1, retry_delay_seconds=2)

        new_policy = schemas.core.TaskRunPolicy(**old_policy.dict())

        assert new_policy.retries == 1
        assert new_policy.retry_delay == 2


class TestWorkQueueHealthPolicy:
    def test_health_policy_enforces_max_late_runs(self):
        policy = schemas.core.WorkQueueHealthPolicy(
            maximum_late_runs=1, maximum_seconds_since_last_polled=None
        )

        assert policy.evaluate_health_status(late_runs_count=0) is True
        assert policy.evaluate_health_status(late_runs_count=2) is False

    def test_health_policy_enforces_seconds_since_last_polled(self):
        policy = schemas.core.WorkQueueHealthPolicy(
            maximum_late_runs=None, maximum_seconds_since_last_polled=30
        )

        assert (
            policy.evaluate_health_status(
                late_runs_count=0, last_polled=pendulum.now("UTC")
            )
            is True
        )
        assert (
            policy.evaluate_health_status(
                late_runs_count=2, last_polled=pendulum.now("UTC").subtract(seconds=60)
            )
            is False
        )
        assert (
            policy.evaluate_health_status(late_runs_count=2, last_polled=None) is False
        )
