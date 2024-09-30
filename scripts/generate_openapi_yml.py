import os

import yaml
from fastapi.openapi.utils import get_openapi

from prefect.server.api.server import create_api_app  # type: ignore

app = create_api_app()

schema = get_openapi(title=app.title, version=app.version, routes=app.routes)

OPENAPI_YAML_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "src",
    "prefect",
    "_internal",
    "openapi.yml",
)

with open(OPENAPI_YAML_PATH, "w+") as file:
    yaml.dump(schema, file, sort_keys=False)

del app
