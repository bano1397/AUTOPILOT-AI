"""Unit tests for the S3-compatible storage provider.

The wire format and SigV4 signing are asserted against captured requests via
``httpx.MockTransport``. These tests pin structure and determinism — they cannot
prove the signature is *accepted* by a real S3 implementation; that is what the
opt-in ``tests/integration/test_s3_roundtrip.py`` is for.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import httpx
import pytest
from app.core.exceptions import UpstreamServiceError
from app.infrastructure.storage.s3 import S3StorageProvider

_CREDS = {
    "bucket": "autopilot",
    "endpoint_url": "https://acct.r2.cloudflarestorage.com",
    "access_key_id": "AKIAEXAMPLE",
    "secret_access_key": "secret-example",
    "region": "auto",
}


def _provider(handler: object) -> tuple[S3StorageProvider, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def _capture(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)  # type: ignore[operator]

    client = httpx.AsyncClient(transport=httpx.MockTransport(_capture))
    return S3StorageProvider(**_CREDS, client=client), seen  # type: ignore[arg-type]


async def test_save_puts_content_under_a_random_sharded_key() -> None:
    provider, seen = _provider(lambda _: httpx.Response(200))

    key = await provider.save(b"hello world", suffix=".txt")

    assert key.endswith(".txt")
    # Two-char shard prefix, matching the local provider's layout.
    shard, name = key.split("/")
    assert len(shard) == 2 and name.startswith(shard)
    request = seen[0]
    assert request.method == "PUT"
    assert str(request.url) == f"{_CREDS['endpoint_url']}/autopilot/{key}"
    assert request.content == b"hello world"


async def test_save_generates_a_fresh_key_each_time() -> None:
    provider, _ = _provider(lambda _: httpx.Response(200))

    first = await provider.save(b"a")
    second = await provider.save(b"a")

    assert first != second  # never derived from the caller's filename


async def test_signed_headers_carry_payload_hash_and_credential_scope() -> None:
    provider, seen = _provider(lambda _: httpx.Response(200))

    await provider.save(b"payload")

    headers = seen[0].headers
    assert headers["x-amz-content-sha256"] == hashlib.sha256(b"payload").hexdigest()
    assert headers["x-amz-date"].endswith("Z")
    auth = headers["authorization"]
    assert auth.startswith("AWS4-HMAC-SHA256 Credential=AKIAEXAMPLE/")
    assert "/auto/s3/aws4_request" in auth
    # The signed-header list must match the headers actually sent.
    assert "SignedHeaders=host;x-amz-content-sha256;x-amz-date" in auth
    assert "Signature=" in auth


def test_signature_is_deterministic_for_a_fixed_timestamp() -> None:
    provider = S3StorageProvider(**_CREDS)  # type: ignore[arg-type]
    moment = datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC)

    first = provider._signed_headers("GET", "ab/abcdef.txt", b"", now=moment)
    second = provider._signed_headers("GET", "ab/abcdef.txt", b"", now=moment)

    assert first == second
    assert first["x-amz-date"] == "20260728T120000Z"
    assert "Credential=AKIAEXAMPLE/20260728/auto/s3/aws4_request" in first["Authorization"]


def test_signature_changes_with_method_key_and_payload() -> None:
    provider = S3StorageProvider(**_CREDS)  # type: ignore[arg-type]
    moment = datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC)

    base = provider._signed_headers("GET", "ab/one.txt", b"", now=moment)
    other_method = provider._signed_headers("PUT", "ab/one.txt", b"", now=moment)
    other_key = provider._signed_headers("GET", "ab/two.txt", b"", now=moment)
    other_body = provider._signed_headers("GET", "ab/one.txt", b"x", now=moment)

    signatures = {
        headers["Authorization"].split("Signature=")[1]
        for headers in (base, other_method, other_key, other_body)
    }
    assert len(signatures) == 4  # every component is actually signed


async def test_get_returns_content() -> None:
    provider, seen = _provider(lambda _: httpx.Response(200, content=b"stored"))

    assert await provider.get("ab/abcdef.txt") == b"stored"
    assert seen[0].method == "GET"


async def test_get_missing_object_raises_file_not_found() -> None:
    """Callers already handle FileNotFoundError from the local provider."""
    provider, _ = _provider(lambda _: httpx.Response(404))

    with pytest.raises(FileNotFoundError):
        await provider.get("ab/gone.txt")


async def test_get_server_error_surfaces_as_upstream_error() -> None:
    provider, _ = _provider(lambda _: httpx.Response(503))

    with pytest.raises(UpstreamServiceError):
        await provider.get("ab/abcdef.txt")


@pytest.mark.parametrize("status", [200, 204, 404])
async def test_delete_treats_absent_as_success(status: int) -> None:
    provider, seen = _provider(lambda _: httpx.Response(status))

    await provider.delete("ab/abcdef.txt")

    assert seen[0].method == "DELETE"


async def test_delete_failure_surfaces_as_upstream_error() -> None:
    provider, _ = _provider(lambda _: httpx.Response(500))

    with pytest.raises(UpstreamServiceError):
        await provider.delete("ab/abcdef.txt")


async def test_upload_rejection_surfaces_as_upstream_error() -> None:
    provider, _ = _provider(lambda _: httpx.Response(403))

    with pytest.raises(UpstreamServiceError):
        await provider.save(b"denied")


async def test_transport_failure_surfaces_as_upstream_error() -> None:
    def _boom(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    provider, _ = _provider(_boom)

    with pytest.raises(UpstreamServiceError):
        await provider.save(b"x")


def test_url_for_is_a_diagnostic_locator() -> None:
    provider = S3StorageProvider(**_CREDS)  # type: ignore[arg-type]

    assert provider.url_for("ab/abcdef.txt") == (
        "https://acct.r2.cloudflarestorage.com/autopilot/ab/abcdef.txt"
    )
