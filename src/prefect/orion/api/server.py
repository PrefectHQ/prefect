from fastapi import FastAPI, Request, Response
from prefect.orion.utilities.database import Session

app = FastAPI()


@app.get("/hello")
def hello():
    return "👋"
