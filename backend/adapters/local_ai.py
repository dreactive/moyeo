from copy import deepcopy


class LocalAIBridge:
    def __init__(self, config):
        self.config = deepcopy(config)
        self.runtime = None

    async def start(self):
        if self.runtime is None:
            from ai.runtime import create_runtime
            self.runtime = create_runtime(self.config)

    async def run(self, task, emit_trace):
        return await self.runtime.run(task, emit_trace)

    async def execute_tool(self, name, arguments, context):
        return await self.runtime.execute_tool(name, arguments, context)

    async def aclose(self):
        if self.runtime is not None:
            runtime, self.runtime = self.runtime, None
            await runtime.aclose()
