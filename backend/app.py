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
import signal


def watch_shutdown_signals(stopping):
    """Set `stopping` on Ctrl+C/SIGTERM, then let uvicorn handle the signal as usual.

    Uvicorn waits for open connections before running lifespan shutdown, so live
    event streams must notice the signal themselves or the server never exits.
    """
    loop = asyncio.get_running_loop()
    previous = {}
    for name in ('SIGINT', 'SIGTERM', 'SIGBREAK'):
        sig = getattr(signal, name, None)
        if sig is None:
            continue
        try:
            before = signal.getsignal(sig)
            def handler(signum, frame, before=before):
                loop.call_soon_threadsafe(stopping.set)
                if callable(before):
                    before(signum, frame)
                elif before == signal.SIG_DFL and signum == signal.SIGINT:
                    raise KeyboardInterrupt
            signal.signal(sig, handler)
            previous[sig] = before
        except (ValueError, OSError):
            pass
    def restore():
        for sig, before in previous.items():
            with suppress(ValueError, OSError):
                signal.signal(sig, before)
    return restore


def create_app(agent_port: AgentPort | None = None, *, database_path=None, settings=None, frontend_path=None) -> FastAPI:
    settings = settings if settings is not None else read_settings()
    @asynccontextmanager
    async def lifespan(app):
        app.state.stopping = asyncio.Event()
        restore_signals = watch_shutdown_signals(app.state.stopping)
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
            app.state.stopping.set()
            restore_signals()
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker
            await app.state.agent.aclose()
            if app.state.dev_agent is not app.state.agent:
                await app.state.dev_agent.aclose()
            app.state.db.close()
    app = FastAPI(title="Travel Agent", lifespan=lifespan)
    app.state.cookie_secure = settings.get('cookie_secure', False)
    from backend.public_http import configure_public_http
    configure_public_http(app, settings)
    from backend.routes.health import router as health_router
    app.include_router(health_router)
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
    if settings.get('serve_frontend', True):
        mount_frontend(app, frontend_path or Path(__file__).resolve().parents[1] / 'frontend', settings['public_map_key'])
    return app


app = create_app()
