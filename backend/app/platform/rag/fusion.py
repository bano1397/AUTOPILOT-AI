"""Reciprocal Rank Fusion — combining rankings that don't share a scale (§17).

Vector search returns cosine distances; BM25 returns unbounded relevance
scores. Normalising them onto a common scale means inventing a weighting, and
that weighting would quietly depend on the embedding model, the corpus, and the
query. RRF sidesteps the problem by discarding the scores entirely and fusing
on **rank position** only, which is why it is the standard choice here.

    score(d) = sum over rankings of 1 / (k + rank(d))

``k`` damps the top of each list: with k=60 the difference between rank 1 and
rank 2 is small, so a document both retrievers place highly outranks one that
either places first alone. That is the desired behaviour — agreement between
two independent methods is the signal.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

# The value from Cormack et al. (2009), where RRF was introduced; it has held
# up as a default across corpora and is not tuned to this one.
DEFAULT_K = 60


def reciprocal_rank_fusion(
    rankings: Iterable[Sequence[str]], *, k: int = DEFAULT_K
) -> list[tuple[str, float]]:
    """Fuse ranked id lists into one ranking, best first.

    Each input is an ordered sequence of ids, most relevant first. Ids may
    appear in any subset of the rankings. Ties break on the id so the output is
    deterministic — two documents with identical fused scores must not swap
    order between runs.
    """
    if k < 1:
        raise ValueError("k must be >= 1")

    scores: dict[str, float] = {}
    for ranking in rankings:
        for position, identifier in enumerate(ranking):
            scores[identifier] = scores.get(identifier, 0.0) + 1.0 / (k + position + 1)

    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))
