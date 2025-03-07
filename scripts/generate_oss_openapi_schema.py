import json

from prefect.server.api.server import create_api_app

app = create_api_app()
openapi_schema = app.openapi()

with open("oss_schema.json", "w") as f:
    json.dump(openapi_schema, f)
