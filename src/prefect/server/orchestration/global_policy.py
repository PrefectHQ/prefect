"""
Bookkeeping logic that fires on every state transition.

For clarity, `GlobalFlowpolicy` and `GlobalTaskPolicy` contain all transition logic
implemented using [`BaseUniversalTransform`][prefect.server.orchestration.rules.BaseUniversalTransform].
None of these operations modify state, and regardless of what orchestration Prefect REST API might
enforce on a transition, the global policies contain Prefect's necessary bookkeeping.
Because these transforms record information about the validated state committed to the
state database, they should be the most deeply nested contexts in orchestration loop.
"""

from __future__ import annotations

from typing import Union, cast

from packaging.version import Version

import prefect.server.models as models
from prefect.server.database import orm_models
from prefect.server.orchestration.policies import BaseOrchestrationPolicy
from prefect.server.orchestration.rules import (
    BaseOrchestrationRule,
    BaseUniversalTransform,
    FlowOrchestrationContext,
    FlowRunUniversalTransform,
    GenericOrchestrationContext,
    OrchestrationContext,
    TaskOrchestrationContext,
    TaskRunUniversalTransform,
)
from prefect.server.schemas import core
from prefect.server.schemas.core import FlowRunPolicy


def COMMON_GLOBAL_TRANSFORMS() -> list[
    type[
        BaseUniversalTransform[
            orm_models.Run, Union[core.FlowRunPolicy, core.TaskRunPolicy]
        ]
    ]
]:
    return [
        SetRunStateType,
        SetRunStateName,
        SetRunStateTimestamp,
        SetStartTime,
        SetEndTime,
        IncrementRunTime,
        SetExpectedStartTime,
        SetNextScheduledStartTime,
        UpdateStateDetails,
    ]


class GlobalFlowPolicy(BaseOrchestrationPolicy[orm_models.FlowRun, core.FlowRunPolicy]):
    """
    Global transforms that run against flow-run-state transitions in priority order.

    These transforms are intended to run immediately before and after a state transition
    is validated.
    """

    @staticmethod
    def priority() -> list[
        Union[
            type[BaseUniversalTransform[orm_models.FlowRun, core.FlowRunPolicy]],
            type[BaseOrchestrationRule[orm_models.FlowRun, core.FlowRunPolicy]],
        ]
    ]:
        return cast(
            list[
                Union[
                    type[
                        BaseUniversalTransform[orm_models.FlowRun, core.FlowRunPolicy]
                    ],
                    type[BaseOrchestrationRule[orm_models.FlowRun, core.FlowRunPolicy]],
                ]
            ],
            COMMON_GLOBAL_TRANSFORMS(),
        ) + [
            UpdateSubflowParentTask,
            UpdateSubflowStateDetails,
            IncrementFlowRunCount,
            RemoveResumingIndicator,
        ]


class GlobalTaskPolicy(BaseOrchestrationPolicy[orm_models.TaskRun, core.TaskRunPolicy]):
    """
    Global transforms that run against task-run-state transitions in priority order.

    These transforms are intended to run immediately before and after a state transition
    is validated.
    """

    @staticmethod
    def priority() -> list[
        Union[
            type[BaseUniversalTransform[orm_models.TaskRun, core.TaskRunPolicy]],
            type[BaseOrchestrationRule[orm_models.TaskRun, core.TaskRunPolicy]],
        ]
    ]:
        return cast(
            list[
                Union[
                    type[
                        BaseUniversalTransform[orm_models.TaskRun, core.TaskRunPolicy]
                    ],
                    type[BaseOrchestrationRule[orm_models.TaskRun, core.TaskRunPolicy]],
                ]
            ],
            COMMON_GLOBAL_TRANSFORMS(),
        ) + [IncrementTaskRunCount]


class SetRunStateType(
    BaseUniversalTransform[
        orm_models.Run, Union[core.FlowRunPolicy, core.TaskRunPolicy]
    ]
):
    """
    Updates the state type of a run on a state transition.
    """

    async def before_transition(self, context: GenericOrchestrationContext) -> None:
        if self.nullified_transition():
            return

        # record the new state's type
        if context.proposed_state is not None:
            context.run.state_type = context.proposed_state.type


class SetRunStateName(
    BaseUniversalTransform[
        orm_models.Run, Union[core.FlowRunPolicy, core.TaskRunPolicy]
    ]
):
    """
    Updates the state name of a run on a state transition.
    """

    async def before_transition(self, context: GenericOrchestrationContext) -> None:
        if self.nullified_transition():
            return

        if context.proposed_state is not None:
            # record the new state's name
            context.run.state_name = context.proposed_state.name


class SetStartTime(
    BaseUniversalTransform[
        orm_models.Run, Union[core.FlowRunPolicy, core.TaskRunPolicy]
    ]
):
    """
    Records the time a run enters a running state for the first time.
    """

    async def before_transition(self, context: GenericOrchestrationContext) -> None:
        if self.nullified_transition():
            return

        if context.proposed_state is not None:
            # if entering a running state and no start time is set...
            if context.proposed_state.is_running() and context.run.start_time is None:
                # set the start time
                context.run.start_time = context.proposed_state.timestamp


class SetRunStateTimestamp(
    BaseUniversalTransform[
        orm_models.Run, Union[core.FlowRunPolicy, core.TaskRunPolicy]
    ]
):
    """
    Records the time a run changes states.
    """

    async def before_transition(self, context: GenericOrchestrationContext) -> None:
        if self.nullified_transition():
            return

        if context.proposed_state is not None:
            # record the new state's timestamp
            context.run.state_timestamp = context.proposed_state.timestamp


class SetEndTime(
    BaseUniversalTransform[
        orm_models.Run, Union[core.FlowRunPolicy, core.TaskRunPolicy]
    ]
):
    """
    Records the time a run enters a terminal state.

    With normal client usage, a run will not transition out of a terminal state.
    However, it's possible to force these transitions manually via the API. While
    leaving a terminal state, the end time will be unset.
    """

    async def before_transition(self, context: GenericOrchestrationContext) -> None:
        if self.nullified_transition():
            return

        if context.proposed_state is not None:
            # if exiting a final state for a non-final state...
            if (
                context.initial_state
                and context.initial_state.is_final()
                and not context.proposed_state.is_final()
            ):
                # clear the end time
                context.run.end_time = None

            # if entering a final state...
            if context.proposed_state.is_final():
                # if the run has a start time and no end time, give it one
                if context.run.start_time and not context.run.end_time:
                    context.run.end_time = context.proposed_state.timestamp


class IncrementRunTime(
    BaseUniversalTransform[
        orm_models.Run, Union[core.FlowRunPolicy, core.TaskRunPolicy]
    ]
):
    """
    Records the amount of time a run spends in the running state.
    """

    async def before_transition(self, context: GenericOrchestrationContext) -> None:
        if self.nullified_transition():
            return

        if context.proposed_state is not None:
            # if exiting a running state...
            if context.initial_state and context.initial_state.is_running():
                # increment the run time by the time spent in the previous state
                context.run.total_run_time += (
                    context.proposed_state.timestamp - context.initial_state.timestamp
                )


class IncrementFlowRunCount(FlowRunUniversalTransform):
    """
    Records the number of times a run enters a running state. For use with retries.
    """

    async def before_transition(
        self, context: OrchestrationContext[orm_models.FlowRun, core.FlowRunPolicy]
    ) -> None:
        if self.nullified_transition():
            return

        if context.proposed_state is not None:
            # if entering a running state...
            if context.proposed_state.is_running():
                # do not increment the run count if resuming a paused flow
                api_version = context.parameters.get("api-version", None)
                if api_version is None or api_version >= Version("0.8.4"):
                    if context.run.empirical_policy.resuming:
                        return

                # increment the run count
                context.run.run_count += 1


class RemoveResumingIndicator(
    BaseUniversalTransform[orm_models.FlowRun, core.FlowRunPolicy]
):
    """
    Removes the indicator on a flow run that marks it as resuming.
    """

    async def before_transition(
        self, context: OrchestrationContext[orm_models.FlowRun, core.FlowRunPolicy]
    ) -> None:
        if self.nullified_transition():
            return

        proposed_state = context.proposed_state

        api_version = context.parameters.get("api-version", None)
        if api_version is None or api_version >= Version("0.8.4"):
            if proposed_state is not None and (
                proposed_state.is_running() or proposed_state.is_final()
            ):
                if context.run.empirical_policy.resuming:
                    updated_policy = context.run.empirical_policy.model_dump()
                    updated_policy["resuming"] = False
                    context.run.empirical_policy = FlowRunPolicy(**updated_policy)


class IncrementTaskRunCount(TaskRunUniversalTransform):
    """
    Records the number of times a run enters a running state. For use with retries.
    """

    async def before_transition(
        self, context: OrchestrationContext[orm_models.TaskRun, core.TaskRunPolicy]
    ) -> None:
        if self.nullified_transition():
            return

        proposed_state = context.proposed_state

        # if entering a running state...
        if proposed_state is not None and proposed_state.is_running():
            # increment the run count
            context.run.run_count += 1


class SetExpectedStartTime(
    BaseUniversalTransform[
        orm_models.Run, Union[core.FlowRunPolicy, core.TaskRunPolicy]
    ]
):
    """
    Estimates the time a state is expected to start running if not set.

    For scheduled states, this estimate is simply the scheduled time. For other states,
    this is set to the time the proposed state was created by Prefect.
    """

    async def before_transition(self, context: GenericOrchestrationContext) -> None:
        if self.nullified_transition():
            return

        # set expected start time if this is the first state
        if not context.run.expected_start_time and context.proposed_state is not None:
            if context.proposed_state.is_scheduled():
                context.run.expected_start_time = (
                    context.proposed_state.state_details.scheduled_time
                )
            else:
                context.run.expected_start_time = context.proposed_state.timestamp


class SetNextScheduledStartTime(
    BaseUniversalTransform[
        orm_models.Run, Union[core.FlowRunPolicy, core.TaskRunPolicy]
    ]
):
    """
    Records the scheduled time on a run.

    When a run enters a scheduled state, `run.next_scheduled_start_time` is set to
    the state's scheduled time. When leaving a scheduled state,
    `run.next_scheduled_start_time` is unset.
    """

    async def before_transition(self, context: GenericOrchestrationContext) -> None:
        if self.nullified_transition():
            return

        # remove the next scheduled start time if exiting a scheduled state
        if context.initial_state and context.initial_state.is_scheduled():
            context.run.next_scheduled_start_time = None

        # set next scheduled start time if entering a scheduled state
        if context.proposed_state is not None and context.proposed_state.is_scheduled():
            context.run.next_scheduled_start_time = (
                context.proposed_state.state_details.scheduled_time
            )


class UpdateSubflowParentTask(
    BaseUniversalTransform[orm_models.FlowRun, core.FlowRunPolicy]
):
    """
    Whenever a subflow changes state, it must update its parent task run's state.
    """

    async def after_transition(
        self, context: OrchestrationContext[orm_models.FlowRun, core.FlowRunPolicy]
    ) -> None:
        if self.nullified_transition():
            return

        # only applies to flow runs with a parent task run id
        if (
            context.run.parent_task_run_id is not None
            and context.validated_state is not None
        ):
            # avoid mutation of the flow run state
            subflow_parent_task_state = context.validated_state.fresh_copy()

            # set the task's "child flow run id" to be the subflow run id
            subflow_parent_task_state.state_details.child_flow_run_id = context.run.id

            await models.task_runs.set_task_run_state(
                session=context.session,
                task_run_id=context.run.parent_task_run_id,
                state=subflow_parent_task_state,
                force=True,
            )


class UpdateSubflowStateDetails(
    BaseUniversalTransform[orm_models.FlowRun, core.FlowRunPolicy]
):
    """
    Update a child subflow state's references to a corresponding tracking task run id
    in the parent flow run
    """

    async def before_transition(
        self, context: OrchestrationContext[orm_models.FlowRun, core.FlowRunPolicy]
    ) -> None:
        if self.nullified_transition():
            return

        # only applies to flow runs with a parent task run id
        if (
            context.run.parent_task_run_id is not None
            and context.proposed_state is not None
        ):
            context.proposed_state.state_details.task_run_id = (
                context.run.parent_task_run_id
            )


class UpdateStateDetails(
    BaseUniversalTransform[
        orm_models.Run, Union[core.FlowRunPolicy, core.TaskRunPolicy]
    ]
):
    """
    Update a state's references to a corresponding flow- or task- run.
    """

    async def before_transition(
        self,
        context: GenericOrchestrationContext,
    ) -> None:
        if self.nullified_transition():
            return

        if isinstance(context, FlowOrchestrationContext):
            flow_run = await context.flow_run()
            context.proposed_state.state_details.flow_run_id = flow_run.id

        elif isinstance(context, TaskOrchestrationContext):
            task_run = await context.task_run()
            context.proposed_state.state_details.flow_run_id = task_run.flow_run_id
            context.proposed_state.state_details.task_run_id = task_run.id
