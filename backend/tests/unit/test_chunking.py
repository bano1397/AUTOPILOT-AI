"""Unit tests for the sliding-window text chunker."""

from __future__ import annotations

import pytest
from app.platform.rag import TextChunker


def test_empty_and_whitespace_text_yield_no_chunks() -> None:
    chunker = TextChunker(chunk_size=100, chunk_overlap=20)
    assert chunker.split("") == []
    assert chunker.split("   \n\t  ") == []


def test_short_text_is_a_single_chunk() -> None:
    chunks = TextChunker(chunk_size=100, chunk_overlap=20).split("hello world")
    assert len(chunks) == 1
    assert chunks[0].index == 0
    assert chunks[0].text == "hello world"


def test_long_text_is_split_with_overlap() -> None:
    words = " ".join(f"word{i}" for i in range(200))
    chunks = TextChunker(chunk_size=100, chunk_overlap=30).split(words)

    assert len(chunks) > 1
    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))
    for chunk in chunks:
        assert len(chunk.text) <= 100
    # Consecutive chunks share content (the overlap).
    for previous, current in zip(chunks, chunks[1:], strict=False):
        tail_word = previous.text.split()[-1]
        assert tail_word in current.text

    # Reassembly sanity: every source word appears somewhere.
    combined = " ".join(chunk.text for chunk in chunks)
    assert all(f"word{i}" in combined for i in range(200))


def test_chunks_break_at_whitespace() -> None:
    words = " ".join(["abcdefghij"] * 50)
    chunks = TextChunker(chunk_size=100, chunk_overlap=10).split(words)
    for chunk in chunks:
        # A soft break never cuts a word in half.
        assert all(word == "abcdefghij" for word in chunk.text.split())


def test_unbroken_text_still_makes_progress() -> None:
    text = "x" * 500  # no whitespace anywhere
    chunks = TextChunker(chunk_size=100, chunk_overlap=20).split(text)
    assert len(chunks) >= 5
    assert "".join(c.text for c in chunks).count("x") >= 500


def test_invalid_parameters_are_rejected() -> None:
    with pytest.raises(ValueError):
        TextChunker(chunk_size=0)
    with pytest.raises(ValueError):
        TextChunker(chunk_size=100, chunk_overlap=100)
    with pytest.raises(ValueError):
        TextChunker(chunk_size=100, chunk_overlap=-1)
