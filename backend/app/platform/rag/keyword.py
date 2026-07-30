"""BM25 keyword scoring — the lexical half of hybrid retrieval (§17).

Vector search matches meaning and misses exact tokens: part numbers, error
codes, surnames, "Q3-2026". BM25 matches those and misses paraphrase. Hybrid
retrieval runs both and fuses the rankings (see :mod:`app.platform.rag.fusion`).

Pure logic over text passed in by the caller: no I/O, no database, no
dependency on which store the text came from.

**Scoring is over the candidate set, not the whole corpus.** IDF is computed
from the candidates the database prefilter returned rather than from every
chunk, because true corpus IDF would need a document-frequency count per term
per query. Within a candidate set the ordering stays directionally right —
terms common across candidates are still discounted relative to rare ones — but
the scores are not comparable to a corpus-wide BM25 implementation, and they
are not meant to be: only the *ranking* feeds fusion.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Deliberately tiny. An aggressive stop-list hurts exactly the queries BM25 is
# here to serve -- "who owns the AS-9 line" needs "as" and "9".
_STOPWORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
        "in", "is", "it", "of", "on", "or", "that", "the", "to", "was", "were",
        "what", "which", "with",
    }
)

# BM25 tuning. These are the values the original TREC experiments settled on
# and remain the standard default; nothing here is tuned to this corpus.
_K1 = 1.5
_B = 0.75


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens, stop-words removed."""
    return [
        token
        for token in _TOKEN_RE.findall(text.lower())
        if token not in _STOPWORDS
    ]


def query_terms(query: str) -> list[str]:
    """Distinct query tokens, order preserved.

    Deduplicated because a term repeated in the query would otherwise
    multiply its own contribution to every document's score.
    """
    seen: set[str] = set()
    terms: list[str] = []
    for token in tokenize(query):
        if token not in seen:
            seen.add(token)
            terms.append(token)
    return terms


def bm25_rank(query: str, documents: Sequence[str]) -> list[tuple[int, float]]:
    """Rank ``documents`` against ``query``, best first.

    Returns ``(index, score)`` pairs for documents scoring above zero, so a
    document sharing no terms with the query is dropped rather than ranked
    last. An empty query or corpus yields no results.
    """
    terms = query_terms(query)
    if not terms or not documents:
        return []

    tokenized = [tokenize(document) for document in documents]
    lengths = [len(tokens) for tokens in tokenized]
    total = len(tokenized)
    average_length = sum(lengths) / total if total else 0.0
    if average_length == 0.0:
        return []

    counts = [Counter(tokens) for tokens in tokenized]
    document_frequency = {
        term: sum(1 for count in counts if term in count) for term in terms
    }

    scored: list[tuple[int, float]] = []
    for index, count in enumerate(counts):
        score = 0.0
        for term in terms:
            frequency = count.get(term, 0)
            if frequency == 0:
                continue
            # Robertson/Sparck-Jones IDF with the +1 smoothing that keeps it
            # positive when a term appears in more than half the candidates.
            frequency_in_corpus = document_frequency[term]
            idf = math.log(
                1.0
                + (total - frequency_in_corpus + 0.5) / (frequency_in_corpus + 0.5)
            )
            normalization = _K1 * (
                1.0 - _B + _B * (lengths[index] / average_length)
            )
            score += idf * (frequency * (_K1 + 1.0)) / (frequency + normalization)
        if score > 0.0:
            scored.append((index, score))

    scored.sort(key=lambda item: (-item[1], item[0]))
    return scored
