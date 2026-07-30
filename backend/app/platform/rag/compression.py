"""Context compression to a token budget (§17).

Retrieval returns the best chunks; it has no idea whether they fit. Without
this stage the prompt grows with ``top_k`` until the provider truncates it —
silently, from whichever end it prefers, usually taking the citations with it.
Compressing here means the caller decides what to drop, in rank order, and can
say what it dropped.

Two things happen, in this order:

1. **Near-duplicate removal.** Chunking overlaps windows by ``CHUNK_OVERLAP``
   characters, so adjacent chunks from one document genuinely share text. When
   both are retrieved — likely, since they are textually similar — the overlap
   is paid for twice out of a fixed budget.
2. **Greedy fill by rank.** Take chunks in order while they fit. The last one
   may be truncated at a word boundary if a worthwhile amount of budget
   remains, because half of a relevant passage usually beats none of it.

Token counting is an **estimate**, not a tokenizer. Exact counts differ per
model and would mean a tokenizer dependency plus a per-provider mapping; the
budget is a safety margin, so a documented approximation with a conservative
divisor is the honest trade. See :func:`estimate_tokens`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.platform.rag.keyword import tokenize
from app.platform.rag.types import RetrievedChunk

# Characters per token. English prose on BPE tokenizers averages ~4; 3.5 is
# deliberately pessimistic so the estimate errs toward under-filling the window
# rather than overflowing it.
_CHARS_PER_TOKEN = 3.5

# Below this many tokens a truncated tail is not worth a citation slot.
_MIN_USEFUL_TAIL_TOKENS = 40

# Token-set overlap above which a chunk is treated as already covered.
_DUPLICATE_THRESHOLD = 0.8


def estimate_tokens(text: str) -> int:
    """Approximate the token count of ``text`` (see module note)."""
    if not text:
        return 0
    return max(1, int(len(text) / _CHARS_PER_TOKEN) + 1)


@dataclass(frozen=True)
class CompressionResult:
    """What survived the budget, and what did not."""

    chunks: list[RetrievedChunk]
    used_tokens: int
    dropped_duplicates: int
    dropped_over_budget: int
    truncated: bool

    @property
    def dropped(self) -> int:
        return self.dropped_duplicates + self.dropped_over_budget


def _similarity(left: frozenset[str], right: frozenset[str]) -> float:
    """Overlap coefficient of two token sets.

    Overlap, not Jaccard: a short chunk fully contained in a longer one scores
    1.0 here but only ~0.5 under Jaccard, and containment is precisely the case
    that chunk overlap produces.
    """
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def _truncate_to_tokens(text: str, budget: int) -> str:
    """Cut ``text`` to roughly ``budget`` tokens, ending on a word boundary."""
    limit = int(budget * _CHARS_PER_TOKEN)
    if limit >= len(text):
        return text
    cut = text[:limit]
    boundary = cut.rfind(" ")
    if boundary > limit // 2:
        cut = cut[:boundary]
    return cut.rstrip() + " …"


def compress(
    chunks: Sequence[RetrievedChunk], *, budget_tokens: int
) -> CompressionResult:
    """Fit ``chunks`` into ``budget_tokens``, best-ranked first.

    Input order is treated as relevance order and is preserved. A non-positive
    budget yields nothing rather than raising: an unusable budget is a
    configuration problem the caller reports, not a crash mid-answer.
    """
    if budget_tokens <= 0 or not chunks:
        return CompressionResult(
            chunks=[],
            used_tokens=0,
            dropped_duplicates=0,
            dropped_over_budget=len(chunks),
            truncated=False,
        )

    kept: list[RetrievedChunk] = []
    seen_tokens: list[frozenset[str]] = []
    used = 0
    duplicates = 0
    over_budget = 0
    truncated = False

    for chunk in chunks:
        tokens = frozenset(tokenize(chunk.text))
        if any(
            _similarity(tokens, previous) >= _DUPLICATE_THRESHOLD
            for previous in seen_tokens
        ):
            duplicates += 1
            continue

        cost = estimate_tokens(chunk.text)
        remaining = budget_tokens - used

        if cost <= remaining:
            kept.append(chunk)
            seen_tokens.append(tokens)
            used += cost
            continue

        # Does not fit whole. Keep a worthwhile tail, otherwise drop it and
        # keep going -- a later chunk may be small enough to fit.
        if remaining >= _MIN_USEFUL_TAIL_TOKENS and not truncated:
            shortened = _truncate_to_tokens(chunk.text, remaining)
            kept.append(chunk.with_text(shortened))
            seen_tokens.append(frozenset(tokenize(shortened)))
            used += estimate_tokens(shortened)
            truncated = True
        else:
            over_budget += 1

    return CompressionResult(
        chunks=kept,
        used_tokens=used,
        dropped_duplicates=duplicates,
        dropped_over_budget=over_budget,
        truncated=truncated,
    )
