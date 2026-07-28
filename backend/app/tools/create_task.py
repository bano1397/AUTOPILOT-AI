"""Create a task in the workspace's task list."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, Field

from app.domain.interfaces.tool import ToolMeta
from app.features.tasks.models import TaskPriority
from app.features.tasks.schemas import TaskCreateRequest
from app.features.tasks.service import TaskService
from app.platform.registry import register_tool
from app.tools.context import ToolContext


class CreateTaskIn(BaseModel):
    """Input for :class:`CreateTaskTool`."""

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    priority: TaskPriority = TaskPriority.MEDIUM


class CreateTaskOut(BaseModel):
    """Output of :class:`CreateTaskTool`."""

    task_id: str
    title: str
    priority: TaskPriority


_META = ToolMeta(
    name="create_task",
    description="Create a task with a title, description, and priority.",
    category="productivity",
    inputs=CreateTaskIn,
    outputs=CreateTaskOut,
    permissions=("tasks:write",),
    dependencies=("DatabaseProvider",),
    version="1.0.0",
    tags=("tasks", "planning"),
)


@register_tool(name=_META.name)
class CreateTaskTool:
    """Persist a single task, owned by the workspace identity."""

    meta: ClassVar[ToolMeta] = _META

    def __init__(self, context: ToolContext) -> None:
        self._context = context

    async def run(self, args: BaseModel) -> CreateTaskOut:
        payload = CreateTaskIn.model_validate(args.model_dump())
        async with self._context.db.session() as session:
            task = await TaskService(session).create(
                self._context.user_id,
                TaskCreateRequest(
                    title=payload.title,
                    description=payload.description,
                    priority=payload.priority,
                ),
            )
            return CreateTaskOut(
                task_id=str(task.id), title=task.title, priority=task.priority
            )
