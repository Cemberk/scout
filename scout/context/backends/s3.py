"""S3Backend — WikiBackend backed by an S3 bucket + prefix.

Raw + compiled + state live as S3 keys. Concurrency on the state key
(``.scout/state.json``) uses S3 conditional PUT via ``If-Match: <etag>``:
if another container updated the state since we last read, the PUT
fails with 412; we re-read and retry.

Regular keys (raw/ + compiled/) use plain put_object / get_object /
delete. The wiki compile pipeline treats the state key as the sync
point — raw/ and compiled/ can race without coordination because the
state file records which compiled output corresponds to which raw hash.
"""

from __future__ import annotations

import logging
import time

from scout.context.backends._s3 import build_client, normalize_prefix
from scout.context.base import HealthState, HealthStatus

log = logging.getLogger(__name__)

STATE_KEY_SUFFIX = ".scout/state.json"
_STATE_PUT_RETRIES = 3


class S3Backend:
    """WikiBackend whose substrate is an S3 bucket + prefix."""

    kind: str = "s3"

    def __init__(self, bucket: str, prefix: str = "") -> None:
        self.bucket = bucket
        self.prefix = normalize_prefix(prefix)
        self._state_etag: str | None = None

    def health(self) -> HealthStatus:
        try:
            client = build_client()
            client.head_bucket(Bucket=self.bucket)
        except Exception as exc:
            return HealthStatus(HealthState.DISCONNECTED, f"head_bucket failed: {exc}")
        display = f"s3://{self.bucket}/{self.prefix}" if self.prefix else f"s3://{self.bucket}"
        return HealthStatus(HealthState.CONNECTED, display)

    # ------------------------------------------------------------------
    # WikiBackend protocol
    # ------------------------------------------------------------------

    def list_paths(self, prefix: str = "") -> list[str]:
        full_prefix = self.prefix + prefix.lstrip("/") if prefix else self.prefix
        client = build_client()
        paginator = client.get_paginator("list_objects_v2")
        out: list[str] = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=full_prefix):
            for obj in page.get("Contents") or []:
                key = obj.get("Key", "")
                if self.prefix and key.startswith(self.prefix):
                    out.append(key[len(self.prefix) :])
                else:
                    out.append(key)
        return sorted(out)

    def read_bytes(self, path: str) -> bytes:
        key = self._key(path)
        client = build_client()
        resp = client.get_object(Bucket=self.bucket, Key=key)
        data = resp["Body"].read()
        if path == STATE_KEY_SUFFIX:
            # Cache the state etag so the next write_bytes can use If-Match.
            self._state_etag = resp.get("ETag")
        return data

    def write_bytes(self, path: str, content: bytes) -> None:
        """Regular writes are unconditional PUTs. The state key uses
        ``If-Match`` on the etag cached from the last read; on 412 we
        re-read and retry."""
        if path == STATE_KEY_SUFFIX:
            self._write_state(content)
            return
        key = self._key(path)
        client = build_client()
        client.put_object(Bucket=self.bucket, Key=key, Body=content)

    def delete(self, path: str) -> None:
        key = self._key(path)
        client = build_client()
        client.delete_object(Bucket=self.bucket, Key=key)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _key(self, path: str) -> str:
        return f"{self.prefix}{path}" if self.prefix else path

    def _write_state(self, content: bytes) -> None:
        """Conditional PUT on ``.scout/state.json`` — retries on 412."""
        client = build_client()
        key = self._key(STATE_KEY_SUFFIX)
        for attempt in range(1, _STATE_PUT_RETRIES + 1):
            extra: dict[str, str] = {}
            if self._state_etag:
                # boto3 forwards IfMatch on put_object
                extra["IfMatch"] = self._state_etag
            try:
                resp = client.put_object(Bucket=self.bucket, Key=key, Body=content, **extra)
            except client.exceptions.ClientError as exc:
                code = (exc.response.get("Error") or {}).get("Code", "")
                if code in ("PreconditionFailed", "ConditionalRequestConflict"):
                    log.warning(
                        "S3Backend: state PUT 412 (attempt %d/%d); re-reading and retrying",
                        attempt,
                        _STATE_PUT_RETRIES,
                    )
                    # Re-fetch to refresh etag, then loop.
                    try:
                        head = client.head_object(Bucket=self.bucket, Key=key)
                        self._state_etag = head.get("ETag")
                    except Exception:
                        self._state_etag = None
                    time.sleep(0.2 * attempt)
                    continue
                raise
            self._state_etag = resp.get("ETag")
            return
        raise RuntimeError(f"S3Backend.state PUT failed after {_STATE_PUT_RETRIES} retries (etag conflict)")
