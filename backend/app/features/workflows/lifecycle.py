"""Workflow definition lifecycle: version, activate, roll back, clone (§20).

The invariants this service exists to hold:

* **Versions are immutable.** There is no update path. Changing a workflow adds
  a version; reverting activates an older one. That is what makes a run's
  pinned ``workflow_version_id`` a trustworthy record of what executed.
* **Exactly one active version per definition**, swapped inside a single
  transaction so no reader ever observes zero or two.
* **A version that cannot compile is never stored.** Specs are validated
  against the agents this deployment actually has, at write time — an invalid
  version that reached the database could be activated and would then break
  every run until someone noticed.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.logging import get_logger
from app.core.pagination import PaginationParams
from app.features.workflows.models import (
    WorkflowDefinition,
    WorkflowRun,
    WorkflowVersion,
)
from app.features.workflows.repository import WorkflowDefinitionRepository
from app.platform.registry import agent_registry
from app.workflows.spec import GraphSpec, default_spec

logger = get_logger("app.features.workflows.lifecycle")

# The definition the supervisor graph runs under. Seeded on first use so an
# existing deployment gains versioning without a data migration.
DEFAULT_WORKFLOW_NAME = "agents.ask"
DEFAULT_WORKFLOW_DESCRIPTION = (
    "Supervisor routing across the specialist agents, with a human approval gate."
)


def available_agents() -> list[str]:
    """Agent names this process can actually route to."""
    return sorted(entry.name for entry in agent_registry.entries())


class WorkflowLifecycleService:
    """Owns definitions, their versions, and which one is live."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = WorkflowDefinitionRepository(session)

    # -- definitions ---------------------------------------------------------

    async def list_definitions(
        self, pagination: PaginationParams
    ) -> tuple[Sequence[WorkflowDefinition], int]:
        items = await self._repo.list_definitions(
            offset=pagination.offset, limit=pagination.limit
        )
        return items, await self._repo.count_definitions()

    async def get_definition(self, definition_id: UUID) -> WorkflowDefinition:
        definition = await self._repo.get(definition_id)
        if definition is None:
            raise NotFoundError("Workflow definition not found")
        return definition

    async def create_definition(
        self,
        name: str,
        description: str,
        spec: GraphSpec,
        *,
        cloned_from_id: UUID | None = None,
    ) -> tuple[WorkflowDefinition, WorkflowVersion]:
        """Create a definition and its active v1."""
        self._validate(spec)
        if await self._repo.get_by_name(name) is not None:
            raise ConflictError(f"A workflow named {name!r} already exists")

        definition = WorkflowDefinition(
            name=name, description=description, cloned_from_id=cloned_from_id
        )
        try:
            await self._repo.add(definition)
            version = await self._repo.add_version(
                WorkflowVersion(
                    definition_id=definition.id,
                    version=1,
                    graph_spec=spec.to_mapping(),
                    is_active=True,
                    notes="Initial version",
                )
            )
            await self._session.commit()
        except IntegrityError as exc:  # pragma: no cover - concurrent create
            await self._session.rollback()
            raise ConflictError(f"A workflow named {name!r} already exists") from exc

        await self._session.refresh(definition)
        await self._session.refresh(version)
        logger.info(
            "workflow.definition_created",
            extra={"definition": name, "definition_id": str(definition.id)},
        )
        return definition, version

    async def clone_definition(
        self, definition_id: UUID, new_name: str, *, description: str | None = None
    ) -> tuple[WorkflowDefinition, WorkflowVersion]:
        """Fork a definition, seeding v1 from the source's *active* spec.

        The active version, not the latest: cloning should reproduce what the
        source workflow currently does, which is rarely a draft nobody
        activated.
        """
        source = await self.get_definition(definition_id)
        active = await self._repo.active_version(source.id)
        if active is None:
            raise ValidationAppError(
                f"Workflow {source.name!r} has no active version to clone"
            )

        return await self.create_definition(
            new_name,
            description if description is not None else source.description,
            GraphSpec.from_mapping(active.graph_spec),
            cloned_from_id=source.id,
        )

    # -- versions ------------------------------------------------------------

    async def list_versions(self, definition_id: UUID) -> Sequence[WorkflowVersion]:
        await self.get_definition(definition_id)
        return await self._repo.list_versions(definition_id)

    async def get_version(self, version_id: UUID) -> WorkflowVersion:
        version = await self._repo.get_version(version_id)
        if version is None:
            raise NotFoundError("Workflow version not found")
        return version

    async def add_version(
        self,
        definition_id: UUID,
        spec: GraphSpec,
        *,
        notes: str = "",
        activate: bool = True,
    ) -> WorkflowVersion:
        """Append a new immutable version, optionally making it live."""
        self._validate(spec)
        await self.get_definition(definition_id)

        number = await self._repo.next_version_number(definition_id)
        if activate:
            await self._repo.deactivate_all(definition_id)

        version = await self._repo.add_version(
            WorkflowVersion(
                definition_id=definition_id,
                version=number,
                graph_spec=spec.to_mapping(),
                is_active=activate,
                notes=notes,
            )
        )
        await self._session.commit()
        await self._session.refresh(version)
        logger.info(
            "workflow.version_added",
            extra={
                "definition_id": str(definition_id),
                "version": number,
                "active": activate,
            },
        )
        return version

    async def activate_version(self, version_id: UUID) -> WorkflowVersion:
        """Make ``version_id`` the live one — this is also rollback.

        Rolling back is not a distinct operation: activating an earlier version
        *is* the rollback, and it leaves the newer versions in place rather
        than deleting them, so the history stays complete and the change is
        itself reversible.
        """
        version = await self.get_version(version_id)
        if version.is_active:
            return version

        await self._repo.deactivate_all(version.definition_id)
        version.is_active = True
        await self._session.commit()
        await self._session.refresh(version)
        logger.info(
            "workflow.version_activated",
            extra={
                "definition_id": str(version.definition_id),
                "version": version.version,
            },
        )
        return version

    async def active_spec(self, name: str) -> tuple[WorkflowVersion, GraphSpec]:
        """Resolve a workflow name to its live version and compiled-from spec.

        Seeds the default definition on first call so an existing deployment
        starts running under a real version without any migration step.
        """
        definition = await self._repo.get_by_name(name)
        if definition is None:
            if name != DEFAULT_WORKFLOW_NAME:
                raise NotFoundError(f"Workflow {name!r} is not defined")
            definition, version = await self.create_definition(
                DEFAULT_WORKFLOW_NAME,
                DEFAULT_WORKFLOW_DESCRIPTION,
                default_spec(available_agents()),
            )
            return version, GraphSpec.from_mapping(version.graph_spec)

        active = await self._repo.active_version(definition.id)
        if active is None:
            raise ValidationAppError(
                f"Workflow {name!r} has no active version; activate one to run it"
            )
        return active, GraphSpec.from_mapping(active.graph_spec)

    # -- history -------------------------------------------------------------

    async def runs_for_version(
        self, version_id: UUID, pagination: PaginationParams
    ) -> tuple[Sequence[WorkflowRun], int]:
        await self.get_version(version_id)
        items = await self._repo.list_runs_for_version(
            version_id, offset=pagination.offset, limit=pagination.limit
        )
        return items, await self._repo.count_runs_for_version(version_id)

    # -- internals -----------------------------------------------------------

    @staticmethod
    def _validate(spec: GraphSpec) -> None:
        try:
            spec.validate_against(available_agents())
        except ValueError as exc:
            raise ValidationAppError(str(exc)) from exc

    @staticmethod
    def parse_spec(payload: dict[str, Any]) -> GraphSpec:
        """Parse an untrusted spec payload into a validated GraphSpec."""
        try:
            return GraphSpec.from_mapping(payload)
        except Exception as exc:  # pydantic ValidationError and friends
            raise ValidationAppError(f"Invalid graph_spec: {exc}") from exc
