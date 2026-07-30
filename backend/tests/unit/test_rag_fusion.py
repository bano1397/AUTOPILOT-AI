"""Unit tests for Reciprocal Rank Fusion."""

from __future__ import annotations

import pytest
from app.platform.rag.fusion import reciprocal_rank_fusion


def _order(fused: list[tuple[str, float]]) -> list[str]:
    return [identifier for identifier, _ in fused]


class TestReciprocalRankFusion:
    def test_agreement_between_rankings_wins(self) -> None:
        """The whole point: two independent methods agreeing is the signal."""
        vector = ["a", "b", "c"]
        keyword = ["d", "b", "e"]

        # b is 2nd in both; a and d are each 1st in one list only.
        assert _order(reciprocal_rank_fusion([vector, keyword]))[0] == "b"

    def test_two_second_places_beat_one_first_place(self) -> None:
        """Holds for every k >= 1: 2/(k+2) > 1/(k+1). Worth pinning — it is
        the property that makes fusion prefer corroborated results."""
        for k in (1, 10, 60, 500):
            fused = _order(reciprocal_rank_fusion([["a", "b"], ["c", "b"]], k=k))
            assert fused[0] == "b", f"failed at k={k}"

    def test_a_single_ranking_passes_through_unchanged(self) -> None:
        assert _order(reciprocal_rank_fusion([["a", "b", "c"]])) == ["a", "b", "c"]

    def test_ids_unique_to_one_ranking_are_kept(self) -> None:
        """Recall is the reason for running two retrievers at all."""
        fused = _order(reciprocal_rank_fusion([["a"], ["b"]]))

        assert set(fused) == {"a", "b"}

    def test_scores_descend(self) -> None:
        fused = reciprocal_rank_fusion([["a", "b", "c"], ["b", "c", "a"]])
        scores = [score for _, score in fused]

        assert scores == sorted(scores, reverse=True)

    def test_ties_break_deterministically_on_id(self) -> None:
        """Two runs must not swap equal-scoring results."""
        first = reciprocal_rank_fusion([["b", "a"], ["a", "b"]])
        second = reciprocal_rank_fusion([["b", "a"], ["a", "b"]])

        assert first == second
        assert _order(first) == ["a", "b"]

    def test_empty_input_yields_nothing(self) -> None:
        assert reciprocal_rank_fusion([]) == []
        assert reciprocal_rank_fusion([[], []]) == []

    def test_larger_k_damps_the_gap_between_adjacent_ranks(self) -> None:
        """That damping is why fusion tolerates disagreement about exact order."""
        ranking = [["a", "b"]]

        sharp = dict(reciprocal_rank_fusion(ranking, k=1))
        damped = dict(reciprocal_rank_fusion(ranking, k=60))

        assert sharp["a"] - sharp["b"] > damped["a"] - damped["b"]

    def test_k_below_one_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="k must be"):
            reciprocal_rank_fusion([["a"]], k=0)
