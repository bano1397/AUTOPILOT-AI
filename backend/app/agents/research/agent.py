"""Research agent implementation."""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from app.agents.base import BaseAgent
from app.agents.research.prompts import build_research_messages
from app.core.exceptions import UpstreamServiceError
from app.core.logging import get_logger
from app.domain.interfaces.llm import LLMProvider
from app.domain.interfaces.search import SearchProvider, SearchResult
from app.platform.observability.recorder import AiExecutionRecorder
from app.platform.registry import register_agent
from app.workflows.state import AgentState

logger = get_logger("app.agents.research")

_MAX_RESULTS = 5
_FETCH_PAGES = 3
_PAGE_CHARS_IN_PROMPT = 4000

NO_RESULTS_ANSWER = (
    "I couldn't find any web results for that question. Try rephrasing it or "
    "narrowing the topic."
)


@register_agent
class ResearchAgent(BaseAgent):
    """Searches the web, reads the top results, and synthesizes an answer."""

    name: ClassVar[str] = "research"
    description: ClassVar[str] = (
        "Researches questions on the live web and answers with cited sources."
    )

    def __init__(
        self,
        search: SearchProvider,
        llm: LLMProvider,
        recorder: AiExecutionRecorder,
    ) -> None:
        self._search = search
        self._llm = llm
        self._recorder = recorder

    async def run(self, state: AgentState) -> AgentState:
        request = state.get("request", "")
        user_id = state.get("user_id")

        try:
            results = await self._search.search(request, max_results=_MAX_RESULTS)
        except Exception as exc:
            logger.warning("research.search_failed", extra={"error": str(exc)})
            raise UpstreamServiceError("Web search is unavailable") from exc

        if not results:
            return {
                "agent": self.name,
                "answer": NO_RESULTS_ANSWER,
                "model": None,
                "grounded": False,
                "sources": [],
                "web_sources": [],
            }

        contents = await self._gather_contents(results)
        result = await self._recorder.chat(
            self._llm,
            build_research_messages(request, contents, state.get("history", [])),
            feature="agent.research",
            agent_name=self.name,
            user_id=UUID(user_id) if user_id else None,
            temperature=0.3,
        )
        return {
            "agent": self.name,
            "answer": result.content,
            "model": result.model,
            "grounded": False,  # web-grounded, not document-grounded
            "sources": [],
            "web_sources": [
                {"title": item.title, "url": item.url, "snippet": item.snippet}
                for item in results
            ],
        }

    async def _gather_contents(
        self, results: list[SearchResult]
    ) -> list[dict[str, str]]:
        """Fetch the top pages; a failed fetch degrades to the search snippet."""
        contents: list[dict[str, str]] = []
        for result in results[:_FETCH_PAGES]:
            try:
                text = await self._search.fetch(result.url)
            except Exception as exc:
                logger.info(
                    "research.fetch_skipped",
                    extra={"url": result.url[:120], "error": str(exc)},
                )
                text = result.snippet
            contents.append(
                {
                    "title": result.title,
                    "url": result.url,
                    "content": (text or result.snippet)[:_PAGE_CHARS_IN_PROMPT],
                }
            )
        return contents
