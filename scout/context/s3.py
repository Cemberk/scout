"""S3Context — agentic read-only context over an S3 bucket + prefix.

Registered via ``SCOUT_CONTEXTS=s3:<bucket>[/<prefix>]``. The agent has
``list_keys`` / ``get_object`` / ``head_object`` scoped to the configured
prefix.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from agno.agent import Agent
from agno.models.openai import OpenAIResponses
from agno.tools import tool

from scout.context._shared import answer_from_run
from scout.context.backends._s3 import build_client, normalize_prefix
from scout.context.base import Answer, HealthState, HealthStatus

log = logging.getLogger(__name__)


class S3Context:
    """Agentic read-only context over a bucket + prefix."""

    kind: str = "s3"

    def __init__(self, bucket: str, prefix: str = "") -> None:
        self.bucket = bucket
        self.prefix = normalize_prefix(prefix)
        display_prefix = prefix.strip("/")
        self.id = f"s3:{bucket}/{display_prefix}" if display_prefix else f"s3:{bucket}"
        self.name = self.id.replace("s3:", "")
        self._agent: Agent | None = None

    def health(self) -> HealthStatus:
        try:
            client = build_client()
            client.head_bucket(Bucket=self.bucket)
        except Exception as exc:
            return HealthStatus(HealthState.DISCONNECTED, f"head_bucket failed: {exc}")
        return HealthStatus(HealthState.CONNECTED, self.id)

    def query(
        self,
        question: str,
        *,
        limit: int = 10,
        filters: dict | None = None,
    ) -> Answer:
        del filters, limit
        agent = self._ensure_agent()
        return answer_from_run(agent.run(question))

    def _ensure_agent(self) -> Agent:
        if self._agent is None:
            self._agent = self._build_agent()
        return self._agent

    def _build_agent(self) -> Agent:
        return Agent(
            id=f"s3-context-{self.bucket}",
            name=f"S3Context({self.id})",
            role=f"Read-only exploration of s3://{self.bucket}/{self.prefix}",
            model=OpenAIResponses(id="gpt-5.4"),
            instructions=_instructions(self.id),
            tools=_s3_tools(self.bucket, self.prefix),
            markdown=True,
        )


def _s3_tools(bucket: str, prefix: str) -> list:
    """list_keys / head_object / get_object, scoped to bucket + prefix."""

    def _scoped(key: str) -> str:
        """Force every key through the configured prefix."""
        key = key.lstrip("/")
        if prefix and not key.startswith(prefix):
            return f"{prefix}{key}"
        return key

    @tool
    def list_keys(sub_prefix: str = "", limit: int = 50) -> str:
        """List object keys under the configured prefix (optionally narrowed).

        Args:
            sub_prefix: Extra suffix appended to the context's base prefix.
            limit: Max keys to return.
        """
        full_prefix = prefix + sub_prefix.lstrip("/") if sub_prefix else prefix
        client = build_client()
        try:
            resp = client.list_objects_v2(Bucket=bucket, Prefix=full_prefix, MaxKeys=limit)
        except Exception as exc:
            return json.dumps({"error": f"{type(exc).__name__}: {exc}"})
        contents: list[dict[str, Any]] = []
        for obj in resp.get("Contents") or []:
            contents.append(
                {
                    "key": obj.get("Key"),
                    "size": obj.get("Size"),
                    "last_modified": str(obj.get("LastModified")),
                }
            )
        return json.dumps({"keys": contents, "truncated": resp.get("IsTruncated", False)})

    @tool
    def head_object(key: str) -> str:
        """Return HEAD metadata for a key (scoped under the context's prefix)."""
        full_key = _scoped(key)
        client = build_client()
        try:
            resp = client.head_object(Bucket=bucket, Key=full_key)
        except Exception as exc:
            return json.dumps({"error": f"{type(exc).__name__}: {exc}"})
        return json.dumps(
            {
                "key": full_key,
                "size": resp.get("ContentLength"),
                "content_type": resp.get("ContentType"),
                "etag": resp.get("ETag"),
                "last_modified": str(resp.get("LastModified")),
            }
        )

    @tool
    def get_object(key: str, max_bytes: int = 200_000) -> str:
        """Fetch an object's body as UTF-8 text (truncated).

        Args:
            key: Object key (scoped under the context's prefix).
            max_bytes: Soft cap on bytes read.
        """
        full_key = _scoped(key)
        client = build_client()
        try:
            resp = client.get_object(Bucket=bucket, Key=full_key, Range=f"bytes=0-{max_bytes - 1}")
            data = resp["Body"].read()
        except Exception as exc:
            return json.dumps({"error": f"{type(exc).__name__}: {exc}"})
        try:
            return data.decode("utf-8", errors="replace")
        except Exception:
            return json.dumps({"key": full_key, "binary_bytes": len(data)})

    return [list_keys, head_object, get_object]


def _instructions(target_id: str) -> str:
    return f"""\
You are a read-only explorer of `{target_id}`.

Answer questions by:
- `list_keys` to see what's there (narrow with `sub_prefix`)
- `head_object` to check size / content type before downloading
- `get_object` to read text (capped at 200KB by default)

Cite the S3 key in your answer so the user can fetch it themselves. If
you find nothing, say what you searched. Never output secrets or
credentials, even if they appear inside an object.
"""
