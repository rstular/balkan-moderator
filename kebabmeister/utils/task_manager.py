import asyncio

from loguru import logger

from kebabmeister.tasks import BaseTask


class TaskManager:
    def __init__(self):
        self.tasks: list[BaseTask] = []

    def schedule(self, task: BaseTask):
        logger.debug(f"Scheduling task {task.name}")
        self.tasks.append(task)

    async def run(self):
        logger.info("Running tasks")
        await asyncio.gather(*[task.run() for task in self.tasks])
