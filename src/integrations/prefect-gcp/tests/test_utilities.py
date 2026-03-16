from unittest.mock import Mock

from pydantic import VERSION as PYDANTIC_VERSION

if PYDANTIC_VERSION.startswith("2."):
    pass
else:
    pass

import pytest
from prefect_gcp.utilities import (
    Execution,
    Job,
    merge_labels_for_gcp,
    sanitize_labels_for_gcp,
)

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


class TestSanitizeLabelsForGcp:
    def test_dots_and_slashes_replaced(self):
        result = sanitize_labels_for_gcp({"prefect.io/flow-run-id": "abc-123"})
        assert result == {"prefect-io-flow-run-id": "abc-123"}

    def test_keys_and_values_lowercased(self):
        result = sanitize_labels_for_gcp({"MyKey": "MyValue"})
        assert result == {"mykey": "myvalue"}

    def test_values_truncated_to_63_chars(self):
        long_value = "a" * 100
        result = sanitize_labels_for_gcp({"key": long_value})
        assert len(result["key"]) == 63

    def test_empty_labels(self):
        assert sanitize_labels_for_gcp({}) == {}

    def test_typical_prefect_labels(self):
        labels = {
            "prefect.io/flow-run-id": "069b2be6-88cf-7155-8000-fb8956c7ebf3",
            "prefect.io/flow-run-name": "green-coati",
            "prefect.io/version": "3.2.1",
        }
        result = sanitize_labels_for_gcp(labels)
        assert result == {
            "prefect-io-flow-run-id": "069b2be6-88cf-7155-8000-fb8956c7ebf3",
            "prefect-io-flow-run-name": "green-coati",
            "prefect-io-version": "3-2-1",
        }

    def test_leading_digits_stripped_from_key(self):
        result = sanitize_labels_for_gcp({"1team": "value"})
        assert result == {"team": "value"}

    def test_leading_non_letter_chars_stripped_from_key(self):
        result = sanitize_labels_for_gcp({".team": "value", "-org": "value2"})
        assert result == {"team": "value", "org": "value2"}

    def test_key_empty_after_sanitization_is_dropped(self):
        result = sanitize_labels_for_gcp({"123": "value", "---": "value2"})
        assert result == {}


class TestMergeLabelsForGcp:
    def test_merges_prefect_and_existing(self):
        result = merge_labels_for_gcp(
            {"prefect.io/flow-run-id": "abc"},
            {"my-label": "val"},
        )
        assert result == {"prefect-io-flow-run-id": "abc", "my-label": "val"}

    def test_existing_labels_take_precedence(self):
        result = merge_labels_for_gcp(
            {"prefect.io/flow-run-id": "from-prefect"},
            {"prefect-io-flow-run-id": "override"},
        )
        assert result["prefect-io-flow-run-id"] == "override"

    def test_caps_at_64_labels_dropping_prefect_labels(self):
        existing = {f"existing-{i}": "v" for i in range(60)}
        prefect = {f"prefect.io/label-{i}": "v" for i in range(10)}
        result = merge_labels_for_gcp(prefect, existing)
        assert len(result) == 64
        # All 60 existing labels are preserved
        for key in existing:
            assert key in result

    def test_all_existing_preserved_even_above_64(self):
        existing = {f"existing-{i}": "v" for i in range(64)}
        prefect = {f"prefect.io/label-{i}": "v" for i in range(5)}
        result = merge_labels_for_gcp(prefect, existing)
        # All existing labels kept; all prefect labels dropped
        assert len(result) == 64
        assert result == existing


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
