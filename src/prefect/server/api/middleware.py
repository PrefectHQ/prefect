from typing import Awaitable, Callable

from fastapi import status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from prefect import settings
from prefect.server import models
from prefect.server.database import provide_database_interface

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
            incoming_token = request.headers.get("Prefect-Csrf-Token")
            incoming_client = request.headers.get("Prefect-Csrf-Client")

            if incoming_token is None:
                return JSONResponse(
                    {"detail": "Missing CSRF token."},
                    status_code=status.HTTP_403_FORBIDDEN,
                )

            if incoming_client is None:
                return JSONResponse(
                    {"detail": "Missing client identifier."},
                    status_code=status.HTTP_403_FORBIDDEN,
                )

            db = provide_database_interface()
            async with db.session_context() as session:
                token = await models.csrf_token.read_token_for_client(
                    session=session, client=incoming_client
                )

                if token is None or token.token != incoming_token:
                    return JSONResponse(
                        {"detail": "Invalid CSRF token or client identifier."},
                        status_code=status.HTTP_403_FORBIDDEN,
                        headers={"Access-Control-Allow-Origin": "*"},
                    )

        return await call_next(request)
