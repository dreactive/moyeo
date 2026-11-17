from contextlib import asynccontextmanager
from fastapi import FastAPI
from backend.ports import AgentPort


def create_app(agent_port: AgentPort | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        app.state.agent = agent_port
        yield
        if agent_port is not None:
            await agent_port.aclose()
    return FastAPI(title="Travel Agent", lifespan=lifespan)


app = create_app()
