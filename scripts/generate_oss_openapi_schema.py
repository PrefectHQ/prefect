import argparse
import json

from prefect.server.api.server import create_api_app, create_ui_app

parser = argparse.ArgumentParser()
parser.add_argument("--api-compatibility", action="store_true")
args = parser.parse_args()

api_app = create_api_app()
openapi_schema = api_app.openapi()

if args.api_compatibility:
    # The shared suite expects the API mount prefix and excludes the root UI.
    openapi_schema["paths"] = {
        f"/api{path}": item for path, item in openapi_schema["paths"].items()
    }
else:
    # UI type generation also needs the root webserver's settings endpoint.
    ui_app = create_ui_app(ephemeral=True)
    ui_schema = ui_app.openapi()
    for path, path_item in ui_schema.get("paths", {}).items():
        if "ui-settings" in path:
            openapi_schema["paths"]["/ui-settings"] = path_item
    for schema_name, schema_def in (
        ui_schema.get("components", {}).get("schemas", {}).items()
    ):
        if schema_name not in openapi_schema.get("components", {}).get("schemas", {}):
            openapi_schema["components"]["schemas"][schema_name] = schema_def

with open("oss_schema.json", "w") as f:
    json.dump(openapi_schema, f)
