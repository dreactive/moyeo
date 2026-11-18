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

    async def run_current(self, task, emit_trace, is_current):
        return await self.runtime.run(task, emit_trace, is_current=is_current)

    async def extract(self, task, previous=None):
        return await self.runtime.extract(task, previous=previous)

    async def run_prepared(self, task, prepared, emit_trace, is_current=None):
        return await self.runtime.run_prepared(task, prepared, emit_trace, is_current=is_current)


    async def execute_tool(self, name, arguments, context):
        return await self.runtime.execute_tool(name, arguments, context)

    async def aclose(self):
        if self.runtime is not None:
            runtime, self.runtime = self.runtime, None
            await runtime.aclose()
