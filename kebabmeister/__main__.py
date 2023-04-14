import argparse
import asyncio
import atexit

import asyncpraw
from loguru import logger

from kebabmeister import constants, state
from kebabmeister.configuration import Configuration
from kebabmeister.database import initialize_db
from kebabmeister.tasks.submission_monitoring import SubmissionMonitoringTask
from kebabmeister.utils.task_manager import TaskManager


async def main(config: Configuration) -> int:
    """
    Main function of the program.

    @param config: Configuration object
    @return: Exit code
    """
    state.db_engine, state.db_session = await initialize_db(config.database)

    state.reddit = asyncpraw.Reddit(
        client_id=config.reddit.client_id,
        client_secret=config.reddit.client_secret,
        user_agent=config.reddit.user_agent,
        username=config.reddit.username,
        password=config.reddit.password,
    )

    state.me = await state.reddit.user.me()
    logger.info(f"Logged in as {state.me.name} ({state.me.id})")

    task_mgr = TaskManager()
    task_mgr.schedule(SubmissionMonitoringTask(config=config))
    await task_mgr.run()

    return 0


@atexit.register
def exit_handler():
    """
    Exit handler. Handles sync cleanup.

    @return: None
    """
    logger.info("Exiting")
    state.loop.run_until_complete(exit_task())


async def exit_task():
    """
    Exit task. Handles async cleanup.

    @return: None
    """
    await state.reddit.close()
    await state.db_engine.dispose()
    logger.debug("Database engine disposed")


@logger.catch
def init():
    """
    Initializes the program.

    @return: None
    """
    parser = argparse.ArgumentParser(description="Balkan moderation bot")
    parser.add_argument(
        "-c",
        "--config",
        help=f"Path to the config file (default: {constants.DEFAULT_CONFIG_FILE})",
        required=False,
        type=argparse.FileType("r"),
    )
    args = parser.parse_args()

    try:
        if args.config:
            config = Configuration.schema().loads(args.config.read())
        else:
            with open(constants.DEFAULT_CONFIG_FILE, "r") as f:
                config = Configuration.schema().loads(f.read())
    except FileNotFoundError:
        logger.error("Config file not found")
        exit(1)
    except KeyError as e:
        logger.error(f"Missing key in config: {e}")
        exit(1)

    state.loop = asyncio.get_event_loop()
    exit(state.loop.run_until_complete(main(config=config)))


init()
