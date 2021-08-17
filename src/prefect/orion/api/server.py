# import prefect
from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware

from prefect.orion import api
from prefect.orion.schemas import schedules

app = FastAPI(title="Prefect Orion", version="alpha")

# middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# routers
app.include_router(api.data.router)
app.include_router(api.flows.router)
app.include_router(api.flow_runs.router)
app.include_router(api.task_runs.router)
app.include_router(api.flow_run_states.router)
app.include_router(api.task_run_states.router)


@app.get("/hello", tags=["debug"])
def hello():
    return "👋"


@app.get("/echo", tags=["debug"])
def echo(x: str):
    return x
