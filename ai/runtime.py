"""JSON-only public boundary; models and providers are selected explicitly."""
import asyncio
from ai.context import build_context
from ai.judged_runner import run_judged_agent
from ai.auxiliary import create_auxiliary, extract_auxiliary
from ai.models.fake import FakeModelBackend
from ai.models.worker import ModelWorker
from ai.selection import apply_selection
from ai.tools.registry import RegisteredTools


class AgentRuntime:
    def __init__(self, config):
        self.config = dict(config)
        if config.get("provider_mode", "fixture") not in ("fixture", "live"):
            raise ValueError("Unknown provider mode")
        backend = config.get("model_backend", "fake")
        if backend == "local_qwen":
            from ai.models.local_qwen import LocalQwenBackend
            model = LocalQwenBackend(config.get("base_model_path"), config.get("adapter_path"))
        elif backend == "fake":
            model = FakeModelBackend()
        else:
            raise ValueError("Unknown model backend")
        self.model = ModelWorker(model)
        auxiliary_config = dict(config)
        auxiliary_config.setdefault('auxiliary_backend', 'fixture' if backend == 'fake' else 'external')
        self.auxiliary = create_auxiliary(auxiliary_config)

    async def run(self, task, emit_trace, is_current=None):
        task = build_context(task, [])
        task["_provider_mode"] = self.config.get("provider_mode", "fixture")
        tools = RegisteredTools(task, self.config.get("provider_mode", "fixture"), self.config)
        return await run_judged_agent(task, self.model, tools, emit_trace, self.auxiliary,
                                      is_current, self.config.get('max_decision_rounds', 6))

    async def extract(self, task, previous=None):
        scope, selection_questions = apply_selection(build_context(task, []))
        if selection_questions:
            scope['_selection_only'] = True
        return await extract_auxiliary(scope, self.auxiliary, previous=previous)

    async def run_prepared(self, task, prepared, emit_trace, is_current=None):
        task = build_context(task, [])
        mode = self.config.get("provider_mode", "fixture")
        task["_provider_mode"] = mode
        tools = RegisteredTools(task, mode, self.config)
        return await run_judged_agent(task, self.model, tools, emit_trace, None, is_current,
                                      self.config.get('max_decision_rounds', 6), prepared=prepared)


    async def execute_tool(self, name, arguments, context):
        return await RegisteredTools(context, self.config.get("provider_mode", "fixture"),
                                     self.config).execute(name, arguments)

    async def aclose(self):
        await asyncio.to_thread(self.model.close)


def create_runtime(config):
    return AgentRuntime(config)
