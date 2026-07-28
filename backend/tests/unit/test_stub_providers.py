"""Unit tests for the zero-dependency stub providers.

These back the demo stack and the e2e suite, so their contract is
*determinism and structural validity* — not answer quality.
"""

from __future__ import annotations

import json

import pytest
from app.agents.planner.parsing import parse_plan
from app.domain.interfaces.llm import ChatMessage, ChatRole
from app.infrastructure.embeddings.stub import StubEmbeddingProvider
from app.infrastructure.llm.stub import StubLLMProvider
from app.infrastructure.vectorstore.memory import InMemoryVectorStore
from app.platform.prompts.registry import prompt_registry


def _messages(system: str, user: str) -> list[ChatMessage]:
    return [
        ChatMessage(role=ChatRole.SYSTEM, content=system),
        ChatMessage(role=ChatRole.USER, content=user),
    ]


class TestStubLLM:
    async def test_is_deterministic(self) -> None:
        llm = StubLLMProvider()
        messages = _messages("You are helpful.", "hello there")

        first = await llm.chat(messages)
        second = await llm.chat(messages)

        assert first.content == second.content

    @pytest.mark.parametrize(
        ("request_text", "expected"),
        [
            ("hey there!", "general"),
            ("plan a product launch", "plan"),
            ("research our competitors", "research"),
            ("what does our vacation policy say?", "knowledge"),
        ],
    )
    async def test_routing_returns_a_valid_route(
        self, request_text: str, expected: str
    ) -> None:
        """The supervisor parses this reply, so it must be a bare route word."""
        llm = StubLLMProvider()
        routing_prompt = prompt_registry.render("agent.supervisor.routing")

        result = await llm.chat(_messages(routing_prompt, request_text))

        assert result.content == expected

    async def test_planner_reply_parses_into_tasks(self) -> None:
        """The planner's real parser must accept the stub's output."""
        llm = StubLLMProvider()
        planner_prompt = prompt_registry.render("agent.planner.system")

        result = await llm.chat(_messages(planner_prompt, "launch the beta"))
        items = parse_plan(result.content)

        assert len(items) >= 3
        assert all(item.title for item in items)

    async def test_email_classification_is_valid_json(self) -> None:
        llm = StubLLMProvider()
        classify_prompt = prompt_registry.render("agent.email.classify")

        result = await llm.chat(_messages(classify_prompt, "when does my plan renew?"))
        payload = json.loads(result.content)

        assert payload["intent"] == "question"

    async def test_grounded_answers_carry_a_citation(self) -> None:
        """The knowledge agent is only asked to answer when context exists."""
        llm = StubLLMProvider()
        ask_prompt = prompt_registry.render("rag.ask.system")

        result = await llm.chat(_messages(ask_prompt, "how many days?"))

        assert "[1]" in result.content

    async def test_reports_usage_so_the_audit_trail_is_populated(self) -> None:
        llm = StubLLMProvider()

        result = await llm.chat(_messages("sys", "a longer user request here"))

        assert result.model == "stub"
        assert result.prompt_tokens > 0
        assert result.completion_tokens > 0


class TestStubEmbeddings:
    async def test_is_deterministic_and_correctly_shaped(self) -> None:
        provider = StubEmbeddingProvider(dimensions=64)

        first = await provider.embed(["vacation policy"])
        second = await provider.embed(["vacation policy"])

        assert first == second
        assert len(first[0]) == 64

    async def test_returns_one_vector_per_input_in_order(self) -> None:
        provider = StubEmbeddingProvider(dimensions=32)

        vectors = await provider.embed(["alpha", "beta", "alpha"])

        assert len(vectors) == 3
        assert vectors[0] == vectors[2]
        assert vectors[0] != vectors[1]

    async def test_empty_text_still_yields_a_usable_unit_vector(self) -> None:
        """A zero vector would make every cosine score 0 and break retrieval."""
        provider = StubEmbeddingProvider(dimensions=16)

        (vector,) = await provider.embed(["!!! ???"])

        assert any(value != 0.0 for value in vector)

    async def test_shared_words_score_closer_than_unrelated_text(self) -> None:
        """Enough signal for e2e to assert retrieval found the right document."""
        provider = StubEmbeddingProvider(dimensions=256)
        query, related, unrelated = await provider.embed(
            [
                "vacation policy days",
                "the vacation policy grants twenty days",
                "quarterly revenue in the northern region",
            ]
        )

        def dot(a: list[float], b: list[float]) -> float:
            return sum(x * y for x, y in zip(a, b, strict=True))

        assert dot(query, related) > dot(query, unrelated)


class TestInMemoryVectorStore:
    async def test_returns_nearest_first(self) -> None:
        store = InMemoryVectorStore()
        await store.upsert(
            ids=["far", "near"],
            embeddings=[[0.0, 1.0], [1.0, 0.0]],
            documents=["far doc", "near doc"],
            metadatas=[{}, {}],
        )

        matches = await store.query([1.0, 0.0], top_k=2)

        assert [match.id for match in matches] == ["near", "far"]
        assert matches[0].distance < matches[1].distance

    async def test_metadata_filter_scopes_results(self) -> None:
        store = InMemoryVectorStore()
        await store.upsert(
            ids=["mine", "theirs"],
            embeddings=[[1.0, 0.0], [1.0, 0.0]],
            documents=["a", "b"],
            metadatas=[{"user_id": "u1"}, {"user_id": "u2"}],
        )

        matches = await store.query([1.0, 0.0], top_k=10, where={"user_id": "u1"})

        assert [match.id for match in matches] == ["mine"]

    async def test_top_k_truncates(self) -> None:
        store = InMemoryVectorStore()
        await store.upsert(
            ids=[f"v{index}" for index in range(5)],
            embeddings=[[1.0, 0.0]] * 5,
            documents=["x"] * 5,
            metadatas=[{}] * 5,
        )

        assert len(await store.query([1.0, 0.0], top_k=3)) == 3

    async def test_upsert_replaces_and_delete_removes(self) -> None:
        store = InMemoryVectorStore()
        await store.upsert(
            ids=["a"], embeddings=[[1.0, 0.0]], documents=["first"], metadatas=[{}]
        )
        await store.upsert(
            ids=["a"], embeddings=[[1.0, 0.0]], documents=["second"], metadatas=[{}]
        )

        (match,) = await store.query([1.0, 0.0], top_k=5)
        assert match.text == "second"

        await store.delete(["a"])
        assert await store.query([1.0, 0.0], top_k=5) == []

    async def test_zero_vector_scores_without_dividing_by_zero(self) -> None:
        store = InMemoryVectorStore()
        await store.upsert(
            ids=["z"], embeddings=[[0.0, 0.0]], documents=["z"], metadatas=[{}]
        )

        (match,) = await store.query([1.0, 0.0], top_k=1)

        assert match.distance == 1.0
