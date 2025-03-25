import orjson
from fastapi import Body, Response
from jinja2.exceptions import TemplateSyntaxError

from prefect.server.utilities.server import PrefectRouter
from prefect.server.utilities.user_templates import (
    TemplateSecurityError,
    validate_user_template,
)

router: PrefectRouter = PrefectRouter(prefix="/templates", tags=["Automations"])


@router.post(
    "/validate",
    response_class=Response,
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
