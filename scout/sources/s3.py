"""
S3Source
========

Compile-only source (spec §4.5). One instance per `bucket[:prefix]` entry
in S3_BUCKETS.

- `list` → paginated list_objects_v2.
- `read` → get_object + LocalFolder-style extraction (PDF/docx/html/text).
  Objects >25 MB skip text extraction and return bytes only — the
  Compiler will log `skipped-empty` for them (tmp/spec-diff.md A7).
- `metadata` → head_object.
- `health` → head_bucket.
- `find` → not supported; rely on compile → local:wiki.
- capabilities: LIST, READ, METADATA. No find.

Auth comes from AWS_* env; boto3 is imported lazily so S3 being off
doesn't pull boto3 in at startup.
"""

from __future__ import annotations

import mimetypes

from scout.sources.base import (
    Capability,
    Content,
    Entry,
    FindKind,
    HealthState,
    HealthStatus,
    Hit,
    Meta,
    NotSupported,
    SourceError,
)

_MAX_TEXT_EXTRACT_BYTES = 25 * 1024 * 1024  # 25 MB
_PRESIGN_TTL_S = 900  # 15 min
_TEXT_EXTS = {".md", ".markdown", ".txt", ".json", ".yaml", ".yml", ".csv", ".html", ".htm"}
_PDF_EXTS = {".pdf"}
_DOCX_EXTS = {".docx"}


def _extract_text(key: str, raw: bytes) -> str | None:
    """Same extractors as LocalFolderSource, scoped by key suffix."""
    lower = key.lower()
    try:
        if any(lower.endswith(e) for e in _TEXT_EXTS):
            text = raw.decode("utf-8", errors="replace")
            if lower.endswith((".html", ".htm")):
                try:
                    from bs4 import BeautifulSoup  # type: ignore[import-not-found]

                    return BeautifulSoup(text, "html.parser").get_text(separator="\n")
                except ImportError:
                    return text
            return text
        if any(lower.endswith(e) for e in _PDF_EXTS):
            try:
                from io import BytesIO

                from pypdf import PdfReader  # type: ignore[import-not-found]

                reader = PdfReader(BytesIO(raw))
                return "\n\n".join(p.extract_text() or "" for p in reader.pages)
            except ImportError:
                return None
        if any(lower.endswith(e) for e in _DOCX_EXTS):
            try:
                from io import BytesIO

                from docx import Document  # type: ignore[import-not-found]

                doc = Document(BytesIO(raw))
                return "\n\n".join(p.text for p in doc.paragraphs)
            except ImportError:
                return None
    except Exception:
        return None
    return None


class S3Source:
    """Compile-only S3 bucket (optionally scoped to a key prefix)."""

    def __init__(
        self,
        bucket: str,
        *,
        prefix: str = "",
        region: str = "",
        aws_access_key_id: str = "",
        aws_secret_access_key: str = "",
        id: str | None = None,
        name: str | None = None,
        compile: bool = True,
        live_read: bool = False,
    ) -> None:
        self.bucket = bucket
        self.prefix = prefix.lstrip("/")
        self.region = region
        self._aws_key = aws_access_key_id
        self._aws_secret = aws_secret_access_key
        self.id = id or (f"s3:{bucket}/{self.prefix}" if self.prefix else f"s3:{bucket}")
        self.name = name or (f"S3 {bucket}/{self.prefix}" if self.prefix else f"S3 {bucket}")
        self.compile = compile
        self.live_read = live_read
        self._client = None  # type: ignore[var-annotated]

    # ------------------------------------------------------------------
    # Client lifecycle
    # ------------------------------------------------------------------

    def _client_or_none(self):
        if self._client is not None:
            return self._client
        try:
            import boto3  # type: ignore[import-not-found]
        except ImportError:
            return None
        kwargs = {"region_name": self.region} if self.region else {}
        if self._aws_key and self._aws_secret:
            kwargs["aws_access_key_id"] = self._aws_key
            kwargs["aws_secret_access_key"] = self._aws_secret
        self._client = boto3.client("s3", **kwargs)
        return self._client

    # ------------------------------------------------------------------
    # Protocol surface
    # ------------------------------------------------------------------

    def list(self, path: str = "") -> list[Entry]:
        client = self._client_or_none()
        if client is None:
            raise SourceError("S3 client not configured (missing boto3 or credentials)")
        scope = "/".join(filter(None, [self.prefix, path.lstrip("/")]))
        entries: list[Entry] = []
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=scope):
            for obj in page.get("Contents", []) or []:
                key = obj["Key"]
                entries.append(
                    Entry(
                        id=key,
                        name=key.split("/")[-1],
                        kind="file",
                        path=key,
                        size=obj.get("Size"),
                        modified_at=(
                            obj["LastModified"].isoformat() if obj.get("LastModified") else None
                        ),
                    )
                )
        return entries

    def read(self, entry_id: str) -> Content:
        client = self._client_or_none()
        if client is None:
            raise SourceError("S3 client not configured")
        try:
            resp = client.get_object(Bucket=self.bucket, Key=entry_id)
        except Exception as e:
            raise SourceError(f"get_object failed: {e}") from e
        raw = resp["Body"].read()
        text: str | None = None
        if len(raw) <= _MAX_TEXT_EXTRACT_BYTES:
            text = _extract_text(entry_id, raw)
        mime = resp.get("ContentType") or mimetypes.guess_type(entry_id)[0] or "application/octet-stream"
        try:
            presigned = client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": entry_id},
                ExpiresIn=_PRESIGN_TTL_S,
            )
        except Exception:
            presigned = None
        return Content(
            bytes=raw,
            text=text,
            mime=mime,
            source_url=presigned,
            citation_hint=f"s3://{self.bucket}/{entry_id}",
        )

    def metadata(self, entry_id: str) -> Meta:
        client = self._client_or_none()
        if client is None:
            raise SourceError("S3 client not configured")
        try:
            resp = client.head_object(Bucket=self.bucket, Key=entry_id)
        except Exception as e:
            raise SourceError(f"head_object failed: {e}") from e
        return Meta(
            name=entry_id.split("/")[-1],
            mime=resp.get("ContentType") or mimetypes.guess_type(entry_id)[0],
            size=resp.get("ContentLength"),
            modified_at=resp["LastModified"].isoformat() if resp.get("LastModified") else None,
            source_url=None,
            extra={"key": entry_id, "etag": resp.get("ETag")},
        )

    def health(self) -> HealthStatus:
        if not self.bucket:
            return HealthStatus(HealthState.UNCONFIGURED, "bucket not set")
        if not (self._aws_key and self._aws_secret and self.region):
            return HealthStatus(HealthState.UNCONFIGURED, "AWS credentials/region missing")
        client = self._client_or_none()
        if client is None:
            return HealthStatus(HealthState.UNCONFIGURED, "boto3 not installed")
        try:
            client.head_bucket(Bucket=self.bucket)
        except Exception as e:
            return HealthStatus(HealthState.DEGRADED, str(e)[:160])
        scope = f"{self.bucket}/{self.prefix}" if self.prefix else self.bucket
        return HealthStatus(HealthState.CONNECTED, scope)

    def capabilities(self) -> set[Capability]:
        return {Capability.LIST, Capability.READ, Capability.METADATA}

    def find(self, query: str, kind: FindKind = FindKind.LEXICAL) -> list[Hit]:
        raise NotSupported(
            "S3Source has no native find. Compile the bucket and search via local:wiki."
        )


def parse_bucket_spec(spec: str) -> tuple[str, str]:
    """`bucket:prefix` → ('bucket', 'prefix'). Bare bucket → ('bucket', '')."""
    bucket, _, prefix = spec.partition(":")
    return bucket.strip(), prefix.strip()
