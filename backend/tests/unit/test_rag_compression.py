"""Unit tests for context compression to a token budget."""

from __future__ import annotations

from app.platform.rag.compression import compress, estimate_tokens
from app.platform.rag.types import RetrievalSource, RetrievedChunk


def _chunk(text: str, index: int = 0) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=f"chunk-{index}",
        document_id="doc-1",
        filename="policy.txt",
        chunk_index=index,
        text=text,
        source=RetrievalSource.VECTOR,
    )


class TestEstimateTokens:
    def test_scales_with_length(self) -> None:
        assert estimate_tokens("word " * 100) > estimate_tokens("word " * 10)

    def test_empty_text_costs_nothing(self) -> None:
        assert estimate_tokens("") == 0

    def test_any_text_costs_at_least_one_token(self) -> None:
        assert estimate_tokens("a") >= 1


class TestBudget:
    def test_everything_fits_under_a_generous_budget(self) -> None:
        chunks = [_chunk(f"unique content {index} " * 5, index) for index in range(3)]

        result = compress(chunks, budget_tokens=10_000)

        assert len(result.chunks) == 3
        assert result.dropped == 0
        assert not result.truncated

    def test_rank_order_is_preserved(self) -> None:
        chunks = [_chunk(f"alpha{index} beta gamma", index) for index in range(3)]

        result = compress(chunks, budget_tokens=10_000)

        assert [chunk.chunk_index for chunk in result.chunks] == [0, 1, 2]

    def test_over_budget_chunks_are_dropped_lowest_rank_first(self) -> None:
        chunks = [_chunk(f"topic{index} " + "filler " * 100, index) for index in range(5)]
        one_chunk = estimate_tokens(chunks[0].text)

        result = compress(chunks, budget_tokens=one_chunk * 2)

        assert len(result.chunks) <= 3
        assert result.chunks[0].chunk_index == 0, "the best-ranked chunk survives"
        assert result.dropped_over_budget > 0

    def test_used_tokens_never_exceed_the_budget(self) -> None:
        chunks = [_chunk(f"topic{index} " + "filler " * 80, index) for index in range(6)]

        result = compress(chunks, budget_tokens=200)

        assert result.used_tokens <= 200

    def test_a_partial_tail_is_kept_when_the_remainder_is_worth_it(self) -> None:
        first = _chunk("alpha " * 100, 0)
        second = _chunk("beta " * 400, 1)
        budget = estimate_tokens(first.text) + 120

        result = compress([first, second], budget_tokens=budget)

        assert len(result.chunks) == 2
        assert result.truncated
        assert result.chunks[1].text.endswith("…")
        assert len(result.chunks[1].text) < len(second.text)

    def test_a_non_positive_budget_yields_nothing(self) -> None:
        """A misconfigured budget must not raise mid-answer."""
        result = compress([_chunk("text")], budget_tokens=0)

        assert result.chunks == []
        assert result.dropped_over_budget == 1

    def test_no_chunks_in_no_chunks_out(self) -> None:
        result = compress([], budget_tokens=1000)

        assert result.chunks == []
        assert result.dropped == 0


class TestDeduplication:
    def test_identical_chunks_are_collapsed(self) -> None:
        text = "employees receive twenty vacation days per year"

        result = compress([_chunk(text, 0), _chunk(text, 1)], budget_tokens=10_000)

        assert len(result.chunks) == 1
        assert result.dropped_duplicates == 1

    def test_an_overlapping_window_is_collapsed(self) -> None:
        """Chunking overlaps adjacent windows; both often get retrieved."""
        shared = "employees receive twenty vacation days per year and they expire"
        first = _chunk(shared + " at year end", 0)
        second = _chunk(shared, 1)

        result = compress([first, second], budget_tokens=10_000)

        assert len(result.chunks) == 1
        assert result.dropped_duplicates == 1
        assert result.chunks[0].chunk_index == 0, "the better-ranked one survives"

    def test_genuinely_different_chunks_are_both_kept(self) -> None:
        first = _chunk("vacation days accrue monthly for full-time staff", 0)
        second = _chunk("parking permits are issued quarterly by facilities", 1)

        result = compress([first, second], budget_tokens=10_000)

        assert len(result.chunks) == 2
        assert result.dropped_duplicates == 0

    def test_deduplication_frees_budget_for_later_chunks(self) -> None:
        """The reason dedup runs before the fill, not after."""
        duplicate = _chunk("alpha beta gamma delta " * 20, 0)
        same = _chunk("alpha beta gamma delta " * 20, 1)
        distinct = _chunk("epsilon zeta eta theta " * 20, 2)
        budget = estimate_tokens(duplicate.text) * 2

        result = compress([duplicate, same, distinct], budget_tokens=budget)

        kept = [chunk.chunk_index for chunk in result.chunks]
        assert kept == [0, 2]
