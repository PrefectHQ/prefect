from typing import Any, Dict, Optional, Sequence, Type

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import BaseModel, ValidationError, create_model
    from pydantic.v1.error_wrappers import ErrorList
else:
    from pydantic import BaseModel, ValidationError, create_model
    from pydantic.error_wrappers import ErrorList

from prefect._vendor.starlette.exceptions import HTTPException as StarletteHTTPException
from prefect._vendor.starlette.exceptions import (
    WebSocketException as WebSocketException,  # noqa: F401
)


class HTTPException(StarletteHTTPException):
    def __init__(
        self,
        status_code: int,
        detail: Any = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail, headers=headers)


RequestErrorModel: Type[BaseModel] = create_model("Request")
WebSocketErrorModel: Type[BaseModel] = create_model("WebSocket")


class FastAPIError(RuntimeError):
    """
    A generic, FastAPI-specific error.
    """


class RequestValidationError(ValidationError):
    def __init__(self, errors: Sequence[ErrorList], *, body: Any = None) -> None:
        self.body = body
        super().__init__(errors, RequestErrorModel)


class WebSocketRequestValidationError(ValidationError):
    def __init__(self, errors: Sequence[ErrorList]) -> None:
        super().__init__(errors, WebSocketErrorModel)
