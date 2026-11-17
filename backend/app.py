from fastapi import FastAPI
from backend.ports import AgentPort


def create_app(agent_port: AgentPort | None = None) -> FastAPI:
    return FastAPI(title="Travel Agent")


app = create_app()
