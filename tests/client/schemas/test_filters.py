from prefect.client.schemas.filters import (
    FlowRunFilter,
    TaskRunFilter,
    TaskRunFilterState,
)


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
