"""
Routes for interacting with log objects.
"""

from typing import List

from fastapi import Body, Depends, WebSocket, status
from starlette.status import WS_1002_PROTOCOL_ERROR

import prefect.server.api.dependencies as dependencies
import prefect.server.models as models
import prefect.server.schemas as schemas
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.logs import stream
from prefect.server.utilities import subscriptions
from prefect.server.utilities.server import PrefectRouter

router: PrefectRouter = PrefectRouter(prefix="/logs", tags=["Logs"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_logs(
    logs: List[schemas.actions.LogCreate],
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """
    Create new logs from the provided schema.

    For more information, see https://docs.prefect.io/v3/develop/logging.
    """
    for batch in models.logs.split_logs_into_batches(logs):
        async with db.session_context(begin_transaction=True) as session:
            await models.logs.create_logs(session=session, logs=batch)


@router.post("/filter")
async def read_logs(
    limit: int = dependencies.LimitBody(),
    offset: int = Body(0, ge=0),
    logs: schemas.filters.LogFilter = None,
    sort: schemas.sorting.LogSort = Body(schemas.sorting.LogSort.TIMESTAMP_ASC),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> List[schemas.core.Log]:
    """
    Query for logs.
    """
    async with db.session_context() as session:
        return await models.logs.read_logs(
            session=session, log_filter=logs, offset=offset, limit=limit, sort=sort
        )


@router.websocket("/out")
async def stream_logs_out(
    websocket: WebSocket,
) -> None:
    """Serve a WebSocket to stream live logs"""
    websocket = await subscriptions.accept_prefect_socket(
        websocket,
    )
    if not websocket:
        return

    try:
        # After authentication, the next message is expected to be a filter message, any
        # other type of message will close the connection.
        message = await websocket.receive_json()

        if message["type"] != "filter":
            return await websocket.close(
                WS_1002_PROTOCOL_ERROR, reason="Expected 'filter' message"
            )

        try:
            filter = schemas.filters.LogFilter.model_validate(message["filter"])
        except Exception as e:
            return await websocket.close(
                WS_1002_PROTOCOL_ERROR, reason=f"Invalid filter: {e}"
            )

        # No backfill support for logs - only live streaming
        # Subscribe to the ongoing log stream
        async with stream.logs(filter) as log_stream:
            async for log in log_stream:
                if not log:
                    if await subscriptions.still_connected(websocket):
                        continue
                    break

                await websocket.send_json(
                    {"type": "log", "log": log.model_dump(mode="json")}
                )

    except subscriptions.NORMAL_DISCONNECT_EXCEPTIONS:  # pragma: no cover
        pass  # it's fine if a client disconnects either normally or abnormally

    return None
