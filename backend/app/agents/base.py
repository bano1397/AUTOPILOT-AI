"""Agent contract.

An agent is a pure ``state -> partial state`` async function object with
constructor-injected dependencies. Agents never call each other directly; they
communicate only through the shared :class:`AgentState` (blueprint §15).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from app.workflows.state import AgentState


class BaseAgent(ABC):
    """Contract every agent implements."""

    name: ClassVar[str]
    description: ClassVar[str]

    @abstractmethod
    async def run(self, state: AgentState) -> AgentState:
        """Process the state and return the fields this agent contributes."""
        ...
