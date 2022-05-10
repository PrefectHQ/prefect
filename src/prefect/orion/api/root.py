"""
Contains the `hello` route for testing and healthcheck purposes.
"""

from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="", tags=["Root"])


@router.get("/hello")
async def hello():
    """Say hello!"""
    return "👋"
