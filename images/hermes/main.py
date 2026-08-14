from fastapi import FastAPI
import os
app = FastAPI()

@app.get("/")
async def root():
    key = os.environ.get("OPENAI_API_KEY", "")
    return {"status": "ok", "agent": "hermes", "key_prefix": key[:6], "base_url": os.environ.get("OPENAI_BASE_URL", "")}
