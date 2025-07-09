"""
Orchestration logic that fires on state transitions.

`CoreFlowPolicy` and `CoreTaskPolicy` contain all default orchestration rules that
Prefect enforces on a state transition.
"""

from __future__ import annotations

import datetime
import math
from typing import Any, Union, cast
from uuid import uuid4

import sqlalchemy as sa
from packaging.version import Version
from sqlalchemy import select

from prefect.logging import get_logger
from prefect.server import models
from prefect.server.database import PrefectDBInterface, orm_models
from prefect.server.database.dependencies import db_injector
from prefect.server.exceptions import ObjectNotFoundError
from prefect.server.models import concurrency_limits, concurrency_limits_v2, deployments
from prefect.server.orchestration.policies import (
    FlowRunOrchestrationPolicy,
    TaskRunOrchestrationPolicy,
)
from prefect.server.orchestration.rules import (
    ALL_ORCHESTRATION_STATES,
    TERMINAL_STATES,
    BaseOrchestrationRule,
    BaseUniversalTransform,
    FlowOrchestrationContext,
    FlowRunOrchestrationRule,
    FlowRunUniversalTransform,
    GenericOrchestrationRule,
    OrchestrationContext,
    TaskRunOrchestrationRule,
    TaskRunUniversalTransform,
)
from prefect.server.schemas import core, filters, states
from prefect.server.schemas.states import StateType
from prefect.server.task_queue import TaskQueue
from prefect.settings import (
    PREFECT_API_TASK_CACHE_KEY_MAX_LENGTH,
    PREFECT_DEPLOYMENT_CONCURRENCY_SLOT_WAIT_SECONDS,
    PREFECT_TASK_RUN_TAG_CONCURRENCY_SLOT_WAIT_SECONDS,
)
from prefect.types._datetime import now
from prefect.utilities.math import clamped_poisson_interval

from .instrumentation_policies import InstrumentFlowRunStateTransitions


class CoreFlowPolicyWithoutDeploymentConcurrency(FlowRunOrchestrationPolicy):
    """
    Orchestration rules that run against flow-run-state transitions in priority order.
    """

    @staticmethod
    def priority() -> list[
        Union[
            type[BaseUniversalTransform[orm_models.FlowRun, core.FlowRunPolicy],],
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
            [
                PreventDuplicateTransitions,
                HandleFlowTerminalStateTransitions,
                EnforceCancellingToCancelledTransition,
                BypassCancellingFlowRunsWithNoInfra,
                PreventPendingTransitions,
                EnsureOnlyScheduledFlowsMarkedLate,
                HandlePausingFlows,
                HandleResumingPausedFlows,
                CopyScheduledTime,
                WaitForScheduledTime,
                RetryFailedFlows,
                InstrumentFlowRunStateTransitions,
            ],
        )


class CoreFlowPolicy(FlowRunOrchestrationPolicy):
    """
    Orchestration rules that run against flow-run-state transitions in priority order.
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
            [
                PreventDuplicateTransitions,
                HandleFlowTerminalStateTransitions,
                EnforceCancellingToCancelledTransition,
                BypassCancellingFlowRunsWithNoInfra,
                PreventPendingTransitions,
                SecureFlowConcurrencySlots,
                EnsureOnlyScheduledFlowsMarkedLate,
                HandlePausingFlows,
                HandleResumingPausedFlows,
                CopyScheduledTime,
                WaitForScheduledTime,
                RetryFailedFlows,
                InstrumentFlowRunStateTransitions,
                ReleaseFlowConcurrencySlots,
            ],
        )


class CoreTaskPolicy(TaskRunOrchestrationPolicy):
    """
    Orchestration rules that run against task-run-state transitions in priority order.
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
            [
                CacheRetrieval,
                HandleTaskTerminalStateTransitions,
                PreventRunningTasksFromStoppedFlows,
                SecureTaskConcurrencySlots,  # retrieve cached states even if slots are full
                CopyScheduledTime,
                WaitForScheduledTime,
                RetryFailedTasks,
                RenameReruns,
                UpdateFlowRunTrackerOnTasks,
                CacheInsertion,
                ReleaseTaskConcurrencySlots,
            ],
        )


class ClientSideTaskOrchestrationPolicy(TaskRunOrchestrationPolicy):
    """
    Orchestration rules that run against task-run-state transitions in priority order,
    specifically for clients doing client-side orchestration.
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
            [
                CacheRetrieval,
                HandleTaskTerminalStateTransitions,
                PreventRunningTasksFromStoppedFlows,
                CopyScheduledTime,
                WaitForScheduledTime,
                RetryFailedTasks,
                RenameReruns,
                UpdateFlowRunTrackerOnTasks,
                CacheInsertion,
                ReleaseTaskConcurrencySlots,
            ],
        )


class BackgroundTaskPolicy(TaskRunOrchestrationPolicy):
    """
    Orchestration rules that run against task-run-state transitions in priority order.
    """

    @staticmethod
    def priority() -> list[
        type[BaseUniversalTransform[orm_models.TaskRun, core.TaskRunPolicy]]
        | type[BaseOrchestrationRule[orm_models.TaskRun, core.TaskRunPolicy]]
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
            [
                PreventPendingTransitions,
                CacheRetrieval,
                HandleTaskTerminalStateTransitions,
                # SecureTaskConcurrencySlots,  # retrieve cached states even if slots are full
                CopyScheduledTime,
                CopyTaskParametersID,
                WaitForScheduledTime,
                RetryFailedTasks,
                RenameReruns,
                UpdateFlowRunTrackerOnTasks,
                CacheInsertion,
                ReleaseTaskConcurrencySlots,
                EnqueueScheduledTasks,
            ],
        )


class MinimalFlowPolicy(FlowRunOrchestrationPolicy):
    @staticmethod
    def priority() -> list[
        Union[
            type[BaseUniversalTransform[orm_models.FlowRun, core.FlowRunPolicy]],
            type[BaseOrchestrationRule[orm_models.FlowRun, core.FlowRunPolicy]],
        ]
    ]:
        return [
            BypassCancellingFlowRunsWithNoInfra,  # cancel scheduled or suspended runs from the UI
            InstrumentFlowRunStateTransitions,
            ReleaseFlowConcurrencySlots,
        ]


class MarkLateRunsPolicy(FlowRunOrchestrationPolicy):
    @staticmethod
    def priority() -> list[
        Union[
            type[BaseUniversalTransform[orm_models.FlowRun, core.FlowRunPolicy]],
            type[BaseOrchestrationRule[orm_models.FlowRun, core.FlowRunPolicy]],
        ]
    ]:
        return [
            EnsureOnlyScheduledFlowsMarkedLate,
            InstrumentFlowRunStateTransitions,
        ]


class MinimalTaskPolicy(TaskRunOrchestrationPolicy):
    @staticmethod
    def priority() -> list[
        Union[
            type[BaseUniversalTransform[orm_models.TaskRun, core.TaskRunPolicy]],
            type[BaseOrchestrationRule[orm_models.TaskRun, core.TaskRunPolicy]],
        ]
    ]:
        return [
            ReleaseTaskConcurrencySlots,  # always release concurrency slots
        ]


class SecureTaskConcurrencySlots(TaskRunOrchestrationRule):
    """
    Checks relevant concurrency slots are available before entering a Running state.

    This rule checks if concurrency limits have been set on the tags associated with a
    TaskRun. If so, a concurrency slot will be secured against each concurrency limit
    before being allowed to transition into a running state. If a concurrency limit has
    been reached, the client will be instructed to delay the transition for the duration
    specified by the "PREFECT_TASK_RUN_TAG_CONCURRENCY_SLOT_WAIT_SECONDS" setting
    before trying again. If the concurrency limit set on a tag is 0, the transition will
    be aborted to prevent deadlocks.
    """

    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = {StateType.RUNNING}

    async def before_transition(
        self,
        initial_state: states.State[Any] | None,
        proposed_state: states.State[Any] | None,
        context: OrchestrationContext[orm_models.TaskRun, core.TaskRunPolicy],
    ) -> None:
        self._applied_limits: list[str] = []
        filtered_limits = (
            await concurrency_limits.filter_concurrency_limits_for_orchestration(
                context.session, tags=context.run.tags
            )
        )
        run_limits = {limit.tag: limit for limit in filtered_limits}
        for tag, cl in run_limits.items():
            limit = cl.concurrency_limit
            if limit == 0:
                # limits of 0 will deadlock, and the transition needs to abort
                for stale_tag in self._applied_limits:
                    stale_limit = run_limits.get(stale_tag, None)
                    if stale_limit:
                        active_slots: set[str] = set(stale_limit.active_slots)
                        active_slots.discard(str(context.run.id))
                        stale_limit.active_slots = list(active_slots)

                await self.abort_transition(
                    reason=(
                        f'The concurrency limit on tag "{tag}" is 0 and will deadlock'
                        " if the task tries to run again."
                    ),
                )
            elif len(cl.active_slots) >= limit:
                # if the limit has already been reached, delay the transition
                for stale_tag in self._applied_limits:
                    stale_limit = run_limits.get(stale_tag, None)
                    if stale_limit:
                        active_slots = set(stale_limit.active_slots)
                        active_slots.discard(str(context.run.id))
                        stale_limit.active_slots = list(active_slots)

                await self.delay_transition(
                    PREFECT_TASK_RUN_TAG_CONCURRENCY_SLOT_WAIT_SECONDS.value(),
                    f"Concurrency limit for the {tag} tag has been reached",
                )
            else:
                # log the TaskRun ID to active_slots
                self._applied_limits.append(tag)
                active_slots = set(cl.active_slots)
                active_slots.add(str(context.run.id))
                cl.active_slots = list(active_slots)

    async def cleanup(
        self,
        initial_state: states.State[Any] | None,
        validated_state: states.State[Any] | None,
        context: OrchestrationContext[orm_models.TaskRun, core.TaskRunPolicy],
    ) -> None:
        for tag in self._applied_limits:
            cl = await concurrency_limits.read_concurrency_limit_by_tag(
                context.session, tag
            )
            if cl:
                active_slots = set(cl.active_slots)
                active_slots.discard(str(context.run.id))
                cl.active_slots = list(active_slots)


class ReleaseTaskConcurrencySlots(TaskRunUniversalTransform):
    """
    Releases any concurrency slots held by a run upon exiting a Running or
    Cancelling state.
    """

    async def after_transition(
        self,
        context: OrchestrationContext[orm_models.TaskRun, core.TaskRunPolicy],
    ) -> None:
        if self.nullified_transition():
            return

        if context.validated_state and context.validated_state.type not in [
            states.StateType.RUNNING,
            states.StateType.CANCELLING,
        ]:
            filtered_limits = (
                await concurrency_limits.filter_concurrency_limits_for_orchestration(
                    context.session, tags=context.run.tags
                )
            )
            run_limits = {limit.tag: limit for limit in filtered_limits}
            for cl in run_limits.values():
                active_slots = set(cl.active_slots)
                active_slots.discard(str(context.run.id))
                cl.active_slots = list(active_slots)


class SecureFlowConcurrencySlots(FlowRunOrchestrationRule):
    """
    Enforce deployment concurrency limits.

    This rule enforces concurrency limits on deployments. If a deployment has a concurrency limit,
    this rule will prevent more than that number of flow runs from being submitted concurrently
    based on the concurrency limit behavior configured for the deployment.

    We use the PENDING state as the target transition because this allows workers to secure a slot
    before provisioning dynamic infrastructure to run a flow. If a slot isn't available, the worker
    won't provision infrastructure.
    """

    FROM_STATES = ALL_ORCHESTRATION_STATES - {
        states.StateType.PENDING,
        states.StateType.RUNNING,
        states.StateType.CANCELLING,
    }
    TO_STATES = {states.StateType.PENDING}

    async def before_transition(  # type: ignore
        self,
        initial_state: states.State[Any] | None,
        proposed_state: states.State[Any] | None,
        context: FlowOrchestrationContext,
    ) -> None:
        if not context.session or not context.run.deployment_id:
            return

        deployment = await deployments.read_deployment(
            session=context.session,
            deployment_id=context.run.deployment_id,
        )
        if not deployment:
            await self.abort_transition("Deployment not found.")
            return

        if (
            not deployment.global_concurrency_limit
            or not deployment.concurrency_limit_id
        ):
            return

        if deployment.global_concurrency_limit.limit == 0:
            await self.abort_transition(
                "The deployment concurrency limit is 0. The flow will deadlock if submitted again."
            )
            return

        acquired = await concurrency_limits_v2.bulk_increment_active_slots(
            session=context.session,
            concurrency_limit_ids=[deployment.concurrency_limit_id],
            slots=1,
        )

        if not acquired:
            concurrency_options = (
                deployment.concurrency_options
                or core.ConcurrencyOptions(
                    collision_strategy=core.ConcurrencyLimitStrategy.ENQUEUE
                )
            )

            if (
                concurrency_options.collision_strategy
                == core.ConcurrencyLimitStrategy.ENQUEUE
            ):
                await self.reject_transition(
                    state=states.Scheduled(
                        name="AwaitingConcurrencySlot",
                        scheduled_time=now("UTC")
                        + datetime.timedelta(
                            seconds=PREFECT_DEPLOYMENT_CONCURRENCY_SLOT_WAIT_SECONDS.value()
                        ),
                    ),
                    reason="Deployment concurrency limit reached.",
                )
            elif (
                concurrency_options.collision_strategy
                == core.ConcurrencyLimitStrategy.CANCEL_NEW
            ):
                await self.reject_transition(
                    state=states.Cancelled(
                        message="Deployment concurrency limit reached."
                    ),
                    reason="Deployment concurrency limit reached.",
                )

    async def cleanup(  # type: ignore
        self,
        initial_state: states.State[Any] | None,
        validated_state: states.State[Any] | None,
        context: FlowOrchestrationContext,
    ) -> None:
        logger = get_logger()
        if not context.session or not context.run.deployment_id:
            return

        try:
            deployment = await deployments.read_deployment(
                session=context.session,
                deployment_id=context.run.deployment_id,
            )

            if not deployment or not deployment.concurrency_limit_id:
                return

            await concurrency_limits_v2.bulk_decrement_active_slots(
                session=context.session,
                concurrency_limit_ids=[deployment.concurrency_limit_id],
                slots=1,
            )
        except Exception as e:
            logger.error(f"Error releasing concurrency slots on cleanup: {e}")


class ReleaseFlowConcurrencySlots(FlowRunUniversalTransform):
    """
    Releases deployment concurrency slots held by a flow run.

    This rule releases a concurrency slot for a deployment when a flow run
    transitions out of the Running or Cancelling state.
    """

    async def after_transition(
        self,
        context: OrchestrationContext[orm_models.FlowRun, core.FlowRunPolicy],
    ) -> None:
        if self.nullified_transition():
            return

        initial_state_type = (
            context.initial_state.type if context.initial_state else None
        )
        proposed_state_type = (
            context.proposed_state.type if context.proposed_state else None
        )

        # Check if the transition is valid for releasing concurrency slots.
        # This should happen within `after_transition` because BaseUniversalTransforms
        # don't know how to "fizzle" themselves if they encounter a transition that
        # shouldn't apply to them, even if they use FROM_STATES and TO_STATES.
        if not (
            initial_state_type
            in {
                states.StateType.RUNNING,
                states.StateType.CANCELLING,
                states.StateType.PENDING,
            }
            and proposed_state_type
            not in {
                states.StateType.PENDING,
                states.StateType.RUNNING,
                states.StateType.CANCELLING,
            }
        ):
            return
        if not context.session or not context.run.deployment_id:
            return

        deployment = await deployments.read_deployment(
            session=context.session,
            deployment_id=context.run.deployment_id,
        )
        if not deployment or not deployment.concurrency_limit_id:
            return

        await concurrency_limits_v2.bulk_decrement_active_slots(
            session=context.session,
            concurrency_limit_ids=[deployment.concurrency_limit_id],
            slots=1,
        )


class CacheInsertion(TaskRunOrchestrationRule):
    """
    Caches completed states with cache keys after they are validated.
    """

    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = {StateType.COMPLETED}

    async def before_transition(
        self,
        initial_state: states.State[Any] | None,
        proposed_state: states.State[Any] | None,
        context: OrchestrationContext[orm_models.TaskRun, core.TaskRunPolicy],
    ) -> None:
        if proposed_state is None:
            return

        cache_key = proposed_state.state_details.cache_key
        if cache_key and len(cache_key) > PREFECT_API_TASK_CACHE_KEY_MAX_LENGTH.value():
            await self.reject_transition(
                state=proposed_state,
                reason=f"Cache key exceeded maximum allowed length of {PREFECT_API_TASK_CACHE_KEY_MAX_LENGTH.value()} characters.",
            )
            return

    @db_injector
    async def after_transition(
        self,
        db: PrefectDBInterface,
        initial_state: states.State[Any] | None,
        validated_state: states.State[Any] | None,
        context: OrchestrationContext[orm_models.TaskRun, core.TaskRunPolicy],
    ) -> None:
        if not validated_state or not context.session:
            return

        cache_key = validated_state.state_details.cache_key
        if cache_key:
            new_cache_item = db.TaskRunStateCache(
                cache_key=cache_key,
                cache_expiration=validated_state.state_details.cache_expiration,
                task_run_state_id=validated_state.id,
            )
            context.session.add(new_cache_item)


class CacheRetrieval(TaskRunOrchestrationRule):
    """
    Rejects running states if a completed state has been cached.

    This rule rejects transitions into a running state with a cache key if the key
    has already been associated with a completed state in the cache table. The client
    will be instructed to transition into the cached completed state instead.
    """

    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = {StateType.RUNNING}

    @db_injector
    async def before_transition(
        self,
        db: PrefectDBInterface,
        initial_state: states.State[Any] | None,
        proposed_state: states.State[Any] | None,
        context: OrchestrationContext[orm_models.TaskRun, core.TaskRunPolicy],
    ) -> None:
        if not proposed_state:
            return

        cache_key = proposed_state.state_details.cache_key
        if cache_key and not proposed_state.state_details.refresh_cache:
            # Check for cached states matching the cache key
            cached_state_id = (
                select(db.TaskRunStateCache.task_run_state_id)
                .where(
                    sa.and_(
                        db.TaskRunStateCache.cache_key == cache_key,
                        sa.or_(
                            db.TaskRunStateCache.cache_expiration.is_(None),
                            db.TaskRunStateCache.cache_expiration > now("UTC"),
                        ),
                    ),
                )
                .order_by(db.TaskRunStateCache.created.desc())
                .limit(1)
            ).scalar_subquery()
            query = select(db.TaskRunState).where(db.TaskRunState.id == cached_state_id)
            cached_state = (await context.session.execute(query)).scalar()
            if cached_state:
                new_state = cached_state.as_state().fresh_copy()
                new_state.name = "Cached"
                await self.reject_transition(
                    state=new_state, reason="Retrieved state from cache"
                )


class RetryFailedFlows(FlowRunOrchestrationRule):
    """
    Rejects failed states and schedules a retry if the retry limit has not been reached.

    This rule rejects transitions into a failed state if `retries` has been
    set and the run count has not reached the specified limit. The client will be
    instructed to transition into a scheduled state to retry flow execution.
    """

    FROM_STATES = {StateType.RUNNING}
    TO_STATES = {StateType.FAILED}

    async def before_transition(
        self,
        initial_state: states.State[Any] | None,
        proposed_state: states.State[Any] | None,
        context: OrchestrationContext[orm_models.FlowRun, core.FlowRunPolicy],
    ) -> None:
        if initial_state is None or proposed_state is None:
            return

        run_settings = context.run_settings
        run_count = context.run.run_count

        if run_settings.retries is None or run_count > run_settings.retries:
            # Clear retry type to allow for future infrastructure level retries (e.g. via the UI)
            updated_policy = context.run.empirical_policy.model_dump()
            updated_policy["retry_type"] = None
            context.run.empirical_policy = core.FlowRunPolicy(**updated_policy)

            return  # Retry count exceeded, allow transition to failed

        scheduled_start_time = now("UTC") + datetime.timedelta(
            seconds=run_settings.retry_delay or 0
        )

        # support old-style flow run retries for older clients
        # older flow retries require us to loop over failed tasks to update their state
        # this is not required after API version 0.8.3
        api_version = context.parameters.get("api-version", None)
        if api_version and api_version < Version("0.8.3"):
            failed_task_runs = await models.task_runs.read_task_runs(
                context.session,
                flow_run_filter=filters.FlowRunFilter(
                    id=filters.FlowRunFilterId(any_=[context.run.id])
                ),
                task_run_filter=filters.TaskRunFilter(
                    state=filters.TaskRunFilterState(
                        type=filters.TaskRunFilterStateType(any_=[StateType.FAILED])
                    )
                ),
            )
            for run in failed_task_runs:
                await models.task_runs.set_task_run_state(
                    context.session,
                    run.id,
                    state=states.AwaitingRetry(scheduled_time=scheduled_start_time),
                    force=True,
                )
                # Reset the run count so that the task run retries still work correctly
                run.run_count = 0

        # Reset pause metadata on retry
        # Pauses as a concept only exist after API version 0.8.4
        api_version = context.parameters.get("api-version", None)
        if api_version is None or api_version >= Version("0.8.4"):
            updated_policy = context.run.empirical_policy.model_dump()
            updated_policy["resuming"] = False
            updated_policy["pause_keys"] = set()
            updated_policy["retry_type"] = "in_process"
            context.run.empirical_policy = core.FlowRunPolicy(**updated_policy)

        # Generate a new state for the flow
        retry_state = states.AwaitingRetry(
            scheduled_time=scheduled_start_time,
            message=proposed_state.message,
            data=proposed_state.data,
        )
        await self.reject_transition(state=retry_state, reason="Retrying")


class RetryFailedTasks(TaskRunOrchestrationRule):
    """
    Rejects failed states and schedules a retry if the retry limit has not been reached.

    This rule rejects transitions into a failed state if `retries` has been
    set, the run count has not reached the specified limit, and the client
    asserts it is a retriable task run. The client will be instructed to
    transition into a scheduled state to retry task execution.
    """

    FROM_STATES = {StateType.RUNNING}
    TO_STATES = {StateType.FAILED}

    async def before_transition(
        self,
        initial_state: states.State[Any] | None,
        proposed_state: states.State[Any] | None,
        context: OrchestrationContext[orm_models.TaskRun, core.TaskRunPolicy],
    ) -> None:
        if initial_state is None or proposed_state is None:
            return

        run_settings = context.run_settings
        run_count = context.run.run_count
        delay = run_settings.retry_delay

        if isinstance(delay, list):
            base_delay = delay[min(run_count - 1, len(delay) - 1)]
        else:
            base_delay = delay or 0

        # guard against negative relative jitter inputs
        if run_settings.retry_jitter_factor:
            delay = clamped_poisson_interval(
                base_delay, clamping_factor=run_settings.retry_jitter_factor
            )
        else:
            delay = base_delay

        # set by user to conditionally retry a task using @task(retry_condition_fn=...)
        if getattr(proposed_state.state_details, "retriable", True) is False:
            return

        if run_settings.retries is not None and run_count <= run_settings.retries:
            retry_state = states.AwaitingRetry(
                scheduled_time=now("UTC") + datetime.timedelta(seconds=delay),
                message=proposed_state.message,
                data=proposed_state.data,
            )
            await self.reject_transition(state=retry_state, reason="Retrying")


class EnqueueScheduledTasks(TaskRunOrchestrationRule):
    """
    Enqueues background task runs when they are scheduled
    """

    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = {StateType.SCHEDULED}

    async def after_transition(
        self,
        initial_state: states.State[Any] | None,
        validated_state: states.State[Any] | None,
        context: OrchestrationContext[orm_models.TaskRun, core.TaskRunPolicy],
    ) -> None:
        if not validated_state:
            # Only if the transition was valid
            return

        if not validated_state.state_details.deferred:
            # Only for tasks that are deferred
            return

        task_run: core.TaskRun = core.TaskRun.model_validate(context.run)
        queue: TaskQueue = TaskQueue.for_key(task_run.task_key)

        if validated_state.name == "AwaitingRetry":
            await queue.retry(task_run)
        else:
            await queue.enqueue(task_run)


class RenameReruns(GenericOrchestrationRule):
    """
    Name the states if they have run more than once.

    In the special case where the initial state is an "AwaitingRetry" scheduled state,
    the proposed state will be renamed to "Retrying" instead.
    """

    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = {StateType.RUNNING}

    async def before_transition(
        self,
        initial_state: states.State[Any] | None,
        proposed_state: states.State[Any] | None,
        context: OrchestrationContext[
            orm_models.Run, core.TaskRunPolicy | core.FlowRunPolicy
        ],
    ) -> None:
        if initial_state is None or proposed_state is None:
            return

        run_count = context.run.run_count
        if run_count > 0:
            if initial_state.name == "AwaitingRetry":
                await self.rename_state("Retrying")
            else:
                await self.rename_state("Rerunning")


class CopyScheduledTime(
    BaseOrchestrationRule[orm_models.Run, Union[core.TaskRunPolicy, core.FlowRunPolicy]]
):
    """
    Ensures scheduled time is copied from scheduled states to pending states.

    If a new scheduled time has been proposed on the pending state, the scheduled time
    on the scheduled state will be ignored.
    """

    FROM_STATES = {StateType.SCHEDULED}
    TO_STATES = {StateType.PENDING}

    async def before_transition(
        self,
        initial_state: states.State[Any] | None,
        proposed_state: states.State[Any] | None,
        context: OrchestrationContext[
            orm_models.Run, core.TaskRunPolicy | core.FlowRunPolicy
        ],
    ) -> None:
        if initial_state is None or proposed_state is None:
            return

        if not proposed_state.state_details.scheduled_time:
            proposed_state.state_details.scheduled_time = (
                initial_state.state_details.scheduled_time
            )


class WaitForScheduledTime(
    BaseOrchestrationRule[orm_models.Run, Union[core.TaskRunPolicy, core.FlowRunPolicy]]
):
    """
    Prevents transitions to running states from happening too early.

    This rule enforces that all scheduled states will only start with the machine clock
    used by the Prefect REST API instance. This rule will identify transitions from scheduled
    states that are too early and nullify them. Instead, no state will be written to the
    database and the client will be sent an instruction to wait for `delay_seconds`
    before attempting the transition again.
    """

    FROM_STATES = {StateType.SCHEDULED, StateType.PENDING}
    TO_STATES = {StateType.RUNNING}

    async def before_transition(
        self,
        initial_state: states.State[Any] | None,
        proposed_state: states.State[Any] | None,
        context: OrchestrationContext[
            orm_models.Run, core.TaskRunPolicy | core.FlowRunPolicy
        ],
    ) -> None:
        if initial_state is None or proposed_state is None:
            return

        scheduled_time = initial_state.state_details.scheduled_time
        if not scheduled_time:
            return

        # At this moment, we round delay to the nearest second as the API schema
        # specifies an integer return value.
        delay = scheduled_time - now("UTC")
        delay_seconds = math.floor(delay.total_seconds())
        delay_seconds += round(delay.microseconds / 1e6)
        if delay_seconds > 0:
            await self.delay_transition(
                delay_seconds, reason="Scheduled time is in the future"
            )


class CopyTaskParametersID(TaskRunOrchestrationRule):
    """
    Ensures a task's parameters ID is copied from Scheduled to Pending and from
    Pending to Running states.

    If a parameters ID has been included on the proposed state, the parameters ID
    on the initial state will be ignored.
    """

    FROM_STATES = {StateType.SCHEDULED, StateType.PENDING}
    TO_STATES = {StateType.PENDING, StateType.RUNNING}

    async def before_transition(
        self,
        initial_state: states.State[Any] | None,
        proposed_state: states.State[Any] | None,
        context: OrchestrationContext[orm_models.TaskRun, core.TaskRunPolicy],
    ) -> None:
        if initial_state is None or proposed_state is None:
            return

        if not proposed_state.state_details.task_parameters_id:
            proposed_state.state_details.task_parameters_id = (
                initial_state.state_details.task_parameters_id
            )


class HandlePausingFlows(FlowRunOrchestrationRule):
    """
    Governs runs attempting to enter a Paused/Suspended state
    """

    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = {StateType.PAUSED}

    async def before_transition(
        self,
        initial_state: states.State[Any] | None,
        proposed_state: states.State[Any] | None,
        context: OrchestrationContext[orm_models.FlowRun, core.FlowRunPolicy],
    ) -> None:
        if proposed_state is None:
            return

        verb = "suspend" if proposed_state.name == "Suspended" else "pause"

        if initial_state is None:
            await self.abort_transition(f"Cannot {verb} flows with no state.")
            return

        if not initial_state.is_running():
            await self.reject_transition(
                state=None,
                reason=f"Cannot {verb} flows that are not currently running.",
            )
            return

        self.key = proposed_state.state_details.pause_key
        if self.key is None:
            # if no pause key is provided, default to a UUID
            self.key = str(uuid4())

        pause_keys = context.run.empirical_policy.pause_keys or set()
        if self.key in pause_keys:
            await self.reject_transition(
                state=None, reason=f"This {verb} has already fired."
            )
            return

        if proposed_state.state_details.pause_reschedule:
            if context.run.parent_task_run_id:
                await self.abort_transition(
                    reason=f"Cannot {verb} subflows.",
                )
                return

            if context.run.deployment_id is None:
                await self.abort_transition(
                    reason=f"Cannot {verb} flows without a deployment.",
                )
                return

    async def after_transition(
        self,
        initial_state: states.State[Any] | None,
        validated_state: states.State[Any] | None,
        context: OrchestrationContext[orm_models.FlowRun, core.FlowRunPolicy],
    ) -> None:
        updated_policy = context.run.empirical_policy.model_dump()
        updated_policy["pause_keys"].add(self.key)
        context.run.empirical_policy = core.FlowRunPolicy(**updated_policy)


class HandleResumingPausedFlows(FlowRunOrchestrationRule):
    """
    Governs runs attempting to leave a Paused state
    """

    FROM_STATES = {StateType.PAUSED}
    TO_STATES = ALL_ORCHESTRATION_STATES

    async def before_transition(
        self,
        initial_state: states.State[Any] | None,
        proposed_state: states.State[Any] | None,
        context: OrchestrationContext[orm_models.FlowRun, core.FlowRunPolicy],
    ) -> None:
        if initial_state is None or proposed_state is None:
            return

        if not (
            proposed_state
            and (
                proposed_state.is_running()
                or proposed_state.is_scheduled()
                or proposed_state.is_final()
            )
        ):
            await self.reject_transition(
                state=None,
                reason=(
                    f"This run cannot transition to the {proposed_state.type} state"
                    f" from the {initial_state.type} state."
                ),
            )
            return

        verb = "suspend" if proposed_state.name == "Suspended" else "pause"

        display_state_name = (
            proposed_state.name.lower()
            if proposed_state.name
            else proposed_state.type.value.lower()
        )

        if initial_state.state_details.pause_reschedule:
            if not context.run.deployment_id:
                await self.reject_transition(
                    state=None,
                    reason=(
                        f"Cannot reschedule a {display_state_name} flow run"
                        " without a deployment."
                    ),
                )
                return
        pause_timeout = initial_state.state_details.pause_timeout
        if pause_timeout and pause_timeout < now("UTC"):
            pause_timeout_failure = states.Failed(
                message=(f"The flow was {display_state_name} and never resumed."),
            )
            await self.reject_transition(
                state=pause_timeout_failure,
                reason=f"The flow run {verb} has timed out and can no longer resume.",
            )
            return

    async def after_transition(
        self,
        initial_state: states.State[Any] | None,
        validated_state: states.State[Any] | None,
        context: OrchestrationContext[orm_models.FlowRun, core.FlowRunPolicy],
    ) -> None:
        updated_policy = context.run.empirical_policy.model_dump()
        updated_policy["resuming"] = True
        context.run.empirical_policy = core.FlowRunPolicy(**updated_policy)


class UpdateFlowRunTrackerOnTasks(TaskRunOrchestrationRule):
    """
    Tracks the flow run attempt a task run state is associated with.
    """

    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = {StateType.RUNNING}

    async def after_transition(
        self,
        initial_state: states.State[Any] | None,
        validated_state: states.State[Any] | None,
        context: OrchestrationContext[orm_models.TaskRun, core.TaskRunPolicy],
    ) -> None:
        if context.run.flow_run_id is not None:
            self.flow_run: orm_models.FlowRun | None = await context.flow_run()
            if self.flow_run:
                context.run.flow_run_run_count = self.flow_run.run_count
            else:
                raise ObjectNotFoundError(
                    (
                        "Unable to read flow run associated with task run:"
                        f" {context.run.id}, this flow run might have been deleted"
                    ),
                )


class HandleTaskTerminalStateTransitions(TaskRunOrchestrationRule):
    """
    We do not allow tasks to leave terminal states if:
    - The task is completed and has a persisted result
    - The task is going to CANCELLING / PAUSED / CRASHED

    We reset the run count when a task leaves a terminal state for a non-terminal state
    which resets task run retries; this is particularly relevant for flow run retries.
    """

    FROM_STATES: set[states.StateType | None] = TERMINAL_STATES  # pyright: ignore[reportAssignmentType] technically TERMINAL_STATES doesn't contain None
    TO_STATES: set[states.StateType | None] = ALL_ORCHESTRATION_STATES

    async def before_transition(
        self,
        initial_state: states.State[Any] | None,
        proposed_state: states.State[Any] | None,
        context: OrchestrationContext[orm_models.TaskRun, core.TaskRunPolicy],
    ) -> None:
        if initial_state is None or proposed_state is None:
            return

        self.original_run_count: int = context.run.run_count

        # Do not allow runs to be marked as crashed, paused, or cancelling if already terminal
        if proposed_state.type in {
            StateType.CANCELLING,
            StateType.PAUSED,
            StateType.CRASHED,
        }:
            await self.abort_transition(f"Run is already {initial_state.type.value}.")
            return

        # Only allow departure from a happily completed state if the result is not persisted
        if (
            initial_state.is_completed()
            and initial_state.data
            and initial_state.data.get("type") != "unpersisted"
        ):
            await self.reject_transition(None, "This run is already completed.")
            return

        if not proposed_state.is_final():
            # Reset run count to reset retries
            context.run.run_count = 0

        # Change the name of the state to retrying if its a flow run retry
        if proposed_state.is_running() and context.run.flow_run_id is not None:
            self.flow_run: orm_models.FlowRun | None = await context.flow_run()
            if self.flow_run is not None:
                flow_retrying = context.run.flow_run_run_count < self.flow_run.run_count
                if flow_retrying:
                    await self.rename_state("Retrying")

    async def cleanup(
        self,
        initial_state: states.State[Any] | None,
        validated_state: states.State[Any] | None,
        context: OrchestrationContext[orm_models.TaskRun, core.TaskRunPolicy],
    ) -> None:
        # reset run count
        context.run.run_count = self.original_run_count


class HandleFlowTerminalStateTransitions(FlowRunOrchestrationRule):
    """
    We do not allow flows to leave terminal states if:
    - The flow is completed and has a persisted result
    - The flow is going to CANCELLING / PAUSED / CRASHED
    - The flow is going to scheduled and has no deployment

    We reset the pause metadata when a flow leaves a terminal state for a non-terminal
    state. This resets pause behavior during manual flow run retries.
    """

    FROM_STATES: set[states.StateType | None] = TERMINAL_STATES  # pyright: ignore[reportAssignmentType] technically TERMINAL_STATES doesn't contain None
    TO_STATES: set[states.StateType | None] = ALL_ORCHESTRATION_STATES

    async def before_transition(
        self,
        initial_state: states.State[Any] | None,
        proposed_state: states.State[Any] | None,
        context: OrchestrationContext[orm_models.FlowRun, core.FlowRunPolicy],
    ) -> None:
        if initial_state is None or proposed_state is None:
            return

        self.original_flow_policy: dict[str, Any] = (
            context.run.empirical_policy.model_dump()
        )

        # Do not allow runs to be marked as crashed, paused, or cancelling if already terminal
        if proposed_state.type in {
            StateType.CANCELLING,
            StateType.PAUSED,
            StateType.CRASHED,
        }:
            await self.abort_transition(
                f"Run is already in terminal state {initial_state.type.value}."
            )
            return

        # Only allow departure from a happily completed state if the result is not
        # persisted and the a rerun is being proposed
        if (
            initial_state.is_completed()
            and not proposed_state.is_final()
            and initial_state.data
            and initial_state.data.get("type") != "unpersisted"
        ):
            await self.reject_transition(None, "Run is already COMPLETED.")
            return

        # Do not allows runs to be rescheduled without a deployment
        if proposed_state.is_scheduled() and not context.run.deployment_id:
            await self.abort_transition(
                "Cannot reschedule a run without an associated deployment."
            )
            return

        if not proposed_state.is_final():
            # Reset pause metadata when leaving a terminal state
            api_version = context.parameters.get("api-version", None)
            if api_version is None or api_version >= Version("0.8.4"):
                updated_policy = context.run.empirical_policy.model_dump()
                updated_policy["resuming"] = False
                updated_policy["pause_keys"] = set()
                if proposed_state.is_scheduled():
                    updated_policy["retry_type"] = "reschedule"
                else:
                    updated_policy["retry_type"] = None
                context.run.empirical_policy = core.FlowRunPolicy(**updated_policy)

    async def cleanup(
        self,
        initial_state: states.State[Any] | None,
        validated_state: states.State[Any] | None,
        context: OrchestrationContext[orm_models.FlowRun, core.FlowRunPolicy],
    ) -> None:
        context.run.empirical_policy = core.FlowRunPolicy(**self.original_flow_policy)


class PreventPendingTransitions(GenericOrchestrationRule):
    """
    Prevents transitions to PENDING.

    This rule is only used for flow runs.

    This is intended to prevent race conditions during duplicate submissions of runs.
    Before a run is submitted to its execution environment, it should be placed in a
    PENDING state. If two workers attempt to submit the same run, one of them should
    encounter a PENDING -> PENDING transition and abort orchestration of the run.

    Similarly, if the execution environment starts quickly the run may be in a RUNNING
    state when the second worker attempts the PENDING transition. We deny these state
    changes as well to prevent duplicate submission. If a run has transitioned to a
    RUNNING state a worker should not attempt to submit it again unless it has moved
    into a terminal state.

    CANCELLING and CANCELLED runs should not be allowed to transition to PENDING.
    For re-runs of deployed runs, they should transition to SCHEDULED first.
    For re-runs of ad-hoc runs, they should transition directly to RUNNING.
    """

    FROM_STATES = {
        StateType.PENDING,
        StateType.CANCELLING,
        StateType.RUNNING,
        StateType.CANCELLED,
    }
    TO_STATES = {StateType.PENDING}

    async def before_transition(
        self,
        initial_state: states.State[Any] | None,
        proposed_state: states.State[Any] | None,
        context: OrchestrationContext[
            orm_models.Run, Union[core.FlowRunPolicy, core.TaskRunPolicy]
        ],
    ) -> None:
        if initial_state is None or proposed_state is None:
            return

        await self.abort_transition(
            reason=(
                f"This run is in a {initial_state.type.name} state and cannot"
                " transition to a PENDING state."
            )
        )


class EnsureOnlyScheduledFlowsMarkedLate(FlowRunOrchestrationRule):
    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = {StateType.SCHEDULED}

    async def before_transition(
        self,
        initial_state: states.State[Any] | None,
        proposed_state: states.State[Any] | None,
        context: OrchestrationContext[orm_models.FlowRun, core.FlowRunPolicy],
    ) -> None:
        if initial_state is None or proposed_state is None:
            return

        marking_flow_late = (
            proposed_state.is_scheduled() and proposed_state.name == "Late"
        )
        if marking_flow_late and not initial_state.is_scheduled():
            await self.reject_transition(
                state=None, reason="Only scheduled flows can be marked late."
            )


class PreventRunningTasksFromStoppedFlows(TaskRunOrchestrationRule):
    """
    Prevents running tasks from stopped flows.

    A running state implies execution, but also the converse. This rule ensures that a
    flow's tasks cannot be run unless the flow is also running.
    """

    FROM_STATES = ALL_ORCHESTRATION_STATES
    TO_STATES = {StateType.RUNNING}

    async def before_transition(
        self,
        initial_state: states.State[Any] | None,
        proposed_state: states.State[Any] | None,
        context: OrchestrationContext[orm_models.TaskRun, core.TaskRunPolicy],
    ) -> None:
        flow_run = await context.flow_run()
        if flow_run is not None:
            if flow_run.state is None:
                await self.abort_transition(
                    reason="The enclosing flow must be running to begin task execution."
                )
            elif flow_run.state.type == StateType.PAUSED:
                # Use the flow run's Paused state details to preserve data like
                # timeouts.
                paused_state = states.Paused(
                    name="NotReady",
                    pause_expiration_time=flow_run.state.state_details.pause_timeout,
                    reschedule=flow_run.state.state_details.pause_reschedule,
                )
                await self.reject_transition(
                    state=paused_state,
                    reason=(
                        "The flow is paused, new tasks can execute after resuming flow"
                        f" run: {flow_run.id}."
                    ),
                )
            elif not flow_run.state.type == StateType.RUNNING:
                # task runners should abort task run execution
                await self.abort_transition(
                    reason=(
                        "The enclosing flow must be running to begin task execution."
                    ),
                )


class EnforceCancellingToCancelledTransition(TaskRunOrchestrationRule):
    """
    Rejects transitions from Cancelling to any terminal state except for Cancelled.
    """

    FROM_STATES = {StateType.CANCELLED, StateType.CANCELLING}
    TO_STATES = ALL_ORCHESTRATION_STATES - {StateType.CANCELLED}

    async def before_transition(
        self,
        initial_state: states.State[Any] | None,
        proposed_state: states.State[Any] | None,
        context: OrchestrationContext[orm_models.TaskRun, core.TaskRunPolicy],
    ) -> None:
        await self.reject_transition(
            state=None,
            reason=(
                "Cannot transition flows that are cancelling to a state other "
                "than Cancelled."
            ),
        )
        return


class BypassCancellingFlowRunsWithNoInfra(FlowRunOrchestrationRule):
    """Rejects transitions from Scheduled to Cancelling, and instead sets the state to Cancelled,
    if the flow run has no associated infrastructure process ID. Also Rejects transitions from
    Paused to Cancelling if the Paused state's details indicates the flow run has been suspended,
    exiting the flow and tearing down infra.

    The `Cancelling` state is used to clean up infrastructure. If there is not infrastructure
    to clean up, we can transition directly to `Cancelled`. Runs that are `Resuming` are in a
    `Scheduled` state that were previously `Suspended` and do not yet have infrastructure.

    Runs that are `AwaitingRetry` are a `Scheduled` state that may have associated infrastructure.
    """

    FROM_STATES = {StateType.SCHEDULED, StateType.PAUSED}
    TO_STATES = {StateType.CANCELLING}

    async def before_transition(
        self,
        initial_state: states.State[Any] | None,
        proposed_state: states.State[Any] | None,
        context: OrchestrationContext[orm_models.FlowRun, core.FlowRunPolicy],
    ) -> None:
        if initial_state is None or proposed_state is None:
            return

        if (
            initial_state.type == states.StateType.SCHEDULED
            and not context.run.infrastructure_pid
            or initial_state.name == "Resuming"
        ):
            await self.reject_transition(
                state=states.Cancelled(),
                reason="Scheduled flow run has no infrastructure to terminate.",
            )
        elif (
            initial_state.type == states.StateType.PAUSED
            and initial_state.state_details.pause_reschedule
        ):
            await self.reject_transition(
                state=states.Cancelled(),
                reason="Suspended flow run has no infrastructure to terminate.",
            )


class PreventDuplicateTransitions(FlowRunOrchestrationRule):
    """
    Prevent duplicate transitions from being made right after one another.

    This rule allows for clients to set an optional transition_id on a state. If the
    run's next transition has the same transition_id, the transition will be
    rejected and the existing state will be returned.

    This allows for clients to make state transition requests without worrying about
    the following case:
    - A client making a state transition request
    - The server accepts transition and commits the transition
    - The client is unable to receive the response and retries the request
    """

    FROM_STATES: set[states.StateType | None] = ALL_ORCHESTRATION_STATES
    TO_STATES: set[states.StateType | None] = ALL_ORCHESTRATION_STATES

    async def before_transition(
        self,
        initial_state: states.State[Any] | None,
        proposed_state: states.State[Any] | None,
        context: OrchestrationContext[orm_models.FlowRun, core.FlowRunPolicy],
    ) -> None:
        if initial_state is None or proposed_state is None:
            return

        initial_transition_id = getattr(
            initial_state.state_details, "transition_id", None
        )
        proposed_transition_id = getattr(
            proposed_state.state_details, "transition_id", None
        )
        if (
            initial_transition_id is not None
            and proposed_transition_id is not None
            and initial_transition_id == proposed_transition_id
        ):
            await self.reject_transition(
                # state=None will return the initial (current) state
                state=None,
                reason="This run has already made this state transition.",
            )
