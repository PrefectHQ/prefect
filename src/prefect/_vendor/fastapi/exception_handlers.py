from prefect._vendor.fastapi.encoders import jsonable_encoder
from prefect._vendor.fastapi.exceptions import (
    RequestValidationError,
    WebSocketRequestValidationError,
)
from prefect._vendor.fastapi.utils import is_body_allowed_for_status_code
from prefect._vendor.fastapi.websockets import WebSocket
from prefect._vendor.starlette.exceptions import HTTPException
from prefect._vendor.starlette.requests import Request
from prefect._vendor.starlette.responses import JSONResponse, Response
from prefect._vendor.starlette.status import (
    HTTP_422_UNPROCESSABLE_ENTITY,
    WS_1008_POLICY_VIOLATION,
)


async def http_exception_handler(request: Request, exc: HTTPException) -> Response:
    headers = getattr(exc, "headers", None)
    if not is_body_allowed_for_status_code(exc.status_code):
        return Response(status_code=exc.status_code, headers=headers)
    return JSONResponse(
        {"detail": exc.detail}, status_code=exc.status_code, headers=headers
    )


async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": jsonable_encoder(exc.errors())},
    )


async def websocket_request_validation_exception_handler(
    websocket: WebSocket, exc: WebSocketRequestValidationError
) -> None:
    await websocket.close(
        code=WS_1008_POLICY_VIOLATION, reason=jsonable_encoder(exc.errors())
    )
