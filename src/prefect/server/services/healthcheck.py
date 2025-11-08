import uvicorn
from fastapi import APIRouter, FastAPI, status
from fastapi.responses import JSONResponse


def build_healthcheck_server() -> uvicorn.Server:
    """
    Build a healthcheck FastAPI server for the Prefect background services.
    """
    app = FastAPI()
    router = APIRouter()

    def healthcheck() -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "OK"})

    router.add_api_route("/health", healthcheck, methods=["GET"])
    app.include_router(router)

    config = uvicorn.Config(app=app, host="0.0.0.0", port=8080)
    return uvicorn.Server(config=config)
