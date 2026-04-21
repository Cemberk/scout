"""Shared boto3 helpers for S3ContextProvider + S3WikiBackend."""

from __future__ import annotations

import os


def build_client():
    """Build a boto3 S3 client from AWS_* env. Caller handles exceptions."""
    import boto3

    return boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID") or None,
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY") or None,
        region_name=os.getenv("AWS_REGION") or None,
    )


def normalize_prefix(prefix: str) -> str:
    """Strip leading slashes; ensure exactly one trailing slash if non-empty."""
    stripped = prefix.strip("/")
    return f"{stripped}/" if stripped else ""
