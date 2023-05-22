from fastapi import FastAPI
import uvicorn

app = FastAPI()


@app.get("/health")
async def check_health():
    return {"status": "OK"}


def run_healthcheck_server():
    uvicorn.run(app, host="0.0.0.0", port=8080)
