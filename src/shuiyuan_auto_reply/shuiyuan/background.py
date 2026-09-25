import asyncio
import logging
from typing import Coroutine, Set


class BackgroundTaskMixin:
    """
    Run coroutines as fire-and-forget tasks so a watcher loop does not block
    waiting for them to finish.
    """

    def __init__(self) -> None:
        super().__init__()
        self._bg_tasks: Set[asyncio.Task] = set()

    def _spawn_background_task(self, coro: Coroutine[object, object, None]) -> None:
        task = asyncio.create_task(coro)
        # keep a reference so tasks aren't garbage-collected
        self._bg_tasks.add(task)
        # remove task from the set (and log any error) when done
        task.add_done_callback(self._on_bg_task_done)

    def _on_bg_task_done(self, task: asyncio.Task) -> None:
        self._bg_tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            logging.error("Background routine failed", exc_info=task.exception())
