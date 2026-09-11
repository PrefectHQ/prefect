import pytest
from pydantic import ValidationError

from prefect.client.schemas.filters import (
    FlowFilter,
    FlowRunFilter,
    FlowRunFilterState,
    FlowRunFilterStateType,
    TaskRunFilter,
    TaskRunFilterState,
)
from prefect.client.schemas.objects import StateType


class TestFlowRunFilter:
    def test_rejects_unknown_top_level_fields(self):
        state_filter = FlowRunFilterState(
            type=FlowRunFilterStateType(any_=[StateType.RUNNING])
        )

        with pytest.raises(ValidationError) as exc_info:
            FlowRunFilter(type=state_filter)  # type: ignore[call-arg]

        error = exc_info.value.errors()[0]
        assert error["type"] == "extra_forbidden"
        assert error["loc"] == ("type",)

    def test_rejects_unknown_nested_fields(self):
        with pytest.raises(ValidationError) as exc_info:
            FlowRunFilter.model_validate(
                {"state": {"types": {"any_": [StateType.RUNNING]}}}
            )

        error = exc_info.value.errors()[0]
        assert error["type"] == "extra_forbidden"
        assert error["loc"] == ("state", "types")

    def test_accepts_known_fields(self):
        flow_run_filter = FlowRunFilter(
            state=FlowRunFilterState(
                type=FlowRunFilterStateType(any_=[StateType.RUNNING])
            )
        )
        assert flow_run_filter.state is not None
        assert flow_run_filter.state.type is not None
        assert flow_run_filter.state.type.any_ == [StateType.RUNNING]

    def test_other_filter_families_remain_permissive(self):
        assert FlowFilter(type="ignored").model_dump(exclude_none=True) == {  # type: ignore[call-arg]
            "operator": "and_"
        }
        assert TaskRunFilter(type="ignored").model_dump(exclude_none=True) == {  # type: ignore[call-arg]
            "operator": "and_"
        }


class TestTaskRunFilterState:
    def test_can_be_constructed_without_arguments(self):
        state_filter = TaskRunFilterState()
        assert state_filter.type is None
        assert state_filter.name is None

    def test_can_filter_on_state_type_alone(self):
        task_run_filter = TaskRunFilter.model_validate(
            {"state": {"type": {"any_": ["COMPLETED"]}}}
        )
        assert task_run_filter.state is not None
        assert task_run_filter.state.name is None

    def test_can_filter_on_state_name_alone(self):
        task_run_filter = TaskRunFilter.model_validate(
            {"state": {"name": {"any_": ["Completed"]}}}
        )
        assert task_run_filter.state is not None
        assert task_run_filter.state.type is None

    def test_matches_flow_run_filter_state(self):
        payload = {"state": {"type": {"any_": ["COMPLETED"]}}}
        assert (
            TaskRunFilter.model_validate(payload).state.type.any_
            == FlowRunFilter.model_validate(payload).state.type.any_
        )
