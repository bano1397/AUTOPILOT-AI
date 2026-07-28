"""S3-compatible implementation of :class:`StorageProvider`.

Durable object storage for deployments whose container disk is ephemeral (Render
and Hugging Face free tiers wipe it on restart, taking uploaded file bytes with
it). Works against any S3 API implementation — Cloudflare R2, AWS S3, MinIO,
Backblaze B2.

**Why no boto3.** Same reasoning as the Ollama and Chroma providers (see
``docs/PROJECT_ANALYSIS.md`` §7 decision 7): the needed surface is three verbs
(PUT / GET / DELETE on one key), the wire format is unit-testable with
``httpx.MockTransport``, and boto3 would add a large transitive dependency tree
plus a thread-pool bridge for what is one signed HTTP request.

**Signing.** AWS Signature Version 4, header-based, with a signed payload hash.
The implementation is exercised by unit tests that assert canonical-request
structure, header set, and signature determinism, and by an opt-in integration
test (``AUTOPILOT_S3_TESTS=1``) that round-trips against a real endpoint.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime
from urllib.parse import quote
from uuid import uuid4

import httpx

from app.core.exceptions import UpstreamServiceError
from app.platform.registry import register_provider

_ALGORITHM = "AWS4-HMAC-SHA256"
_SERVICE = "s3"
_TIMEOUT = 30.0


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _hmac(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode(), hashlib.sha256).digest()


def _encode_key(key: str) -> str:
    """URI-encode an object key, preserving path separators (S3 rules)."""
    return quote(key, safe="/~")


@register_provider(kind="storage", name="s3")
class S3StorageProvider:
    """Stores objects in an S3-compatible bucket under random keys."""

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        region: str = "auto",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._bucket = bucket
        self._endpoint = endpoint_url.rstrip("/")
        self._access_key = access_key_id
        self._secret_key = secret_access_key
        # R2 accepts the literal "auto"; AWS needs a real region name.
        self._region = region
        self._client = client

    # -- signing ---------------------------------------------------------

    def _signing_key(self, date_stamp: str) -> bytes:
        key = f"AWS4{self._secret_key}".encode()
        key = _hmac(key, date_stamp)
        key = _hmac(key, self._region)
        key = _hmac(key, _SERVICE)
        return _hmac(key, "aws4_request")

    def _signed_headers(
        self, method: str, key: str, payload: bytes, *, now: datetime | None = None
    ) -> dict[str, str]:
        """Build the Authorization + x-amz-* headers for one request."""
        stamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
        date_stamp = stamp[:8]
        host = httpx.URL(self._endpoint).host
        payload_hash = _sha256_hex(payload)

        # Canonical request. Header names must be lowercase and sorted; the
        # signed-header list must match the headers actually sent.
        canonical_headers = (
            f"host:{host}\n"
            f"x-amz-content-sha256:{payload_hash}\n"
            f"x-amz-date:{stamp}\n"
        )
        signed_header_names = "host;x-amz-content-sha256;x-amz-date"
        canonical_request = "\n".join(
            [
                method,
                _encode_key(f"/{self._bucket}/{key}"),
                "",  # no query string on any of our three verbs
                canonical_headers,
                signed_header_names,
                payload_hash,
            ]
        )

        scope = f"{date_stamp}/{self._region}/{_SERVICE}/aws4_request"
        string_to_sign = "\n".join(
            [_ALGORITHM, stamp, scope, _sha256_hex(canonical_request.encode())]
        )
        signature = _hmac(self._signing_key(date_stamp), string_to_sign).hex()

        return {
            "Host": host or "",
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": stamp,
            "Authorization": (
                f"{_ALGORITHM} Credential={self._access_key}/{scope}, "
                f"SignedHeaders={signed_header_names}, Signature={signature}"
            ),
        }

    # -- transport -------------------------------------------------------

    async def _request(
        self, method: str, key: str, payload: bytes = b""
    ) -> httpx.Response:
        url = f"{self._endpoint}/{self._bucket}/{_encode_key(key)}"
        headers = self._signed_headers(method, key, payload)
        client = self._client
        try:
            if client is not None:
                return await client.request(
                    method, url, content=payload or None, headers=headers
                )
            async with httpx.AsyncClient(timeout=_TIMEOUT) as owned:
                return await owned.request(
                    method, url, content=payload or None, headers=headers
                )
        except httpx.HTTPError as exc:
            raise UpstreamServiceError(f"Object storage request failed: {exc}") from exc

    # -- StorageProvider -------------------------------------------------

    async def save(self, content: bytes, *, suffix: str = "") -> str:
        name = uuid4().hex + suffix
        # Same two-char sharding as the local provider, so keys are
        # interchangeable between the two and neither leaks a filename.
        key = f"{name[:2]}/{name}"
        response = await self._request("PUT", key, content)
        if response.status_code not in (200, 201):
            raise UpstreamServiceError(
                f"Object storage rejected upload ({response.status_code})"
            )
        return key

    async def get(self, path: str) -> bytes:
        response = await self._request("GET", path)
        if response.status_code == 404:
            # Mirror the local provider's contract so callers stay identical.
            raise FileNotFoundError(path)
        if response.status_code != 200:
            raise UpstreamServiceError(
                f"Object storage read failed ({response.status_code})"
            )
        return bytes(response.content)

    async def delete(self, path: str) -> None:
        response = await self._request("DELETE", path)
        # 204 = deleted, 404 = already gone; both satisfy "ensure absent".
        if response.status_code not in (200, 204, 404):
            raise UpstreamServiceError(
                f"Object storage delete failed ({response.status_code})"
            )

    def url_for(self, path: str) -> str:
        return f"{self._endpoint}/{self._bucket}/{_encode_key(path)}"
