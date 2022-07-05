__all__ = [
    "create_project",
    "create_exam_pool",
    "create_pool",
    "create_tasks",
    "open_pool",
    "open_exam_pool",
    "wait_pool",
    "get_assignments",
    "get_assignments_df",
    "accept_assignment",
    "reject_assignment",
]

import logging
import http
import pandas as pd
import time
from datetime import datetime, timedelta
from enum import Enum, unique
from typing import Dict, List, Optional, Union

from prefect import task

from toloka.client import Assignment, Pool, Project, TolokaClient, Training
from toloka.client import Task as TolokaTask
from toloka.client.analytics_request import CompletionPercentagePoolAnalytics
from toloka.client.assignment import GetAssignmentsTsvParameters
from toloka.client.batch_create_results import TaskBatchCreateResult
from toloka.client.exceptions import IncorrectActionsApiError

from .utils import extract_id, structure_from_conf, with_logger, with_toloka_client


@task
@with_toloka_client
def create_project(
    obj: Union[Project, Dict, str, bytes],
    *,
    toloka_client: Optional[TolokaClient] = None,
) -> Project:
    """
    Task to create a Toloka `Project` object from given config.

    Args:
        - obj (Project, Dict, str, bytes): Either a `Project` object itself
            or a config to make a `Project`.
        - token (str, optional): Toloka token value provided with a Prefect Secret.
            If not provided the task will fallback to using Secret with secret_name.
        - secret_name (str, optional): Allow to use non-default secret for Toloka token.
            Default: "TOLOKA_TOKEN".
        - env (str, optional): Allow to use non-default Toloka environment.
            Default: "PRODUCTION".

    Returns:
        - Project: Toloka project object with id assigned.

    Example:
        >>> project_conf = {...}  # May also be configured toloka.client.Project object.
        >>> project = create_project(project_conf)
        ...
    """
    obj = structure_from_conf(obj, Project)
    return toloka_client.create_project(obj)


@task
@with_toloka_client
def create_exam_pool(
    obj: Union[Training, Dict, str, bytes],
    *,
    project_id: Union[Project, Dict, str, None] = None,
    toloka_client: Optional[TolokaClient] = None,
) -> Training:
    """
    Task to create a Toloka `Training` pool object from given config.

    Args:
        - obj (Training, Dict, str, bytes): Either a `Training` object itself
            or a config to make a `Training`.
        - project_id (Project, Dict, str, optional): Project ID to assign a training pool to.
            May pass either an object, config or project_id value.
        - token (str, optional): Toloka token value provided with a Prefect Secret.
            If not provided the task will fallback to using Secret with secret_name.
        - secret_name (str, optional): Allow to use non-default secret for Toloka token.
            Default: "TOLOKA_TOKEN".
        - env (str, optional): Allow to use non-default Toloka environment.
            Default: "PRODUCTION".

    Returns:
        - Training: Toloka training pool object with id assigned.

    Example:
        >>> project = create_project({...})
        >>> exam = create_exam_pool({...}, project_id=project)
        ...
    """
    obj = structure_from_conf(obj, Training)
    if project_id is not None:
        obj.project_id = extract_id(project_id, Project)
    return toloka_client.create_training(obj)


@task
@with_toloka_client
def create_pool(
    obj: Union[Pool, Dict, str, bytes],
    *,
    project_id: Union[Project, Dict, str, None] = None,
    exam_pool_id: Union[Training, Dict, str, None] = None,
    expiration: Union[datetime, timedelta, None] = None,
    reward_per_assignment: Optional[float] = None,
    toloka_client: Optional[TolokaClient] = None,
) -> Pool:
    """
    Task to create a Toloka `Pool` object from given config.

    Args:
        - obj (Pool, Dict, str, bytes): Either a `Pool` object itself or a config to make a `Pool`.
        - project_id (Project, Dict, str, optional): Project ID to assign a pool to.
            May pass either an object, config or project_id value.
        - exam_pool_id (Training, Dict, str, optional): Related training pool ID.
            May pass either an object, config or pool_id value.
        - expiration (datetime, timedelta, optional): Expiration setting. May pass any of:
            `None` if this setting if already present;
            `datetime` object to set exact datetime;
            `timedelta` to set expiration related to the current time.
        - reward_per_assignment (float, optional): Allow to redefine reward per assignment.
        - token (str, optional): Toloka token value provided with a Prefect Secret.
            If not provided the task will fallback to using Secret with secret_name.
        - secret_name (str, optional): Allow to use non-default secret for Toloka token.
            Default: "TOLOKA_TOKEN".
        - env (str, optional): Allow to use non-default Toloka environment.
            Default: "PRODUCTION".

    Returns:
        - Pool: Toloka pool object with id assigned.

    Example:
        >>> project = create_project({...})
        >>> exam = create_exam_pool({...}, project_id=project)
        >>> pool = create_pool({...}, project_id=project, exam_pool_id=exam)
        ...
    """
    obj = structure_from_conf(obj, Pool)
    if project_id is not None:
        obj.project_id = extract_id(project_id, Project)
    if exam_pool_id:
        if obj.quality_control.training_requirement is None:
            raise ValueError(
                "pool.quality_control.training_requirement should be set before exam_pool assignment"
            )
        obj.quality_control.training_requirement.training_pool_id = extract_id(
            exam_pool_id, Training
        )
    if expiration:
        if isinstance(expiration, timedelta):
            obj.will_expire = datetime.utcnow() + expiration
        else:
            obj.will_expire = expiration
    if reward_per_assignment:
        obj.reward_per_assignment = reward_per_assignment
    return toloka_client.create_pool(obj)


@task
@with_toloka_client
def create_tasks(
    tasks: List[Union[TolokaTask, Dict]],
    *,
    pool_id: Union[Pool, Training, Dict, str, None] = None,
    allow_defaults: bool = False,
    open_pool: bool = False,
    skip_invalid_items: bool = False,
    toloka_client: Optional[TolokaClient] = None,
) -> TaskBatchCreateResult:
    """
    Task to create a list of tasks for a given pool.

    Args:
        - tasks (List[Union[TolokaTask, Dict]]): List of either a `toloka.client.Task` objects
            or task conofigurations.
        - pool_id (Pool, Training, Dict, str, optional): Allow to set tasks pool ID
            if it's not present in tasks themselves.
            May be either a `Pool` or `Training` object or config or a pool_id value.
        - allow_defaults (bool, optional): Allow to use the overlap that is set in the pool parameters.
        - open_pool (bool, optional): Open the pool immediately after creating a task suite, if closed.
        - skip_invalid_items (bool, optional): Allow to skip invalid tasks.
            You can handle them using resulting TaskBatchCreateResult object.
        - token (str, optional): Toloka token value provided with a Prefect Secret.
            If not provided the task will fallback to using Secret with secret_name.
        - secret_name (str, optional): Allow to use non-default secret for Toloka token.
            Default: "TOLOKA_TOKEN".
        - env (str, optional): Allow to use non-default Toloka environment.
            Default: "PRODUCTION".

    Returns:
        - TaskBatchCreateResult: Result object.

    Example:
        >>> tasks = [{'input_values': ...}, {'input_values': ...}, {'input_values': ...}]
        >>> create_tasks(tasks,
        ...              pool_id='some-pool_id-123',
        ...              open_pool=True,
        ...              allow_defaults=True)
        ...
    """
    tasks = [structure_from_conf(task, TolokaTask) for task in tasks]
    if pool_id is not None:
        try:
            pool_id = extract_id(pool_id, Pool)
        except Exception:
            pool_id = extract_id(pool_id, Training)
        for task_ in tasks:
            task_.pool_id = pool_id
    kwargs = {
        "allow_defaults": allow_defaults,
        "open_pool": open_pool,
        "skip_invalid_items": skip_invalid_items,
    }
    return toloka_client.create_tasks(tasks, **kwargs)


@task
@with_toloka_client
def open_pool(
    obj: Union[Pool, Dict, str],
    *,
    toloka_client: Optional[TolokaClient] = None,
) -> Pool:
    """
    Task to open given Toloka pool.

    Args:
        - obj (Pool, Dict, str): Pool id or `Pool` object of it's config.
        - token (str, optional): Toloka token value provided with a Prefect Secret.
            If not provided the task will fallback to using Secret with secret_name.
        - secret_name (str, optional): Allow to use non-default secret for Toloka token.
            Default: "TOLOKA_TOKEN".
        - env (str, optional): Allow to use non-default Toloka environment.
            Default: "PRODUCTION".

    Returns:
        - Pool: Opened pool object.

    Example:
        >>> pool = create_pool({...})
        >>> _tasks_creation = create_tasks([...], pool=pool)
        >>> open_pool(pool, upstream_tasks=[_tasks_creation])
        ...
    """
    pool_id = extract_id(obj, Pool)
    return toloka_client.open_pool(pool_id)


@task
@with_toloka_client
def open_exam_pool(
    obj: Union[Training, str],
    *,
    toloka_client: Optional[TolokaClient] = None,
) -> Pool:
    """
    Task to open given training pool.

    Args:
        - obj (Training, Dict, str): Training pool_id or `Training` object of it's config.
        - token (str, optional): Toloka token value provided with a Prefect Secret.
            If not provided the task will fallback to using Secret with secret_name.
        - secret_name (str, optional): Allow to use non-default secret for Toloka token.
            Default: "TOLOKA_TOKEN".
        - env (str, optional): Allow to use non-default Toloka environment.
            Default: "PRODUCTION".

    Returns:
        - Training: Opened training (exam) pool object.

    Example:
        >>> exam = create_training({...})
        >>> _exam_tasks_creation = create_tasks([...], pool=exam)
        >>> open_exam_pool(exam, upstream_tasks=[_exam_tasks_creation])
        ...
    """
    pool_id = extract_id(obj, Training)
    return toloka_client.open_training(pool_id)


@task
@with_toloka_client
@with_logger
def wait_pool(
    pool_id: Union[Pool, Dict, str],
    period: timedelta = timedelta(seconds=60),
    *,
    open_pool: bool = False,
    logger: logging.Logger,
    toloka_client: Optional[TolokaClient] = None,
) -> Pool:
    """
    Task to wait given Toloka pool until close.

    Args:
        - pool_id (Pool, Dict, str): Either a `Pool` object or it's config or a pool ID value.
        - period (timedelta): Interval between checks. One minute by default.
        - open_pool (bool, optional): Allow to open pool at start if it's closed. False by default.
        - token (str, optional): Toloka token value provided with a Prefect Secret.
            If not provided the task will fallback to using Secret with secret_name.
        - secret_name (str, optional): Allow to use non-default secret for Toloka token.
            Default: "TOLOKA_TOKEN".
        - env (str, optional): Allow to use non-default Toloka environment.
            Default: "PRODUCTION".

    Returns:
        - Pool: Toloka pool object.

    Example:
        >>> pool = create_pool({...})
        >>> _tasks_creation = create_tasks([...], pool=pool)
        >>> wait_pool(pool, open_pool=True, upstream_tasks=[_tasks_creation])
        ...
    """
    pool_id = extract_id(pool_id, Pool)
    pool = toloka_client.get_pool(pool_id)
    if pool.is_closed() and open_pool:
        pool = toloka_client.open_pool(pool_id)

    while pool.is_open():
        op = toloka_client.get_analytics(
            [CompletionPercentagePoolAnalytics(subject_id=pool_id)]
        )
        percentage = toloka_client.wait_operation(op).details["value"][0]["result"][
            "value"
        ]
        logger.info(f"Pool {pool_id} - {percentage}%")

        time.sleep(period.total_seconds())
        pool = toloka_client.get_pool(pool_id)

    return pool


@task
@with_toloka_client
def get_assignments(
    pool_id: Union[Pool, Dict, str],
    status: Union[
        str, List[str], Assignment.Status, List[Assignment.Status], None
    ] = None,
    *,
    toloka_client: Optional[TolokaClient] = None,
    **kwargs,
) -> List[Assignment]:
    """
    Task to get all assignments of selected status from Toloka pool.

    Args:
        - pool_id (Pool, Dict, str): Either a `Pool` object or it's config or a pool ID value.
        - status (str, List[str], optional): A status or a list of statuses to get.
            All statuses (None) by default.
        - token (str, optional): Toloka token value provided with a Prefect Secret.
            If not provided the task will fallback to using Secret with secret_name.
        - secret_name (str, optional): Allow to use non-default secret for Toloka token.
            Default: "TOLOKA_TOKEN".
        - env (str, optional): Allow to use non-default Toloka environment.
            Default: "PRODUCTION".
        - **kwargs: Other args presented in `toloka.client.search_requests.AssignmentSearchRequest`.

    Returns:
        - List[Assignment]: Get assignments result.

    Example:
        >>> pool = create_pool({...})
        >>> _tasks_creation = create_tasks([...], pool=pool)
        >>> _waiting = wait_pool(pool, open_pool=True, upstream_tasks=[_tasks_creation])
        >>> results = get_assignments(pool, status=['SUBMITTED'], upstream_tasks=[_waiting])
        ...
    """
    pool_id = extract_id(pool_id, Pool)
    return list(toloka_client.get_assignments(pool_id=pool_id, status=status, **kwargs))


@task
@with_toloka_client
def get_assignments_df(
    pool_id: Union[Pool, Dict, str],
    status: Union[
        str, List[str], Assignment.Status, List[Assignment.Status], None
    ] = None,
    *,
    toloka_client: Optional[TolokaClient] = None,
    start_time_from: Optional[datetime] = None,
    start_time_to: Optional[datetime] = None,
    exclude_banned: bool = False,
    field: Optional[List[GetAssignmentsTsvParameters.Field]] = None,
) -> pd.DataFrame:
    """
    Task to get pool assignments of selected statuses
    in Pandas `DataFrame` format useful for aggregation.

    Args:
        - pool_id (Pool, Dict, str): Either a `Pool` object or it's config or a pool ID value.
        - status (str, List[str], optional): A status or a list of statuses to get.
            All statuses (None) by default.
        - token (str, optional): Toloka token value provided with a Prefect Secret.
            If not provided the task will fallback to using Secret with secret_name.
        - secret_name (str, optional): Allow to use non-default secret for Toloka token.
            Default: "TOLOKA_TOKEN".
        - env (str, optional): Allow to use non-default Toloka environment.
            Default: "PRODUCTION".
        - start_time_from (str, optional): Upload assignments submitted after the specified datetime.
        - start_time_to (str, optional): Upload assignments submitted before the specified datetime.
        - exclude_banned (bool, optional): Exclude answers from banned performers,
            even if assignments in suitable status "ACCEPTED".
        - field (List[GetAssignmentsTsvParameters.Field], optional): Select some additional fields.
            You can find possible values in the
            `toloka.client.assignment.GetAssignmentsTsvParameters.Field` enum.

    Returns:
        - DataFrame: `pd.DataFrame` with selected assignments.
            Note that nested paths are presented with a ":" sign.

    Example:
        >>> pool = create_pool({...})
        >>> _tasks_creation = create_tasks([...], pool=pool)
        >>> _waiting = wait_pool(pool, open_pool=True, upstream_tasks=[_tasks_creation])
        >>> df = get_assignments_df(pool, status=['SUBMITTED'], upstream_tasks=[_waiting])
        ...
    """
    pool_id = extract_id(pool_id, Pool)
    if not status:
        status = []
    elif isinstance(status, (str, Assignment.Status)):
        status = [status]
    kwargs = {
        "start_time_from": start_time_from,
        "start_time_to": start_time_to,
        "exclude_banned": exclude_banned,
        "field": field,
    }
    return toloka_client.get_assignments_df(
        pool_id=pool_id,
        status=status,
        **{key: value for key, value in kwargs.items() if value is not None},
    )


@unique
class _PatchAssignmentMethod(Enum):
    ACCEPT_ASSIGNMENT = "accept_assignment"
    REJECT_ASSIGNMENT = "reject_assignment"


def _patch_assignment(
    method_name: _PatchAssignmentMethod,
    assignment_id: Union[Assignment, Dict, str],
    public_comment: str,
    fail_if_already_set: bool,
    logger: logging.Logger,
    toloka_client: Optional[TolokaClient],
) -> Union[Assignment, Dict, str]:
    """Function to either accept or reject assignment with given comment."""
    assignment_id = extract_id(assignment_id, Assignment)
    method = getattr(toloka_client, method_name.value)
    try:
        method(assignment_id, public_comment=public_comment)
    except IncorrectActionsApiError as exc:
        logger.warning("Can't %s %s: %s", method_name.value, assignment_id, exc)
        if fail_if_already_set or exc.status_code != http.client.CONFLICT.value:
            raise
    return assignment_id


@task
@with_toloka_client
@with_logger
def accept_assignment(
    assignment_id: Union[Assignment, Dict, str],
    public_comment: str,
    fail_if_already_set: bool = False,
    *,
    logger: logging.Logger,
    toloka_client: Optional[TolokaClient] = None,
) -> Union[Assignment, Dict, str]:
    """
    Task to accept given assignment by given ID.
    Use `accept_assignment.map` to process multiple assignments.
    Pass public_comment with `unmapped` wrapper in this case.

    Args:
        - assignment_id (Assignment, Dict, str): Either an `Assignment` object
            or it's config or an assignment ID value.
        - public_comment (str): Public comment.
        - fail_if_already_set (bool, optional): Fail if the assignment has already been accepted
            (in the UI for example). Skip by default.
        - token (str, optional): Toloka token value provided with a Prefect Secret.
            If not provided the task will fallback to using Secret with secret_name.
        - secret_name (str, optional): Allow to use non-default secret for Toloka token.
            Default: "TOLOKA_TOKEN".
        - env (str, optional): Allow to use non-default Toloka environment.
            Default: "PRODUCTION".

    Returns:
        - Union[Assignment, Dict, str]: The same assignment_id, that was given.

    Example:
        >>> aggregated = do_some_aggregation(assignments)
        >>> to_accept = some_filter_to_accept(aggregated)
        >>> accept_assignment.map(to_accept, unmapped('Well done!'))
        ...
    """
    return _patch_assignment(
        _PatchAssignmentMethod.ACCEPT_ASSIGNMENT,
        assignment_id,
        public_comment,
        fail_if_already_set,
        logger,
        toloka_client,
    )


@task
@with_toloka_client
@with_logger
def reject_assignment(
    assignment_id: Union[Assignment, Dict, str],
    public_comment: str,
    fail_if_already_set: bool = False,
    *,
    logger: logging.Logger,
    toloka_client: Optional[TolokaClient] = None,
) -> Union[Assignment, Dict, str]:
    """
    Task to reject given assignment by given ID.
    Use `reject_assignment.map` to process multiple assignments.
    Pass public_comment with `unmapped` wrapper in this case.

    Args:
        - assignment_id (Assignment, Dict, str): Either an `Assignment` object
            or it's config or an assignment ID value.
        - public_comment (str): Public comment.
        - fail_if_already_set (bool, optional): Fail if the assignment has already been rejected
            (in the UI for example). Skip by default.
        - token (str, optional): Toloka token value provided with a Prefect Secret.
            If not provided the task will fallback to using Secret with secret_name.
        - secret_name (str, optional): Allow to use non-default secret for Toloka token.
            Default: "TOLOKA_TOKEN".
        - env (str, optional): Allow to use non-default Toloka environment.
            Default: "PRODUCTION".

    Returns:
        - Union[Assignment, Dict, str]: The same assignment_id, that was given.

    Example:
        >>> aggregated = do_some_aggregation(assignments)
        >>> to_reject = some_filter_to_reject(aggregated)
        >>> reject_assignment.map(to_reject, unmapped('Incorrect answer'))
        ...
    """
    return _patch_assignment(
        _PatchAssignmentMethod.REJECT_ASSIGNMENT,
        assignment_id,
        public_comment,
        fail_if_already_set,
        logger,
        toloka_client,
    )
