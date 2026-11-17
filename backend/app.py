import os
import asyncio
from contextlib import suppress
from contextlib import asynccontextmanager
from fastapi import FastAPI
from backend.ports import AgentPort
from backend.adapters.fixture_agent import FixtureAgentPort
from backend.db import Database
from backend.services.agent_jobs import AgentJobs


def create_app(agent_port: AgentPort | None = None, *, database_path=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        app.state.agent = agent_port if agent_port is not None else FixtureAgentPort()
        app.state.db = Database(database_path or os.environ.get('BACKEND_DB', 'backend/.data/travel.sqlite3'))
        app.state.dev_token = os.environ.get('DEV_TOKEN', '')
        app.state.jobs = AgentJobs(app.state.db, app.state.agent)
        worker = asyncio.create_task(app.state.jobs.work())
        try:
            yield
        finally:
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker
            await app.state.agent.aclose()
            app.state.db.close()
    app = FastAPI(title="Travel Agent", lifespan=lifespan)
    from backend.routes.auth import router
    app.include_router(router)
    from backend.routes.rooms import router as rooms_router
    app.include_router(rooms_router)
    from backend.routes.messages import router as messages_router
    app.include_router(messages_router)
    from backend.routes.plans import router as plans_router
    app.include_router(plans_router)
    from backend.routes.dev import router as dev_router
    app.include_router(dev_router)
    return app


app = create_app()




