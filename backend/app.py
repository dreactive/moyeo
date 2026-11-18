from backend.adapters.fixture_agent import FixtureAgentPort
from backend.adapters.local_ai import LocalAIBridge
from backend.config import read_settings
from backend.db import Database
from backend.ports import AgentPort
from backend.services.agent_jobs import AgentJobs
from contextlib import asynccontextmanager
from contextlib import suppress
from fastapi import FastAPI
import asyncio
import os


def create_app(agent_port: AgentPort | None = None, *, database_path=None, settings=None, frontend_path=None) -> FastAPI:
    settings = settings if settings is not None else read_settings()
    @asynccontextmanager
    async def lifespan(app):
        app.state.agent = agent_port if agent_port is not None else FixtureAgentPort()
        if agent_port is None and settings['agent_mode'] == 'local_ai':
            app.state.agent = LocalAIBridge(settings['runtime_config'])
        if isinstance(app.state.agent, LocalAIBridge):
            await app.state.agent.start()
        app.state.dev_agent = app.state.agent if isinstance(app.state.agent, LocalAIBridge) else LocalAIBridge(settings['runtime_config'])
        app.state.dev_agent_lock = asyncio.Lock()
        app.state.db = Database(database_path or settings['database_path'])
        app.state.db.trace_enabled = settings['trace_enabled']
        app.state.dev_token = settings['dev_token']
        app.state.dev_runtime_config = settings['runtime_config']
        app.state.jobs = AgentJobs(app.state.db, app.state.agent)
        worker = asyncio.create_task(app.state.jobs.work())
        try:
            yield
        finally:
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker
            await app.state.agent.aclose()
            if app.state.dev_agent is not app.state.agent:
                await app.state.dev_agent.aclose()
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
    from backend.routes.dev_sandbox import router as dev_sandbox_router
    app.include_router(dev_sandbox_router)
    from backend.routes.places import router as places_router
    app.include_router(places_router)
    from pathlib import Path
    from backend.routes.static import mount_frontend
    mount_frontend(app, frontend_path or Path(__file__).resolve().parents[1] / 'frontend', settings['public_map_key'])
    return app


app = create_app()
