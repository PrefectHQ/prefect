from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
async def check_health():
    return {"status": "OK"}
