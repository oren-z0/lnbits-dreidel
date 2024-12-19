import asyncio

from loguru import logger

from .extension import *  # noqa: F401,F403,E402
from .views import *  # noqa: F401,F403,E402
from .views_api import *  # noqa: F401,F403,E402


scheduled_tasks: list[asyncio.Task] = []

def dreidel_stop():
    for task in scheduled_tasks:
        try:
            task.cancel()
        except Exception as ex:
            logger.warning(ex)

def dreidel_start():
    pass
