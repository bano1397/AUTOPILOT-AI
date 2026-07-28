"""Semantic search over the workspace's indexed document chunks."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, Field

from app.domain.interfaces.tool import ToolMeta
from app.features.rag.service import RagService
from app.platform.registry import register_tool
from app.tools.context import ToolContext


class VectorSearchIn(BaseModel):
    """Input for :class:`VectorSearchTool`."""

    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)


class VectorSearchMatch(BaseModel):
    document_id: str
    filename: str
    chunk_index: int
    text: str
    distance: float


class VectorSearchOut(BaseModel):
    """Output of :class:`VectorSearchTool`."""

    matches: list[VectorSearchMatch]


_META = ToolMeta(
    name="vector_search",
    description="Semantic search over indexed documents; returns cited chunks.",
    category="retrieval",
    inputs=VectorSearchIn,
    outputs=VectorSearchOut,
    permissions=("documents:read",),
    dependencies=("EmbeddingProvider", "VectorStoreProvider"),
    version="1.0.0",
    tags=("rag", "documents"),
)


@register_tool(name=_META.name)
class VectorSearchTool:
    """Retrieval tool: embeds a query and returns the closest indexed chunks."""

    meta: ClassVar[ToolMeta] = _META

    def __init__(self, context: ToolContext) -> None:
        self._context = context

    async def run(self, args: BaseModel) -> VectorSearchOut:
        payload = VectorSearchIn.model_validate(args.model_dump())
        service = RagService(self._context.embeddings, self._context.vector_store)
        matches = await service.query(
            self._context.user_id, payload.query, top_k=payload.top_k
        )
        return VectorSearchOut(
            matches=[
                VectorSearchMatch(
                    document_id=str(match.metadata.get("document_id", "")),
                    filename=str(match.metadata.get("filename", "")),
                    chunk_index=int(match.metadata.get("chunk_index", 0)),
                    text=match.text,
                    distance=match.distance,
                )
                for match in matches
            ]
        )
