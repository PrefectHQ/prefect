from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware

from prefect.orion import api

app = FastAPI()

# routers
app.include_router(api.flows.router)

# middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/hello", tags=["meta"])
def hello():
    return "👋"
