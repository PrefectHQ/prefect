from typing import Optional

from prefect._vendor.fastapi.openapi.models import OpenIdConnect as OpenIdConnectModel
from prefect._vendor.fastapi.security.base import SecurityBase
from prefect._vendor.starlette.exceptions import HTTPException
from prefect._vendor.starlette.requests import Request
from prefect._vendor.starlette.status import HTTP_403_FORBIDDEN


class OpenIdConnect(SecurityBase):
    def __init__(
        self,
        *,
        openIdConnectUrl: str,
        scheme_name: Optional[str] = None,
        description: Optional[str] = None,
        auto_error: bool = True,
    ):
        self.model = OpenIdConnectModel(
            openIdConnectUrl=openIdConnectUrl, description=description
        )
        self.scheme_name = scheme_name or self.__class__.__name__
        self.auto_error = auto_error

    async def __call__(self, request: Request) -> Optional[str]:
        authorization = request.headers.get("Authorization")
        if not authorization:
            if self.auto_error:
                raise HTTPException(
                    status_code=HTTP_403_FORBIDDEN, detail="Not authenticated"
                )
            else:
                return None
        return authorization
