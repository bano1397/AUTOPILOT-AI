"""Prompt management: versioned templates, a registry, and the catalog.

Importing this package registers every catalogued prompt.
"""

from app.platform.prompts.catalog import (
    GENERAL_SYSTEM_PROMPT_V2,
    PLANNER_SYSTEM_PROMPT,
    RESEARCH_SYSTEM_PROMPT,
    ROUTING_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
)
from app.platform.prompts.registry import PromptRegistry, prompt_registry, register_prompt
from app.platform.prompts.template import PromptError, PromptTemplate

__all__ = [
    "GENERAL_SYSTEM_PROMPT_V2",
    "PLANNER_SYSTEM_PROMPT",
    "PromptError",
    "PromptRegistry",
    "PromptTemplate",
    "RESEARCH_SYSTEM_PROMPT",
    "ROUTING_SYSTEM_PROMPT",
    "SYSTEM_PROMPT",
    "prompt_registry",
    "register_prompt",
]
