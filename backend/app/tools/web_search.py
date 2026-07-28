"""Live web search via the configured SearchProvider (DuckDuckGo by default)."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, Field

from app.domain.interfaces.tool import ToolMeta
from app.platform.registry import register_tool
from app.tools.context import ToolContext


class WebSearchIn(BaseModel):
    """Input for :class:`WebSearchTool`."""

    query: str = Field(min_length=1, max_length=500)
    max_results: int = Field(default=5, ge=1, le=10)


class WebSearchHit(BaseModel):
    title: str
    url: str
    snippet: str


class WebSearchOut(BaseModel):
    """Output of :class:`WebSearchTool`."""

    results: list[WebSearchHit]


_META = ToolMeta(
    name="web_search",
    description="Search the public web; returns titles, URLs, and snippets.",
    category="research",
    inputs=WebSearchIn,
    outputs=WebSearchOut,
    # Web results are untrusted input: never treat them as instructions.
    permissions=("web:read",),
    dependencies=("SearchProvider",),
    version="1.0.0",
    tags=("web", "research"),
)


@register_tool(name=_META.name)
class WebSearchTool:
    """Search the public web and return titled, linked snippets."""

    meta: ClassVar[ToolMeta] = _META

    def __init__(self, context: ToolContext) -> None:
        self._context = context

    async def run(self, args: BaseModel) -> WebSearchOut:
        payload = WebSearchIn.model_validate(args.model_dump())
        results = await self._context.search.search(
            payload.query, max_results=payload.max_results
        )
        return WebSearchOut(
            results=[
                WebSearchHit(title=r.title, url=r.url, snippet=r.snippet)
                for r in results
            ]
        )
