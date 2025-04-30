from datetime import timedelta
from uuid import uuid4

import pytest
from pydantic import ConfigDict, ValidationError

from prefect.server import schemas
from prefect.server.utilities.schemas import PrefectBaseModel
from prefect.settings import PREFECT_API_TASK_CACHE_KEY_MAX_LENGTH, temporary_settings
from prefect.types._datetime import now


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
    with pytest.raises(ValidationError, match="String should match pattern"):
        assert schemas.core.Flow(name=name)
    with pytest.raises(ValidationError, match="String should match pattern"):
        assert schemas.core.Deployment(
            name=name,
            flow_id=uuid4(),
        )
    with pytest.raises(ValidationError, match="String should match pattern"):
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


class TestBlockDocumentReference:
    async def test_block_document_reference_different_parent_and_ref(self):
        same_id = uuid4()
        with pytest.raises(
            ValueError,
            match=(
                "`parent_block_document_id` and `reference_block_document_id` cannot be"
                " the same"
            ),
        ):
            schemas.core.BlockDocumentReference(
                parent_block_document_id=same_id,
                reference_block_document_id=same_id,
                name="name",
            )


class TestFlowRunPolicy:
    class OldFlowRunPolicy(PrefectBaseModel):
        # Schemas ignore extras during normal execution, but raise errors during tests if not explicitly ignored.
        model_config = ConfigDict(extra="ignore")

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
        self.OldFlowRunPolicy(**empty_new_policy.model_dump())

    async def test_flow_run_policy_populates_new_properties_from_deprecated(self):
        """
        In version 2.1.1 and prior, the FlowRunPolicy schema required two properties,
        `max_retries` and `retry_delay_seconds`. These properties are deprecated.

        This test ensures new servers correctly parse old FlowRunPolicySchemas. It can be removed
        when the corresponding properties are removed.
        """
        old_policy = self.OldFlowRunPolicy(max_retries=1, retry_delay_seconds=2)

        new_policy = schemas.core.FlowRunPolicy(**old_policy.model_dump())

        assert new_policy.retries == 1
        assert new_policy.retry_delay == 2


class TestTaskRunPolicy:
    class OldTaskRunPolicy(PrefectBaseModel):
        # Schemas ignore extras during normal execution, but raise errors during tests if not explicitly ignored.
        model_config = ConfigDict(extra="ignore")

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
        self.OldTaskRunPolicy(**empty_new_policy.model_dump())

    async def test_flow_run_policy_populates_new_properties_from_deprecated(self):
        """
        In version 2.1.1 and prior, the TaskRunPolicy schema required two properties,
        `max_retries` and `retry_delay_seconds`. These properties are deprecated.

        This test ensures new servers correctly parse old TaskRunPolicySchemas. It can be removed
        when the corresponding properties are removed.
        """
        old_policy = self.OldTaskRunPolicy(max_retries=1, retry_delay_seconds=2)

        new_policy = schemas.core.TaskRunPolicy(**old_policy.model_dump())

        assert new_policy.retries == 1
        assert new_policy.retry_delay == 2


class TestTaskRun:
    def test_task_run_cache_key_greater_than_user_configured_max_length(self):
        with temporary_settings({PREFECT_API_TASK_CACHE_KEY_MAX_LENGTH: 5}):
            cache_key_invalid_length = "X" * 6
            with pytest.raises(
                ValidationError,
                match="Cache key exceeded maximum allowed length",
            ):
                schemas.core.TaskRun(
                    id=uuid4(),
                    flow_run_id=uuid4(),
                    task_key="foo",
                    dynamic_key="0",
                    cache_key=cache_key_invalid_length,
                )

            with pytest.raises(
                ValidationError,
                match="Cache key exceeded maximum allowed length",
            ):
                schemas.actions.TaskRunCreate(
                    flow_run_id=uuid4(),
                    task_key="foo",
                    dynamic_key="0",
                    cache_key=cache_key_invalid_length,
                )

    def test_task_run_cache_key_within_user_configured_max_length(self):
        with temporary_settings({PREFECT_API_TASK_CACHE_KEY_MAX_LENGTH: 1000}):
            cache_key_valid_length = "X" * 1000
            schemas.core.TaskRun(
                id=uuid4(),
                flow_run_id=uuid4(),
                task_key="foo",
                dynamic_key="0",
                cache_key=cache_key_valid_length,
            )

            schemas.actions.TaskRunCreate(
                flow_run_id=uuid4(),
                task_key="foo",
                dynamic_key="0",
                cache_key=cache_key_valid_length,
            )

    def test_task_run_cache_key_greater_than_default_max_length(self):
        cache_key_invalid_length = "X" * 2001
        with pytest.raises(
            ValidationError, match="Cache key exceeded maximum allowed length"
        ):
            schemas.core.TaskRun(
                id=uuid4(),
                flow_run_id=uuid4(),
                task_key="foo",
                dynamic_key="0",
                cache_key=cache_key_invalid_length,
            )

        with pytest.raises(
            ValidationError, match="Cache key exceeded maximum allowed length"
        ):
            schemas.actions.TaskRunCreate(
                flow_run_id=uuid4(),
                task_key="foo",
                dynamic_key="0",
                cache_key=cache_key_invalid_length,
            )

    def test_task_run_cache_key_length_within_default_max_length(self):
        cache_key_valid_length = "X" * 2000
        schemas.core.TaskRun(
            id=uuid4(),
            flow_run_id=uuid4(),
            task_key="foo",
            dynamic_key="0",
            cache_key=cache_key_valid_length,
        )

        schemas.actions.TaskRunCreate(
            flow_run_id=uuid4(),
            task_key="foo",
            dynamic_key="0",
            cache_key=cache_key_valid_length,
        )


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
            policy.evaluate_health_status(late_runs_count=0, last_polled=now("UTC"))
            is True
        )
        assert (
            policy.evaluate_health_status(
                late_runs_count=2, last_polled=now("UTC") - timedelta(seconds=60)
            )
            is False
        )
        assert (
            policy.evaluate_health_status(late_runs_count=2, last_polled=None) is False
        )


class TestWorkPool:
    def test_more_helpful_validation_message_for_work_pools(self):
        with pytest.raises(ValidationError):
            schemas.core.WorkPool(name="test")

    async def test_valid_work_pool_default_queue_id(self):
        qid = uuid4()
        wp = schemas.core.WorkPool(name="test", type="test", default_queue_id=qid)
        assert wp.default_queue_id == qid


class TestArtifacts:
    async def test_validates_metadata_sizes(self):
        artifact = schemas.core.Artifact(
            metadata_={"a very long key": "x" * 5000, "a very short key": "o" * 10}
        )
        assert len(artifact.metadata_["a very short key"]) == 10
        assert len(artifact.metadata_["a very long key"]) < 5000
        assert len(artifact.metadata_["a very long key"]) == 503  # max length + "..."

    async def test_from_result_populates_type_key_and_description(self):
        # TODO: results received from the API should conform to a schema
        result = dict(
            some_string="abcdefghijklmnopqrstuvwxyz",
            artifact_key="the secret pa55word",
            artifact_type="a test result",
            artifact_description="the most remarkable word",
        )
        artifact = schemas.core.Artifact.from_result(result)
        assert artifact.key == "the secret pa55word"
        assert artifact.data["some_string"] == "abcdefghijklmnopqrstuvwxyz"
        assert artifact.type == "a test result"
        assert artifact.description == "the most remarkable word"

    async def test_from_result_compatible_with_older_result_payloads(self):
        result = dict(
            some_string="abcdefghijklmnopqrstuvwxyz",
        )
        artifact = schemas.core.Artifact.from_result(result)
        assert artifact.data["some_string"] == "abcdefghijklmnopqrstuvwxyz"
        assert artifact.type is None
        assert artifact.metadata_ is None

    @pytest.mark.parametrize("result", [1, "test", {"foo": "bar"}])
    async def test_from_result_compatible_with_arbitrary_json(self, result):
        artifact = schemas.core.Artifact.from_result(result)
        assert artifact.data == result
        assert artifact.type is None
        assert artifact.description is None
        assert artifact.metadata_ is None

    async def test_from_result_can_contain_arbitrary_fields(self):
        result = dict(
            first_field="chickens",
            second_field="cows",
            third_field="horses",
        )
        artifact = schemas.core.Artifact.from_result(result)
        assert artifact.data == result
        assert artifact.type is None
        assert artifact.metadata_ is None
