from uuid import uuid4
import pendulum
import pytest
from prefect.orion.schemas import filters


@pytest.mark.parametrize(
    "TagsFilter",
    [filters.FlowFilterTags, filters.FlowRunFilterTags, filters.TaskRunFilterTags],
)
def test_tags_filter_validation_does_not_allow_all_and_is_null(TagsFilter):
    with pytest.raises(
        ValueError, match="Cannot provide tags all_ with is_null_ = True"
    ):
        TagsFilter(all_=["foo"], is_null_=True)


def test_deployment_ids_filter_validation_does_not_allow_any_and_is_null():
    with pytest.raises(
        ValueError, match="Cannot provide deployment ids any_ with is_null_ = True"
    ):
        filters.FlowRunFilterDeploymentIds(any_=[uuid4()], is_null_=True)


def test_parent_task_run_ids_filter_validation_does_not_allow_any_and_is_null():
    with pytest.raises(
        ValueError, match="Cannot provide parent task run ids any_ with is_null_ = True"
    ):
        filters.FlowRunFilterParentTaskRunIds(any_=[uuid4()], is_null_=True)


@pytest.mark.parametrize(
    "StartTimeFilter",
    [filters.FlowRunFilterStartTime, filters.TaskRunFilterStartTime],
)
def test_start_time_before_must_be_greater_than_after(StartTimeFilter):
    with pytest.raises(
        ValueError, match="Start time before_ must be greater than after_"
    ):
        StartTimeFilter(
            before_=pendulum.now("UTC"), after_=pendulum.now("UTC").add(days=1)
        )
