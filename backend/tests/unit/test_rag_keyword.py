"""Unit tests for BM25 keyword scoring — the lexical half of hybrid search."""

from __future__ import annotations

from app.platform.rag.keyword import bm25_rank, query_terms, tokenize


class TestTokenize:
    def test_lowercases_and_strips_punctuation(self) -> None:
        assert tokenize("Vacation Policy, 2026!") == ["vacation", "policy", "2026"]

    def test_drops_stopwords(self) -> None:
        assert tokenize("the cost of the report") == ["cost", "report"]

    def test_keeps_alphanumeric_identifiers_intact(self) -> None:
        """Part numbers and codes are exactly what BM25 is here to catch."""
        assert tokenize("error AS9 code") == ["error", "as9", "code"]

    def test_empty_text_yields_no_tokens(self) -> None:
        assert tokenize("   ") == []


class TestQueryTerms:
    def test_deduplicates_while_preserving_order(self) -> None:
        assert query_terms("budget budget report") == ["budget", "report"]

    def test_a_query_of_only_stopwords_has_no_terms(self) -> None:
        assert query_terms("what is the") == []


class TestBm25Rank:
    def test_ranks_the_document_containing_the_query_first(self) -> None:
        documents = [
            "The cafeteria menu changes weekly.",
            "Employees receive twenty vacation days per year.",
            "Parking permits are issued quarterly.",
        ]

        ranked = bm25_rank("vacation days", documents)

        assert ranked[0][0] == 1

    def test_documents_sharing_no_terms_are_excluded(self) -> None:
        """Ranked last would still put them in the context window."""
        documents = ["vacation days policy", "unrelated parking text"]

        ranked = bm25_rank("vacation", documents)

        assert [index for index, _ in ranked] == [0]

    def test_rare_terms_outweigh_common_ones(self) -> None:
        """The IDF term is what makes keyword search useful rather than noisy."""
        documents = [
            "report report report report",  # many hits on the common term
            "report about zylonite",  # one hit on the rare term
            "report about budgets",
            "report about staffing",
            "report about parking",
        ]

        ranked = bm25_rank("report zylonite", documents)

        assert ranked[0][0] == 1

    def test_shorter_documents_win_at_equal_term_frequency(self) -> None:
        """Length normalisation: a hit in 5 words beats a hit in 500."""
        documents = ["vacation", "vacation " + "filler " * 200]

        ranked = bm25_rank("vacation", documents)

        assert ranked[0][0] == 0

    def test_scores_descend(self) -> None:
        documents = ["vacation days", "vacation", "days off work entirely"]

        ranked = bm25_rank("vacation days", documents)
        scores = [score for _, score in ranked]

        assert scores == sorted(scores, reverse=True)

    def test_empty_query_or_corpus_yields_nothing(self) -> None:
        assert bm25_rank("", ["some text"]) == []
        assert bm25_rank("vacation", []) == []

    def test_stopword_only_query_yields_nothing(self) -> None:
        """Otherwise every document matches and ranking is meaningless."""
        assert bm25_rank("what is the", ["what is the policy"]) == []

    def test_documents_with_no_tokens_do_not_divide_by_zero(self) -> None:
        assert bm25_rank("vacation", ["!!!", "???"]) == []

    def test_is_deterministic_across_ties(self) -> None:
        documents = ["vacation", "vacation", "vacation"]

        first = bm25_rank("vacation", documents)
        second = bm25_rank("vacation", documents)

        assert first == second
        assert [index for index, _ in first] == [0, 1, 2]
