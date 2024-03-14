from typing import Awaitable, Callable

import orjson
from prefect._vendor.fastapi import status
from prefect._vendor.starlette.middleware.base import BaseHTTPMiddleware
from prefect._vendor.starlette.requests import Request
from prefect._vendor.starlette.responses import Response

from prefect import settings
from prefect.server import models
from prefect.server.database.dependencies import provide_database_interface

NextMiddlewareFunction = Callable[[Request], Awaitable[Response]]


class CsrfMiddleware(BaseHTTPMiddleware):
    """
    Middleware for CSRF protection. This middleware will check for a CSRF token
    in the headers of any POST, PUT, PATCH, or DELETE request. If the token is
    not present or does not match the token stored in the database for the
    client, the request will be rejected with a 403 status code.
    """

    async def dispatch(
        self, request: Request, call_next: NextMiddlewareFunction
    ) -> Response:
        """
        Dispatch method for the middleware. This method will check for the
        presence of a CSRF token in the headers of the request and compare it
        to the token stored in the database for the client. If the token is not
        present or does not match, the request will be rejected with a 403
        status code.
        """

        request_needs_csrf_protection = request.method in {
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
        }

        if (
            settings.PREFECT_SERVER_CSRF_PROTECTION_ENABLED.value()
            and request_needs_csrf_protection
        ):
            db = provide_database_interface()
            incoming_token = request.headers.get("Prefect-Csrf-Token")
            incoming_client = request.headers.get("Prefect-Csrf-Client")

            async with db.session_context() as session:
                token = await models.csrf_token.read_token_for_client(
                    session=session, client=incoming_client
                )

                if token is None or token.token != incoming_token:
                    return Response(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content=orjson.dumps({"detail": "Invalid CSRF token"}),
                        media_type="application/json",
                    )

        return await call_next(request)
