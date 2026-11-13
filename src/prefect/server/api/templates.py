from typing import Any

import orjson
from fastapi import Body, Response
from jinja2.exceptions import TemplateSyntaxError

from prefect.server.schemas.responses import TemplateValidationErrorResponse
from prefect.server.utilities.server import PrefectRouter
from prefect.server.utilities.user_templates import (
    TemplateSecurityError,
    validate_user_template,
)

router: PrefectRouter = PrefectRouter(tags=["Automations"])

_TEMPLATE_VALIDATION_RESPONSES: dict[int | str, dict[str, Any]] = {
    422: {"model": TemplateValidationErrorResponse}
}


# deprecated and can be removed after the ui removes its dependency on it
# use /templates/validate instead
@router.post(
    "/automations/templates/validate",
    response_class=Response,
    responses=_TEMPLATE_VALIDATION_RESPONSES,
)
@router.post(
    "/templates/validate",
    response_class=Response,
    responses=_TEMPLATE_VALIDATION_RESPONSES,
)
def validate_template(template: str = Body(default="")) -> Response:
    try:
        validate_user_template(template)
        return Response(content="", status_code=204)
    except (TemplateSyntaxError, TemplateSecurityError) as e:
        return Response(
            status_code=422,
            media_type="application/json",
            content=orjson.dumps(
                {
                    "error": {
                        "line": e.lineno,
                        "message": e.message,
                        "source": template,
                    },
                }
            ),
        )
