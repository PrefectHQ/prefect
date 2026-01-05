import json

from prefect.server.api.server import create_api_app, create_ui_app

# Generate schema from main API app
api_app = create_api_app()
openapi_schema = api_app.openapi()

# Generate schema from UI app and merge relevant routes
ui_app = create_ui_app(ephemeral=True)
ui_schema = ui_app.openapi()

# Merge /ui-settings path from ui_app into main schema
for path, path_item in ui_schema.get("paths", {}).items():
    if "ui-settings" in path:
        # Use the path without any base URL prefix
        openapi_schema["paths"]["/ui-settings"] = path_item

# Merge UISettings schema component
for schema_name, schema_def in (
    ui_schema.get("components", {}).get("schemas", {}).items()
):
    if schema_name not in openapi_schema.get("components", {}).get("schemas", {}):
        openapi_schema["components"]["schemas"][schema_name] = schema_def

with open("oss_schema.json", "w") as f:
    json.dump(openapi_schema, f)
