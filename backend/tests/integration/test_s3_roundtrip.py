"""Opt-in round-trip against a real S3-compatible endpoint.

Signature correctness can only be proven by a server that accepts it, and no
CI-safe fake does that. Run against Cloudflare R2, AWS S3, or a local MinIO:

    AUTOPILOT_S3_TESTS=1 \\
    S3_BUCKET=... S3_ENDPOINT_URL=... S3_ACCESS_KEY_ID=... \\
    S3_SECRET_ACCESS_KEY=... S3_REGION=auto \\
    pytest tests/integration/test_s3_roundtrip.py

Follows the same opt-in pattern as ``test_external_providers.py``.
"""

from __future__ import annotations

import os

import pytest
from app.infrastructure.storage.s3 import S3StorageProvider

_ENABLED = os.getenv("AUTOPILOT_S3_TESTS") == "1"
_REQUIRED = ("S3_BUCKET", "S3_ENDPOINT_URL", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY")

pytestmark = pytest.mark.skipif(
    not _ENABLED or any(not os.getenv(name) for name in _REQUIRED),
    reason="real object storage (set AUTOPILOT_S3_TESTS=1 plus S3_* credentials)",
)


def _provider() -> S3StorageProvider:
    return S3StorageProvider(
        bucket=os.environ["S3_BUCKET"],
        endpoint_url=os.environ["S3_ENDPOINT_URL"],
        access_key_id=os.environ["S3_ACCESS_KEY_ID"],
        secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"],
        region=os.getenv("S3_REGION", "auto"),
    )


async def test_save_get_delete_round_trip() -> None:
    provider = _provider()
    payload = b"autopilot s3 round-trip"

    key = await provider.save(payload, suffix=".txt")
    try:
        assert await provider.get(key) == payload
    finally:
        await provider.delete(key)

    with pytest.raises(FileNotFoundError):
        await provider.get(key)


async def test_delete_is_idempotent() -> None:
    provider = _provider()
    key = await provider.save(b"once")

    await provider.delete(key)
    await provider.delete(key)  # second delete must not raise
