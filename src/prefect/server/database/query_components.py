import datetime
from abc import ABC, abstractmethod, abstractproperty
from collections import defaultdict
from typing import (
    TYPE_CHECKING,
    Dict,
    Hashable,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
    cast,
)
from uuid import UUID

import pendulum
import sqlalchemy as sa
from cachetools import TTLCache
from jinja2 import Environment, PackageLoader, select_autoescape
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models, schemas
from prefect.server.database import orm_models
from prefect.server.exceptions import FlowRunGraphTooLarge, ObjectNotFoundError
from prefect.server.schemas.graph import Edge, Graph, GraphArtifact, GraphState, Node
from prefect.server.utilities.database import UUID as UUIDTypeDecorator
from prefect.server.utilities.database import Timestamp, json_has_any_key

if TYPE_CHECKING:
    from prefect.server.database.interface import PrefectDBInterface

ONE_HOUR = 60 * 60


jinja_env = Environment(
    loader=PackageLoader("prefect.server.database", package_path="sql"),
    autoescape=select_autoescape(),
    trim_blocks=True,
)


class BaseQueryComponents(ABC):
    """
    Abstract base class used to inject dialect-specific SQL operations into Prefect.
    """

    CONFIGURATION_CACHE = TTLCache(maxsize=100, ttl=ONE_HOUR)

    def _unique_key(self) -> Tuple[Hashable, ...]:
        """
        Returns a key used to determine whether to instantiate a new DB interface.
        """
        return (self.__class__,)

    # --- dialect-specific SqlAlchemy bindings

    @abstractmethod
    def insert(self, obj) -> Union[postgresql.Insert, sqlite.Insert]:
        """dialect-specific insert statement"""

    @abstractmethod
    def greatest(self, *values):
        """dialect-specific SqlAlchemy binding"""

    @abstractmethod
    def least(self, *values):
        """dialect-specific SqlAlchemy binding"""

    # --- dialect-specific JSON handling

    @abstractproperty
    def uses_json_strings(self) -> bool:
        """specifies whether the configured dialect returns JSON as strings"""

    @abstractmethod
    def cast_to_json(self, json_obj):
        """casts to JSON object if necessary"""

    @abstractmethod
    def build_json_object(self, *args):
        """builds a JSON object from sequential key-value pairs"""

    @abstractmethod
    def json_arr_agg(self, json_array):
        """aggregates a JSON array"""

    # --- dialect-optimized subqueries

    @abstractmethod
    def make_timestamp_intervals(
        self,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        interval: datetime.timedelta,
    ):
        ...

    @abstractmethod
    def set_state_id_on_inserted_flow_runs_statement(
        self,
        fr_model,
        frs_model,
        inserted_flow_run_ids,
        insert_flow_run_states,
    ):
        ...

    @abstractmethod
    async def get_flow_run_notifications_from_queue(
        self, session: AsyncSession, limit: int
    ):
        """Database-specific implementation of reading notifications from the queue and deleting them"""

    async def queue_flow_run_notifications(
        self,
        session: sa.orm.session,
        flow_run: Union[schemas.core.FlowRun, orm_models.FlowRun],
        db: "PrefectDBInterface",
    ):
        """Database-specific implementation of queueing notifications for a flow run"""
        # insert a <policy, state> pair into the notification queue
        stmt = db.insert(orm_models.FlowRunNotificationQueue).from_select(
            [
                orm_models.FlowRunNotificationQueue.flow_run_notification_policy_id,
                orm_models.FlowRunNotificationQueue.flow_run_state_id,
            ],
            # ... by selecting from any notification policy that matches the criteria
            sa.select(
                orm_models.FlowRunNotificationPolicy.id,
                sa.cast(sa.literal(str(flow_run.state_id)), UUIDTypeDecorator),
            )
            .select_from(orm_models.FlowRunNotificationPolicy)
            .where(
                sa.and_(
                    # the policy is active
                    orm_models.FlowRunNotificationPolicy.is_active.is_(True),
                    # the policy state names aren't set or match the current state name
                    sa.or_(
                        orm_models.FlowRunNotificationPolicy.state_names == [],
                        json_has_any_key(
                            orm_models.FlowRunNotificationPolicy.state_names,
                            [flow_run.state_name],
                        ),
                    ),
                    # the policy tags aren't set, or the tags match the flow run tags
                    sa.or_(
                        orm_models.FlowRunNotificationPolicy.tags == [],
                        json_has_any_key(
                            orm_models.FlowRunNotificationPolicy.tags, flow_run.tags
                        ),
                    ),
                )
            ),
            # don't send python defaults as part of the insert statement, because they are
            # evaluated once per statement and create unique constraint violations on each row
            include_defaults=False,
        )
        await session.execute(stmt)

    def get_scheduled_flow_runs_from_work_queues(
        self,
        limit_per_queue: Optional[int] = None,
        work_queue_ids: Optional[List[UUID]] = None,
        scheduled_before: Optional[datetime.datetime] = None,
    ):
        """
        Returns all scheduled runs in work queues, subject to provided parameters.

        This query returns a `(orm_models.FlowRun, orm_models.WorkQueue.id)` pair; calling
        `result.all()` will return both; calling `result.scalars().unique().all()`
        will return only the flow run because it grabs the first result.
        """

        # get any work queues that have a concurrency limit, and compute available
        # slots as their limit less the number of running flows
        concurrency_queues = (
            sa.select(
                orm_models.WorkQueue.id,
                self.greatest(
                    0,
                    orm_models.WorkQueue.concurrency_limit
                    - sa.func.count(orm_models.FlowRun.id),
                ).label("available_slots"),
            )
            .select_from(orm_models.WorkQueue)
            .join(
                orm_models.FlowRun,
                sa.and_(
                    self._flow_run_work_queue_join_clause(
                        orm_models.FlowRun, orm_models.WorkQueue
                    ),
                    orm_models.FlowRun.state_type.in_(
                        ["RUNNING", "PENDING", "CANCELLING"]
                    ),
                ),
                isouter=True,
            )
            .where(orm_models.WorkQueue.concurrency_limit.is_not(None))
            .group_by(orm_models.WorkQueue.id)
            .cte("concurrency_queues")
        )

        # use the available slots information to generate a join
        # for all scheduled runs
        scheduled_flow_runs, join_criteria = self._get_scheduled_flow_runs_join(
            work_queue_query=concurrency_queues,
            limit_per_queue=limit_per_queue,
            scheduled_before=scheduled_before,
        )

        # starting with the work queue table, join the limited queues to get the
        # concurrency information and the scheduled flow runs to load all applicable
        # runs. this will return all the scheduled runs allowed by the parameters
        query = (
            # return a flow run and work queue id
            sa.select(
                sa.orm.aliased(orm_models.FlowRun, scheduled_flow_runs),
                orm_models.WorkQueue.id.label("wq_id"),
            )
            .select_from(orm_models.WorkQueue)
            .join(
                concurrency_queues,
                orm_models.WorkQueue.id == concurrency_queues.c.id,
                isouter=True,
            )
            .join(scheduled_flow_runs, join_criteria)
            .where(
                orm_models.WorkQueue.is_paused.is_(False),
                orm_models.WorkQueue.id.in_(work_queue_ids) if work_queue_ids else True,
            )
            .order_by(
                scheduled_flow_runs.c.next_scheduled_start_time,
                scheduled_flow_runs.c.id,
            )
        )

        return query

    def _get_scheduled_flow_runs_join(
        self,
        work_queue_query,
        limit_per_queue: Optional[int],
        scheduled_before: Optional[datetime.datetime],
    ):
        """Used by self.get_scheduled_flow_runs_from_work_queue, allowing just
        this function to be changed on a per-dialect basis"""

        # precompute for readability
        scheduled_before_clause = (
            orm_models.FlowRun.next_scheduled_start_time <= scheduled_before
            if scheduled_before is not None
            else True
        )

        # get scheduled flow runs with lateral join where the limit is the
        # available slots per queue
        scheduled_flow_runs = (
            sa.select(orm_models.FlowRun)
            .where(
                self._flow_run_work_queue_join_clause(
                    orm_models.FlowRun, orm_models.WorkQueue
                ),
                orm_models.FlowRun.state_type == "SCHEDULED",
                scheduled_before_clause,
            )
            .with_for_update(skip_locked=True)
            # priority given to runs with earlier next_scheduled_start_time
            .order_by(orm_models.FlowRun.next_scheduled_start_time)
            # if null, no limit will be applied
            .limit(sa.func.least(limit_per_queue, work_queue_query.c.available_slots))
            .lateral("scheduled_flow_runs")
        )

        # Perform a cross-join
        join_criteria = sa.literal(True)

        return scheduled_flow_runs, join_criteria

    def _flow_run_work_queue_join_clause(self, flow_run, work_queue):
        """
        On clause for for joining flow runs to work queues

        Used by self.get_scheduled_flow_runs_from_work_queue, allowing just
        this function to be changed on a per-dialect basis
        """
        return sa.and_(flow_run.work_queue_name == work_queue.name)

    # -------------------------------------------------------
    # Workers
    # -------------------------------------------------------

    @abstractproperty
    def _get_scheduled_flow_runs_from_work_pool_template_path(self):
        """
        Template for the query to get scheduled flow runs from a work pool
        """

    async def get_scheduled_flow_runs_from_work_pool(
        self,
        session,
        limit: Optional[int] = None,
        worker_limit: Optional[int] = None,
        queue_limit: Optional[int] = None,
        work_pool_ids: Optional[List[UUID]] = None,
        work_queue_ids: Optional[List[UUID]] = None,
        scheduled_before: Optional[datetime.datetime] = None,
        scheduled_after: Optional[datetime.datetime] = None,
        respect_queue_priorities: bool = False,
    ) -> List[schemas.responses.WorkerFlowRunResponse]:
        template = jinja_env.get_template(
            self._get_scheduled_flow_runs_from_work_pool_template_path
        )

        raw_query = sa.text(
            template.render(
                work_pool_ids=work_pool_ids,
                work_queue_ids=work_queue_ids,
                respect_queue_priorities=respect_queue_priorities,
                scheduled_before=scheduled_before,
                scheduled_after=scheduled_after,
            )
        )

        bindparams = []

        if scheduled_before:
            bindparams.append(
                sa.bindparam("scheduled_before", scheduled_before, type_=Timestamp)
            )

        if scheduled_after:
            bindparams.append(
                sa.bindparam("scheduled_after", scheduled_after, type_=Timestamp)
            )

        # if work pool IDs were provided, bind them
        if work_pool_ids:
            assert all(isinstance(i, UUID) for i in work_pool_ids)
            bindparams.append(
                sa.bindparam(
                    "work_pool_ids",
                    work_pool_ids,
                    expanding=True,
                    type_=UUIDTypeDecorator,
                )
            )

        # if work queue IDs were provided, bind them
        if work_queue_ids:
            assert all(isinstance(i, UUID) for i in work_queue_ids)
            bindparams.append(
                sa.bindparam(
                    "work_queue_ids",
                    work_queue_ids,
                    expanding=True,
                    type_=UUIDTypeDecorator,
                )
            )

        query = raw_query.bindparams(
            *bindparams,
            limit=1000 if limit is None else limit,
            worker_limit=1000 if worker_limit is None else worker_limit,
            queue_limit=1000 if queue_limit is None else queue_limit,
        )

        orm_query = (
            sa.select(
                sa.column("run_work_pool_id"),
                sa.column("run_work_queue_id"),
                orm_models.FlowRun,
            )
            .from_statement(query)
            # indicate that the state relationship isn't being loaded
            .options(sa.orm.noload(orm_models.FlowRun.state))
        )

        result = await session.execute(orm_query)

        return [
            schemas.responses.WorkerFlowRunResponse(
                work_pool_id=r.run_work_pool_id,
                work_queue_id=r.run_work_queue_id,
                flow_run=schemas.core.FlowRun.model_validate(
                    r.FlowRun, from_attributes=True
                ),
            )
            for r in result
        ]

    async def read_block_documents(
        self,
        session: sa.orm.Session,
        block_document_filter: Optional[schemas.filters.BlockDocumentFilter] = None,
        block_type_filter: Optional[schemas.filters.BlockTypeFilter] = None,
        block_schema_filter: Optional[schemas.filters.BlockSchemaFilter] = None,
        include_secrets: bool = False,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ):
        # if no filter is provided, one is created that excludes anonymous blocks
        if block_document_filter is None:
            block_document_filter = schemas.filters.BlockDocumentFilter(
                is_anonymous=schemas.filters.BlockDocumentFilterIsAnonymous(eq_=False)
            )

        # --- Query for Parent Block Documents
        # begin by building a query for only those block documents that are selected
        # by the provided filters
        filtered_block_documents_query = sa.select(orm_models.BlockDocument.id).where(
            block_document_filter.as_sql_filter()
        )

        if block_type_filter is not None:
            block_type_exists_clause = sa.select(orm_models.BlockType).where(
                orm_models.BlockType.id == orm_models.BlockDocument.block_type_id,
                block_type_filter.as_sql_filter(),
            )
            filtered_block_documents_query = filtered_block_documents_query.where(
                block_type_exists_clause.exists()
            )

        if block_schema_filter is not None:
            block_schema_exists_clause = sa.select(orm_models.BlockSchema).where(
                orm_models.BlockSchema.id == orm_models.BlockDocument.block_schema_id,
                block_schema_filter.as_sql_filter(),
            )
            filtered_block_documents_query = filtered_block_documents_query.where(
                block_schema_exists_clause.exists()
            )

        if offset is not None:
            filtered_block_documents_query = filtered_block_documents_query.offset(
                offset
            )

        if limit is not None:
            filtered_block_documents_query = filtered_block_documents_query.limit(limit)

        filtered_block_documents_query = filtered_block_documents_query.cte(
            "filtered_block_documents"
        )

        # --- Query for Referenced Block Documents
        # next build a recursive query for (potentially nested) block documents
        # that reference the filtered block documents
        block_document_references_query = (
            sa.select(orm_models.BlockDocumentReference)
            .filter(
                orm_models.BlockDocumentReference.parent_block_document_id.in_(
                    sa.select(filtered_block_documents_query.c.id)
                )
            )
            .cte("block_document_references", recursive=True)
        )
        block_document_references_join = sa.select(
            orm_models.BlockDocumentReference
        ).join(
            block_document_references_query,
            orm_models.BlockDocumentReference.parent_block_document_id
            == block_document_references_query.c.reference_block_document_id,
        )
        recursive_block_document_references_cte = (
            block_document_references_query.union_all(block_document_references_join)
        )

        # --- Final Query for All Block Documents
        # build a query that unions:
        # - the filtered block documents
        # - with any block documents that are discovered as (potentially nested) references
        all_block_documents_query = sa.union_all(
            # first select the parent block
            sa.select(
                orm_models.BlockDocument,
                sa.null().label("reference_name"),
                sa.null().label("reference_parent_block_document_id"),
            )
            .select_from(orm_models.BlockDocument)
            .where(
                orm_models.BlockDocument.id.in_(
                    sa.select(filtered_block_documents_query.c.id)
                )
            ),
            #
            # then select any referenced blocks
            sa.select(
                orm_models.BlockDocument,
                recursive_block_document_references_cte.c.name,
                recursive_block_document_references_cte.c.parent_block_document_id,
            )
            .select_from(orm_models.BlockDocument)
            .join(
                recursive_block_document_references_cte,
                orm_models.BlockDocument.id
                == recursive_block_document_references_cte.c.reference_block_document_id,
            ),
        ).cte("all_block_documents_query")

        # the final union query needs to be `aliased` for proper ORM unpacking
        # and also be sorted
        return (
            sa.select(
                sa.orm.aliased(orm_models.BlockDocument, all_block_documents_query),
                all_block_documents_query.c.reference_name,
                all_block_documents_query.c.reference_parent_block_document_id,
            )
            .select_from(all_block_documents_query)
            .order_by(all_block_documents_query.c.name)
        )

    async def read_configuration_value(
        self, session: sa.orm.Session, key: str
    ) -> Optional[Dict]:
        """
        Read a configuration value by key.

        Configuration values should not be changed at run time, so retrieved
        values are cached in memory.

        The main use of configurations is encrypting blocks, this speeds up nested
        block document queries.
        """
        try:
            return self.CONFIGURATION_CACHE[key]
        except KeyError:
            query = sa.select(orm_models.Configuration).where(
                orm_models.Configuration.key == key
            )
            result = await session.execute(query)
            configuration = result.scalar()
            if configuration is not None:
                self.CONFIGURATION_CACHE[key] = configuration.value
                return configuration.value
            return configuration

    def clear_configuration_value_cache_for_key(self, key: str):
        """Removes a configuration key from the cache."""
        self.CONFIGURATION_CACHE.pop(key, None)

    @abstractmethod
    async def flow_run_graph_v2(
        self,
        session: AsyncSession,
        flow_run_id: UUID,
        since: datetime.datetime,
        max_nodes: int,
        max_artifacts: int,
    ) -> Graph:
        """Returns the query that selects all of the nodes and edges for a flow run graph (version 2)."""
        ...

    async def _get_flow_run_graph_artifacts(
        self,
        session: AsyncSession,
        flow_run_id: UUID,
        max_artifacts: int,
    ):
        """Get the artifacts for a flow run grouped by task run id.

        Does not recurse into subflows.
        Artifacts for the flow run without a task run id are grouped under None.
        """
        query = (
            sa.select(
                orm_models.Artifact,
                orm_models.ArtifactCollection.id.label("latest_in_collection_id"),
            )
            .where(
                orm_models.Artifact.flow_run_id == flow_run_id,
                orm_models.Artifact.type != "result",
            )
            .join(
                orm_models.ArtifactCollection,
                (orm_models.ArtifactCollection.key == orm_models.Artifact.key)
                & (orm_models.ArtifactCollection.latest_id == orm_models.Artifact.id),
                isouter=True,
            )
            .order_by(orm_models.Artifact.created.asc())
            .limit(max_artifacts)
        )

        results = await session.execute(query)

        artifacts_by_task = defaultdict(list)
        for artifact, latest_in_collection_id in results:
            artifacts_by_task[artifact.task_run_id].append(
                GraphArtifact(
                    id=artifact.id,
                    created=artifact.created,
                    key=artifact.key,
                    type=artifact.type,
                    # We're only using the data field for progress artifacts for now
                    data=artifact.data if artifact.type == "progress" else None,
                    is_latest=artifact.key is None
                    or latest_in_collection_id is not None,
                )
            )

        return artifacts_by_task

    async def _get_flow_run_graph_states(
        self,
        session: AsyncSession,
        flow_run_id: UUID,
    ):
        """Get the flow run states for a flow run graph."""
        flow_run_states = await models.flow_run_states.read_flow_run_states(
            session=session, flow_run_id=flow_run_id
        )

        return [
            GraphState(
                id=state.id,
                timestamp=state.timestamp,
                type=state.type,
                name=state.name,
            )
            for state in flow_run_states
        ]


class AsyncPostgresQueryComponents(BaseQueryComponents):
    # --- Postgres-specific SqlAlchemy bindings

    def insert(self, obj) -> postgresql.Insert:
        return postgresql.insert(obj)

    def greatest(self, *values):
        return sa.func.greatest(*values)

    def least(self, *values):
        return sa.func.least(*values)

    # --- Postgres-specific JSON handling

    @property
    def uses_json_strings(self):
        return False

    def cast_to_json(self, json_obj):
        return json_obj

    def build_json_object(self, *args):
        return sa.func.jsonb_build_object(*args)

    def json_arr_agg(self, json_array):
        return sa.func.jsonb_agg(json_array)

    # --- Postgres-optimized subqueries

    def make_timestamp_intervals(
        self,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        interval: datetime.timedelta,
    ):
        # validate inputs
        start_time = pendulum.instance(start_time)
        end_time = pendulum.instance(end_time)
        assert isinstance(interval, datetime.timedelta)
        return (
            sa.select(
                sa.literal_column("dt").label("interval_start"),
                (sa.literal_column("dt") + interval).label("interval_end"),
            )
            .select_from(
                sa.func.generate_series(start_time, end_time, interval).alias("dt")
            )
            .where(sa.literal_column("dt") < end_time)
            # grab at most 500 intervals
            .limit(500)
        )

    def set_state_id_on_inserted_flow_runs_statement(
        self,
        fr_model,
        frs_model,
        inserted_flow_run_ids,
        insert_flow_run_states,
    ):
        """Given a list of flow run ids and associated states, set the state_id
        to the appropriate state for all flow runs"""
        # postgres supports `UPDATE ... FROM` syntax
        stmt = (
            sa.update(fr_model)
            .where(
                fr_model.id.in_(inserted_flow_run_ids),
                frs_model.flow_run_id == fr_model.id,
                frs_model.id.in_([r["id"] for r in insert_flow_run_states]),
            )
            .values(state_id=frs_model.id)
            # no need to synchronize as these flow runs are entirely new
            .execution_options(synchronize_session=False)
        )
        return stmt

    async def get_flow_run_notifications_from_queue(
        self, session: AsyncSession, limit: int
    ) -> List:
        # including this as a subquery in the where clause of the
        # `queued_notifications` statement below, leads to errors where the limit
        # is not respected if it is 1. pulling this out into a CTE statement
        # prevents this. see link for more details:
        # https://www.postgresql.org/message-id/16497.1553640836%40sss.pgh.pa.us
        queued_notifications_ids = (
            sa.select(orm_models.FlowRunNotificationQueue.id)
            .select_from(orm_models.FlowRunNotificationQueue)
            .order_by(orm_models.FlowRunNotificationQueue.updated)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).cte("queued_notifications_ids")

        queued_notifications = (
            sa.delete(orm_models.FlowRunNotificationQueue)
            .returning(
                orm_models.FlowRunNotificationQueue.id,
                orm_models.FlowRunNotificationQueue.flow_run_notification_policy_id,
                orm_models.FlowRunNotificationQueue.flow_run_state_id,
            )
            .where(
                orm_models.FlowRunNotificationQueue.id.in_(
                    sa.select(queued_notifications_ids)
                )
            )
            .cte("queued_notifications")
        )

        notification_details_stmt = (
            sa.select(
                queued_notifications.c.id.label("queue_id"),
                orm_models.FlowRunNotificationPolicy.id.label(
                    "flow_run_notification_policy_id"
                ),
                orm_models.FlowRunNotificationPolicy.message_template.label(
                    "flow_run_notification_policy_message_template"
                ),
                orm_models.FlowRunNotificationPolicy.block_document_id,
                orm_models.Flow.id.label("flow_id"),
                orm_models.Flow.name.label("flow_name"),
                orm_models.FlowRun.id.label("flow_run_id"),
                orm_models.FlowRun.name.label("flow_run_name"),
                orm_models.FlowRun.parameters.label("flow_run_parameters"),
                orm_models.FlowRunState.type.label("flow_run_state_type"),
                orm_models.FlowRunState.name.label("flow_run_state_name"),
                orm_models.FlowRunState.timestamp.label("flow_run_state_timestamp"),
                orm_models.FlowRunState.message.label("flow_run_state_message"),
            )
            .select_from(queued_notifications)
            .join(
                orm_models.FlowRunNotificationPolicy,
                queued_notifications.c.flow_run_notification_policy_id
                == orm_models.FlowRunNotificationPolicy.id,
            )
            .join(
                orm_models.FlowRunState,
                queued_notifications.c.flow_run_state_id == orm_models.FlowRunState.id,
            )
            .join(
                orm_models.FlowRun,
                orm_models.FlowRunState.flow_run_id == orm_models.FlowRun.id,
            )
            .join(
                orm_models.Flow,
                orm_models.FlowRun.flow_id == orm_models.Flow.id,
            )
        )

        result = await session.execute(notification_details_stmt)
        return result.fetchall()

    @property
    def _get_scheduled_flow_runs_from_work_pool_template_path(self):
        """
        Template for the query to get scheduled flow runs from a work pool
        """
        return "postgres/get-runs-from-worker-queues.sql.jinja"

    async def flow_run_graph_v2(
        self,
        session: AsyncSession,
        flow_run_id: UUID,
        since: datetime.datetime,
        max_nodes: int,
        max_artifacts: int,
    ) -> Graph:
        """Returns the query that selects all of the nodes and edges for a flow run
        graph (version 2)."""
        result = await session.execute(
            sa.select(
                sa.func.coalesce(
                    orm_models.FlowRun.start_time,
                    orm_models.FlowRun.expected_start_time,
                ),
                orm_models.FlowRun.end_time,
            ).where(
                orm_models.FlowRun.id == flow_run_id,
            )
        )
        try:
            start_time, end_time = result.one()
        except NoResultFound:
            raise ObjectNotFoundError(f"Flow run {flow_run_id} not found")

        query = sa.text(
            """
            WITH
            edges AS (
                SELECT  CASE
                            WHEN subflow.id IS NOT NULL THEN 'flow-run'
                            ELSE 'task-run'
                        END as kind,
                        COALESCE(subflow.id, task_run.id) as id,
                        COALESCE(flow.name || ' / ' || subflow.name, task_run.name) as label,
                        COALESCE(subflow.state_type, task_run.state_type) as state_type,
                        COALESCE(
                            subflow.start_time,
                            subflow.expected_start_time,
                            task_run.start_time,
                            task_run.expected_start_time
                        ) as start_time,
                        COALESCE(
                            subflow.end_time,
                            task_run.end_time,
                            CASE
                                WHEN task_run.state_type = 'COMPLETED'
                                    THEN task_run.expected_start_time
                                ELSE NULL
                            END
                        ) as end_time,
                        (argument->>'id')::uuid as parent,
                        input.key = '__parents__' as has_encapsulating_task
                FROM    task_run
                        LEFT JOIN jsonb_each(task_run.task_inputs) as input ON true
                        LEFT JOIN jsonb_array_elements(input.value) as argument ON true
                        LEFT JOIN flow_run as subflow
                                ON subflow.parent_task_run_id = task_run.id
                        LEFT JOIN flow
                                ON flow.id = subflow.flow_id
                WHERE   task_run.flow_run_id = :flow_run_id AND
                        task_run.state_type <> 'PENDING' AND
                        COALESCE(
                            subflow.start_time,
                            subflow.expected_start_time,
                            task_run.start_time,
                            task_run.expected_start_time
                        ) IS NOT NULL

                -- the order here is important to speed up building the two sets of
                -- edges in the with_parents and with_children CTEs below
                ORDER BY COALESCE(subflow.id, task_run.id)
            ),
            with_encapsulating AS (
                SELECT  children.id,
                        array_agg(parents.id order by parents.start_time) as encapsulating_ids
                FROM    edges as children
                        INNER JOIN edges as parents
                                ON parents.id = children.parent
                WHERE children.has_encapsulating_task is True
                GROUP BY children.id
            ),
            with_parents AS (
                SELECT  children.id,
                        array_agg(parents.id order by parents.start_time) as parent_ids
                FROM    edges as children
                        INNER JOIN edges as parents
                                ON parents.id = children.parent
                WHERE children.has_encapsulating_task is FALSE OR children.has_encapsulating_task is NULL
                GROUP BY children.id
            ),
            with_children AS (
                SELECT  parents.id,
                        array_agg(children.id order by children.start_time) as child_ids
                FROM    edges as parents
                        INNER JOIN edges as children
                                ON children.parent = parents.id
                WHERE children.has_encapsulating_task is FALSE OR children.has_encapsulating_task is NULL
                GROUP BY parents.id
            ),
            nodes AS (
                SELECT  DISTINCT ON (edges.id)
                        edges.kind,
                        edges.id,
                        edges.label,
                        edges.state_type,
                        edges.start_time,
                        edges.end_time,
                        with_parents.parent_ids,
                        with_children.child_ids,
                        with_encapsulating.encapsulating_ids
                FROM    edges
                        LEFT JOIN with_parents
                                ON with_parents.id = edges.id
                        LEFT JOIN with_children
                                ON with_children.id = edges.id
                        LEFT JOIN with_encapsulating
                                ON with_encapsulating.id = edges.id
            )
            SELECT  kind,
                    id,
                    label,
                    state_type,
                    start_time,
                    end_time,
                    parent_ids,
                    child_ids,
                    encapsulating_ids
            FROM    nodes
            WHERE   end_time IS NULL OR end_time >= :since
            ORDER BY start_time, end_time
            LIMIT :max_nodes
            ;
        """
        )

        query = query.bindparams(
            sa.bindparam("flow_run_id", value=flow_run_id),
            sa.bindparam("since", value=since),
            sa.bindparam("max_nodes", value=max_nodes + 1),
        )

        results = await session.execute(query)

        graph_artifacts = await self._get_flow_run_graph_artifacts(
            session, flow_run_id, max_artifacts
        )
        graph_states = await self._get_flow_run_graph_states(session, flow_run_id)

        nodes: List[Tuple[UUID, Node]] = []
        root_node_ids: List[UUID] = []

        for row in results:
            if not row.parent_ids:
                root_node_ids.append(row.id)

            nodes.append(
                (
                    row.id,
                    Node(
                        kind=row.kind,
                        id=row.id,
                        label=row.label,
                        state_type=row.state_type,
                        start_time=row.start_time,
                        end_time=row.end_time,
                        parents=[Edge(id=id) for id in row.parent_ids or []],
                        children=[Edge(id=id) for id in row.child_ids or []],
                        encapsulating=[
                            Edge(id=id) for id in row.encapsulating_ids or []
                        ],
                        artifacts=graph_artifacts.get(row.id, []),
                    ),
                )
            )

            if len(nodes) > max_nodes:
                raise FlowRunGraphTooLarge(
                    f"The graph of flow run {flow_run_id} has more than "
                    f"{max_nodes} nodes."
                )

        return Graph(
            start_time=start_time,
            end_time=end_time,
            root_node_ids=root_node_ids,
            nodes=nodes,
            artifacts=graph_artifacts.get(None, []),
            states=graph_states,
        )


class AioSqliteQueryComponents(BaseQueryComponents):
    # --- Sqlite-specific SqlAlchemy bindings

    def insert(self, obj) -> sqlite.Insert:
        return sqlite.insert(obj)

    def greatest(self, *values):
        return sa.func.max(*values)

    def least(self, *values):
        return sa.func.min(*values)

    # --- Sqlite-specific JSON handling

    @property
    def uses_json_strings(self):
        return True

    def cast_to_json(self, json_obj):
        return sa.func.json(json_obj)

    def build_json_object(self, *args):
        return sa.func.json_object(*args)

    def json_arr_agg(self, json_array):
        return sa.func.json_group_array(json_array)

    # --- Sqlite-optimized subqueries

    def make_timestamp_intervals(
        self,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        interval: datetime.timedelta,
    ):
        from prefect.server.utilities.database import Timestamp

        # validate inputs
        start_time = pendulum.instance(start_time)
        end_time = pendulum.instance(end_time)
        assert isinstance(interval, datetime.timedelta)

        return (
            sa.text(
                r"""
                -- recursive CTE to mimic the behavior of `generate_series`,
                -- which is only available as a compiled extension
                WITH RECURSIVE intervals(interval_start, interval_end, counter) AS (
                    VALUES(
                        strftime('%Y-%m-%d %H:%M:%f000', :start_time),
                        strftime('%Y-%m-%d %H:%M:%f000', :start_time, :interval),
                        1
                        )

                    UNION ALL

                    SELECT interval_end, strftime('%Y-%m-%d %H:%M:%f000', interval_end, :interval), counter + 1
                    FROM intervals
                    -- subtract interval because recursive where clauses are effectively evaluated on a t-1 lag
                    WHERE
                        interval_start < strftime('%Y-%m-%d %H:%M:%f000', :end_time, :negative_interval)
                        -- don't compute more than 500 intervals
                        AND counter < 500
                )
                SELECT * FROM intervals
                """
            )
            .bindparams(
                start_time=str(start_time),
                end_time=str(end_time),
                interval=f"+{interval.total_seconds()} seconds",
                negative_interval=f"-{interval.total_seconds()} seconds",
            )
            .columns(interval_start=Timestamp(), interval_end=Timestamp())
        )

    def set_state_id_on_inserted_flow_runs_statement(
        self,
        fr_model,
        frs_model,
        inserted_flow_run_ids,
        insert_flow_run_states,
    ):
        """Given a list of flow run ids and associated states, set the state_id
        to the appropriate state for all flow runs"""
        # sqlite requires a correlated subquery to update from another table
        subquery = (
            sa.select(frs_model.id)
            .where(
                frs_model.flow_run_id == fr_model.id,
                frs_model.id.in_([r["id"] for r in insert_flow_run_states]),
            )
            .limit(1)
            .scalar_subquery()
        )
        stmt = (
            sa.update(fr_model)
            .where(
                fr_model.id.in_(inserted_flow_run_ids),
            )
            .values(state_id=subquery)
            # no need to synchronize as these flow runs are entirely new
            .execution_options(synchronize_session=False)
        )
        return stmt

    async def get_flow_run_notifications_from_queue(
        self, session: AsyncSession, limit: int
    ) -> List:
        """
        Sqlalchemy has no support for DELETE RETURNING in sqlite (as of May 2022)
        so instead we issue two queries; one to get queued notifications and a second to delete
        them. This *could* introduce race conditions if multiple queue workers are
        running.
        """

        notification_details_stmt = (
            sa.select(
                orm_models.FlowRunNotificationQueue.id.label("queue_id"),
                orm_models.FlowRunNotificationPolicy.id.label(
                    "flow_run_notification_policy_id"
                ),
                orm_models.FlowRunNotificationPolicy.message_template.label(
                    "flow_run_notification_policy_message_template"
                ),
                orm_models.FlowRunNotificationPolicy.block_document_id,
                orm_models.Flow.id.label("flow_id"),
                orm_models.Flow.name.label("flow_name"),
                orm_models.FlowRun.id.label("flow_run_id"),
                orm_models.FlowRun.name.label("flow_run_name"),
                orm_models.FlowRun.parameters.label("flow_run_parameters"),
                orm_models.FlowRunState.type.label("flow_run_state_type"),
                orm_models.FlowRunState.name.label("flow_run_state_name"),
                orm_models.FlowRunState.timestamp.label("flow_run_state_timestamp"),
                orm_models.FlowRunState.message.label("flow_run_state_message"),
            )
            .select_from(orm_models.FlowRunNotificationQueue)
            .join(
                orm_models.FlowRunNotificationPolicy,
                orm_models.FlowRunNotificationQueue.flow_run_notification_policy_id
                == orm_models.FlowRunNotificationPolicy.id,
            )
            .join(
                orm_models.FlowRunState,
                orm_models.FlowRunNotificationQueue.flow_run_state_id
                == orm_models.FlowRunState.id,
            )
            .join(
                orm_models.FlowRun,
                orm_models.FlowRunState.flow_run_id == orm_models.FlowRun.id,
            )
            .join(
                orm_models.Flow,
                orm_models.FlowRun.flow_id == orm_models.Flow.id,
            )
            .order_by(orm_models.FlowRunNotificationQueue.updated)
            .limit(limit)
        )

        result = await session.execute(notification_details_stmt)
        notifications = result.fetchall()

        # delete the notifications
        delete_stmt = (
            sa.delete(orm_models.FlowRunNotificationQueue)
            .where(
                orm_models.FlowRunNotificationQueue.id.in_(
                    [n.queue_id for n in notifications]
                )
            )
            .execution_options(synchronize_session="fetch")
        )

        await session.execute(delete_stmt)

        return notifications

    async def _handle_filtered_block_document_ids(
        self, session, filtered_block_documents_query
    ):
        """
        On SQLite, including the filtered block document parameters confuses the
        compiler and it passes positional parameters in the wrong order (it is
        unclear why; SQLalchemy manual compilation works great. Switching to
        `named` paramstyle also works but fails elsewhere in the codebase). To
        resolve this, we materialize the filtered id query into a literal set of
        IDs rather than leaving it as a SQL select.
        """
        result = await session.execute(filtered_block_documents_query)
        return result.scalars().all()

    def _get_scheduled_flow_runs_join(
        self,
        work_queue_query,
        limit_per_queue: Optional[int],
        scheduled_before: Optional[datetime.datetime],
    ):
        # precompute for readability
        scheduled_before_clause = (
            orm_models.FlowRun.next_scheduled_start_time <= scheduled_before
            if scheduled_before is not None
            else True
        )

        # select scheduled flow runs, ordered by scheduled start time per queue
        scheduled_flow_runs = (
            sa.select(
                (
                    sa.func.row_number()
                    .over(
                        partition_by=[orm_models.FlowRun.work_queue_name],
                        order_by=orm_models.FlowRun.next_scheduled_start_time,
                    )
                    .label("rank")
                ),
                orm_models.FlowRun,
            )
            .where(
                orm_models.FlowRun.state_type == "SCHEDULED",
                scheduled_before_clause,
            )
            .subquery("scheduled_flow_runs")
        )

        # sqlite short-circuits the `min` comparison on nulls, so we use `999999`
        # as an "unlimited" limit.
        limit = 999999 if limit_per_queue is None else limit_per_queue

        # in the join, only keep flow runs whose rank is less than or equal to the
        # available slots for each queue
        join_criteria = sa.and_(
            self._flow_run_work_queue_join_clause(
                scheduled_flow_runs.c, orm_models.WorkQueue
            ),
            scheduled_flow_runs.c.rank
            <= sa.func.min(
                sa.func.coalesce(work_queue_query.c.available_slots, limit), limit
            ),
        )
        return scheduled_flow_runs, join_criteria

    # -------------------------------------------------------
    # Workers
    # -------------------------------------------------------

    @property
    def _get_scheduled_flow_runs_from_work_pool_template_path(self):
        """
        Template for the query to get scheduled flow runs from a work pool
        """
        return "sqlite/get-runs-from-worker-queues.sql.jinja"

    async def flow_run_graph_v2(
        self,
        session: AsyncSession,
        flow_run_id: UUID,
        since: datetime.datetime,
        max_nodes: int,
        max_artifacts: int,
    ) -> Graph:
        """Returns the query that selects all of the nodes and edges for a flow run
        graph (version 2)."""
        result = await session.execute(
            sa.select(
                sa.func.coalesce(
                    orm_models.FlowRun.start_time,
                    orm_models.FlowRun.expected_start_time,
                ),
                orm_models.FlowRun.end_time,
            ).where(
                orm_models.FlowRun.id == flow_run_id,
            )
        )
        try:
            start_time, end_time = result.one()
        except NoResultFound:
            raise ObjectNotFoundError(f"Flow run {flow_run_id} not found")

        query = sa.text(
            """
            WITH
            edges AS (
                SELECT  CASE
                            WHEN subflow.id IS NOT NULL THEN 'flow-run'
                            ELSE 'task-run'
                        END as kind,
                        COALESCE(subflow.id, task_run.id) as id,
                        COALESCE(flow.name || ' / ' || subflow.name, task_run.name) as label,
                        COALESCE(subflow.state_type, task_run.state_type) as state_type,
                        COALESCE(
                            subflow.start_time,
                            subflow.expected_start_time,
                            task_run.start_time,
                            task_run.expected_start_time
                        ) as start_time,
                        COALESCE(
                            subflow.end_time,
                            task_run.end_time,
                            CASE
                                WHEN task_run.state_type = 'COMPLETED'
                                    THEN task_run.expected_start_time
                                ELSE NULL
                            END
                        ) as end_time,
                        json_extract(argument.value, '$.id') as parent,
                        input.key = '__parents__' as has_encapsulating_task
                FROM    task_run
                        LEFT JOIN json_each(task_run.task_inputs) as input ON true
                        LEFT JOIN json_each(input.value) as argument ON true
                        LEFT JOIN flow_run as subflow
                                ON subflow.parent_task_run_id = task_run.id
                        LEFT JOIN flow
                                ON flow.id = subflow.flow_id
                WHERE   task_run.flow_run_id = :flow_run_id AND
                        task_run.state_type <> 'PENDING' AND
                        COALESCE(
                            subflow.start_time,
                            subflow.expected_start_time,
                            task_run.start_time,
                            task_run.expected_start_time
                        ) IS NOT NULL

                -- the order here is important to speed up building the two sets of
                -- edges in the with_parents and with_children CTEs below
                ORDER BY COALESCE(subflow.id, task_run.id)
            ),
            with_encapsulating AS (
                SELECT  children.id,
                        group_concat(parents.id) as encapsulating_ids
                FROM    edges as children
                        INNER JOIN edges as parents
                                ON parents.id = children.parent
                WHERE children.has_encapsulating_task IS TRUE
                GROUP BY children.id
            ),
            with_parents AS (
                SELECT  children.id,
                        group_concat(parents.id) as parent_ids
                FROM    edges as children
                        INNER JOIN edges as parents
                                ON parents.id = children.parent
                WHERE children.has_encapsulating_task is FALSE OR children.has_encapsulating_task IS NULL
                GROUP BY children.id
            ),
            with_children AS (
                SELECT  parents.id,
                        group_concat(children.id) as child_ids
                FROM    edges as parents
                        INNER JOIN edges as children
                                ON children.parent = parents.id
                WHERE children.has_encapsulating_task IS FALSE OR children.has_encapsulating_task IS NULL
                GROUP BY parents.id
            ),
            nodes AS (
                SELECT  DISTINCT
                        edges.id,
                        edges.kind,
                        edges.id,
                        edges.label,
                        edges.state_type,
                        edges.start_time,
                        edges.end_time,
                        with_parents.parent_ids,
                        with_children.child_ids,
                        with_encapsulating.encapsulating_ids
                FROM    edges
                        LEFT JOIN with_parents
                                ON with_parents.id = edges.id
                        LEFT JOIN with_children
                                ON with_children.id = edges.id
                        LEFT JOIN with_encapsulating
                                ON with_encapsulating.id = edges.id
            )
            SELECT  kind,
                    id,
                    label,
                    state_type,
                    start_time,
                    end_time,
                    parent_ids,
                    child_ids,
                    encapsulating_ids
            FROM    nodes
            WHERE   end_time IS NULL OR end_time >= :since
            ORDER BY start_time, end_time
            LIMIT :max_nodes
            ;
        """
        )

        # SQLite needs this to be a Python datetime object
        since = datetime.datetime(
            since.year,
            since.month,
            since.day,
            since.hour,
            since.minute,
            since.second,
            since.microsecond,
            tzinfo=since.tzinfo,
        )

        query = query.bindparams(
            sa.bindparam("flow_run_id", value=str(flow_run_id)),
            sa.bindparam("since", value=since),
            sa.bindparam("max_nodes", value=max_nodes + 1),
        )

        results = await session.execute(query)

        graph_artifacts = await self._get_flow_run_graph_artifacts(
            session, flow_run_id, max_artifacts
        )
        graph_states = await self._get_flow_run_graph_states(session, flow_run_id)

        nodes: List[Tuple[UUID, Node]] = []
        root_node_ids: List[UUID] = []

        for row in results:
            if not row.parent_ids:
                root_node_ids.append(row.id)

            # With SQLite, some of the values are returned as strings rather than
            # native Python objects, as they would be from PostgreSQL.  These functions
            # help smooth over those differences.

            def edges(
                value: Union[str, Sequence[UUID], Sequence[str], None],
            ) -> List[UUID]:
                if not value:
                    return []
                if isinstance(value, str):
                    return [Edge(id=id) for id in value.split(",")]
                return [Edge(id=id) for id in value]

            def time(
                value: Union[str, datetime.datetime, None],
            ) -> Optional[pendulum.DateTime]:
                if not value:
                    return None
                if isinstance(value, str):
                    return cast(pendulum.DateTime, pendulum.parse(value))
                return pendulum.instance(value)

            nodes.append(
                (
                    row.id,
                    Node(
                        kind=row.kind,
                        id=row.id,
                        label=row.label,
                        state_type=row.state_type,
                        start_time=time(row.start_time),
                        end_time=time(row.end_time),
                        parents=edges(row.parent_ids),
                        children=edges(row.child_ids),
                        encapsulating=edges(row.encapsulating_ids),
                        artifacts=graph_artifacts.get(UUID(row.id), []),
                    ),
                )
            )

            if len(nodes) > max_nodes:
                raise FlowRunGraphTooLarge(
                    f"The graph of flow run {flow_run_id} has more than "
                    f"{max_nodes} nodes."
                )

        return Graph(
            start_time=start_time,
            end_time=end_time,
            root_node_ids=root_node_ids,
            nodes=nodes,
            artifacts=graph_artifacts.get(None, []),
            states=graph_states,
        )
