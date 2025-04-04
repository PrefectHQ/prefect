from typing import get_args

from prefect.client.orchestration.routes import ServerRoutes
from prefect.server.api.server import create_api_app


def test_server_routes_match_openapi_schema():
    """Test that all ServerRoutes are present in the OpenAPI schema"""
    app = create_api_app()
    openapi_schema = app.openapi()

    # Extract paths from OpenAPI schema
    openapi_paths = set(openapi_schema["paths"].keys())

    # Convert ServerRoutes to set for comparison using typing.get_args()
    server_routes = set(get_args(ServerRoutes)) - {"/deployments/{id}/branch"}

    # Find any missing routes
    missing_routes = server_routes - openapi_paths

    # Print missing routes in an easy to read format if any exist
    if missing_routes:
        print("\nMissing routes:")
        for route in sorted(missing_routes):
            print(route)  # Remove the indentation to avoid concatenation
            print()  # Add blank line between routes for readability

    # Assert ServerRoutes are subset of OpenAPI paths
    assert not missing_routes, (
        f"{len(missing_routes)} routes are missing from OpenAPI schema"
    )
