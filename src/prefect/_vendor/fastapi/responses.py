from typing import Any

from prefect._vendor.starlette.responses import FileResponse as FileResponse  # noqa
from prefect._vendor.starlette.responses import HTMLResponse as HTMLResponse  # noqa
from prefect._vendor.starlette.responses import JSONResponse as JSONResponse  # noqa
from prefect._vendor.starlette.responses import (
    PlainTextResponse as PlainTextResponse,  # noqa
)
from prefect._vendor.starlette.responses import (
    RedirectResponse as RedirectResponse,  # noqa
)
from prefect._vendor.starlette.responses import Response as Response  # noqa
from prefect._vendor.starlette.responses import (
    StreamingResponse as StreamingResponse,  # noqa
)

try:
    import ujson
except ImportError:  # pragma: nocover
    ujson = None  # type: ignore


try:
    import orjson
except ImportError:  # pragma: nocover
    orjson = None  # type: ignore


class UJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        assert ujson is not None, "ujson must be installed to use UJSONResponse"
        return ujson.dumps(content, ensure_ascii=False).encode("utf-8")


class ORJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        assert orjson is not None, "orjson must be installed to use ORJSONResponse"
        return orjson.dumps(
            content, option=orjson.OPT_NON_STR_KEYS | orjson.OPT_SERIALIZE_NUMPY
        )
