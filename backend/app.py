import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from backend.ports import AgentPort
from backend.adapters.fixture_agent import FixtureAgentPort
from backend.db import Database


def create_app(agent_port: AgentPort | None = None, *, database_path=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        app.state.agent = agent_port if agent_port is not None else FixtureAgentPort()
        app.state.db = Database(database_path or os.environ.get('BACKEND_DB', 'backend/.data/travel.sqlite3'))
        try:
            yield
        finally:
            await app.state.agent.aclose()
            app.state.db.close()
    app = FastAPI(title="Travel Agent", lifespan=lifespan)
    from backend.routes.auth import router
    app.include_router(router)
    from backend.routes.rooms import router as rooms_router
    app.include_router(rooms_router)
    return app


app = create_app()

