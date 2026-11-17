"""JSON-only public boundary; models and providers are selected explicitly."""
import asyncio
from ai.context import build_context
from ai.runner import run_agent
from ai.models.fake import FakeModelBackend
from ai.models.worker import ModelWorker
from ai.tools.registry import RegisteredTools


class AgentRuntime:
    def __init__(self, config):
        self.config = dict(config)
        if config.get("model_backend", "fake") != "fake":
            raise ValueError("Model backend unavailable")
        if config.get("provider_mode", "fixture") not in ("fixture", "live"):
            raise ValueError("Unknown provider mode")
        self.model = ModelWorker(FakeModelBackend())

    async def run(self, task, emit_trace):
        task = build_context(task, [])
        tools = RegisteredTools(task, self.config.get("provider_mode", "fixture"), self.config)
        return await run_agent(task, self.model, tools, emit_trace)

    async def execute_tool(self, name, arguments, context):
        return await RegisteredTools(context, self.config.get("provider_mode", "fixture"),
                                     self.config).execute(name, arguments)

    async def aclose(self):
        await asyncio.to_thread(self.model.close)


def create_runtime(config):
    return AgentRuntime(config)
