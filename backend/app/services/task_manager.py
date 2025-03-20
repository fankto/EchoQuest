import asyncio
import uuid
from typing import Dict, Any, Callable, Awaitable, Optional, List
import time
from datetime import datetime

from loguru import logger

from app.core.config import settings


class TaskStatus:
    """Task status constants"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskManager:
    """
    Manager for background tasks with tracking and retrieval

    This is a simple in-memory task manager. In production, this should be
    replaced with a proper task queue like Celery.
    """

    def __init__(self):
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.max_tasks = 1000  # Limit to prevent memory issues

    async def add_task(
            self,
            func: Callable[..., Awaitable[Any]],
            *args,
            **kwargs
    ) -> str:
        """
        Add a task to the task manager

        Args:
            func: Async function to call
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Task ID
        """
        # Clean up old tasks first
        self._cleanup_old_tasks()

        # Generate task ID
        task_id = str(uuid.uuid4())

        # Create task record
        self.tasks[task_id] = {
            "id": task_id,
            "status": TaskStatus.PENDING,
            "created_at": datetime.utcnow(),
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None
        }

        # Run task in background
        asyncio.create_task(self._run_task(task_id, func, *args, **kwargs))

        return task_id

    async def _run_task(
            self,
            task_id: str,
            func: Callable[..., Awaitable[Any]],
            *args,
            **kwargs
    ) -> None:
        """
        Run a task and update its status

        Args:
            task_id: Task ID
            func: Async function to call
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
        """
        # Update task status to running
        self.tasks[task_id]["status"] = TaskStatus.RUNNING
        self.tasks[task_id]["started_at"] = datetime.utcnow()

        try:
            # Run the task
            result = await func(*args, **kwargs)

            # Update task status to completed
            self.tasks[task_id]["status"] = TaskStatus.COMPLETED
            self.tasks[task_id]["completed_at"] = datetime.utcnow()
            self.tasks[task_id]["result"] = result
        except Exception as e:
            # Update task status to failed
            self.tasks[task_id]["status"] = TaskStatus.FAILED
            self.tasks[task_id]["completed_at"] = datetime.utcnow()
            self.tasks[task_id]["error"] = str(e)
            logger.error(f"Task {task_id} failed: {e}")

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get task status

        Args:
            task_id: Task ID

        Returns:
            Task status dict if found, None otherwise
        """
        return self.tasks.get(task_id)

    def _cleanup_old_tasks(self) -> None:
        """
        Remove old completed tasks to prevent memory leaks
        """
        if len(self.tasks) <= self.max_tasks:
            return

        # Sort tasks by creation time
        sorted_tasks = sorted(
            self.tasks.items(),
            key=lambda x: x[1]["created_at"]
        )

        # Remove oldest tasks until we're under the limit
        tasks_to_remove = sorted_tasks[:len(sorted_tasks) - self.max_tasks // 2]
        for task_id, _ in tasks_to_remove:
            if self.tasks[task_id]["status"] in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                del self.tasks[task_id]

    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """
        Get all tasks

        Returns:
            List of task status dictionaries
        """
        return list(self.tasks.values())


# Create singleton instance
task_manager = TaskManager()