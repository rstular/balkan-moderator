from kebabmeister.configuration import Configuration


class BaseTask:
    def __init__(self, config: Configuration, name: str):
        """
        Base class for tasks.

        @param config: Configuration object
        @param name: Name of the task
        """
        self.config = config
        self.name = name

    async def run(self):
        """
        Runs the task.
        """
        raise NotImplementedError("run() not implemented")
