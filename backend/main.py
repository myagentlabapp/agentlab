"""FastAPI application entrypoint for the agent tenant platform."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import init_db
from routes.agents import router as agents_router
from routes.deploy import router as deploy_router
from routes.status import router as status_router
from routes.stop import router as stop_router
from routes.admin import router as admin_router
from routes.auth import router as auth_router
from routes.public_settings import router as public_settings_router
from routes.payment import router as payment_router

app = FastAPI(title="Agent Tenant Platform")

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


app.include_router(agents_router)
app.include_router(deploy_router)
app.include_router(stop_router)
app.include_router(admin_router)
app.include_router(status_router)
app.include_router(auth_router)
app.include_router(public_settings_router)
app.include_router(payment_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
