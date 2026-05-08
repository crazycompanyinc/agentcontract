"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI

from agentcontract.server.routes import router


def create_app() -> FastAPI:
    app = FastAPI(title="AgentContract", version="0.1.0")
    app.include_router(router)
    return app


app = create_app()
