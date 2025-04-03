from sqlalchemy import event
from prefect.server.database.orm_models import WorkPool, WorkQueue
from prefect.events.utilities import emit_event
import logging

logger = logging.getLogger("prefect.events")

def handle_event(mapper, connection, target, event_type):
    """
    Emits an event when WorkPool or WorkQueue is created, updated, or deleted.
    """
    logger.info(f"Emitting event: {event_type} for {target}")

    emit_event(
        event=event_type,
        resource={"prefect.resource.id": str(target.id), "name": target.name},
        related=[],
    )

# Attach event listeners for WorkPool
event.listen(WorkPool, "after_insert", lambda m, c, t: handle_event(m, c, t, "WorkPool.Created"))
event.listen(WorkPool, "after_update", lambda m, c, t: handle_event(m, c, t, "WorkPool.Updated"))
event.listen(WorkPool, "after_delete", lambda m, c, t: handle_event(m, c, t, "WorkPool.Deleted"))

# Attach event listeners for WorkQueue
event.listen(WorkQueue, "after_insert", lambda m, c, t: handle_event(m, c, t, "WorkQueue.Created"))
event.listen(WorkQueue, "after_update", lambda m, c, t: handle_event(m, c, t, "WorkQueue.Updated"))
event.listen(WorkQueue, "after_delete", lambda m, c, t: handle_event(m, c, t, "WorkQueue.Deleted"))
