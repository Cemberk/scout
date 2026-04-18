---
source: local:raw:api-design-principles.md
source_url: file:///app/context/raw/api-design-principles.md
source_hash: cccf594dc168b69f1232cc804d4924ca6711b089b8eb5c0a900668f3f90cf66a
compiled_at: 2026-04-18T07:54:47Z
compiled_by: scout-compiler-v3
user_edited: false
needs_split: false
tags:
backlinks:
---

# API Design Principles

ACME HTTP APIs use consistent resource-oriented conventions for payload shape, errors, versioning, and authentication. New endpoints must follow these rules, and drift in existing endpoints is reviewed weekly and corrected.

## Shape

- Model resources as nouns; actions belong in the HTTP method.
- Use JSON only.
- Set `Content-Type: application/json; charset=utf-8`.
- Use `snake_case` for field names.
- Do not return `null`; omit the key instead.
- Paginate every list endpoint with `limit` and `cursor`.
- Do not use offset-based pagination.

## Errors

Use 4xx status codes for caller mistakes and 5xx status codes for server failures.

Error responses use this body shape:

```json
{
  "error": {
    "code": "...",
    "message": "...",
    "details": {}
  }
}
```

Error codes are stable `UPPER_SNAKE` strings and are never renumbered.

## Versioning

Breaking changes require a new URL version prefix, such as `/v1/...` to `/v2/...`. Additive changes do not require a version bump.

Deprecated endpoints return a `Sunset` header for 90 days before removal. This deprecation window applies before the endpoint is taken away.

## Authentication

Internal services authenticate with mTLS. External clients authenticate with [[OAuth2 Bearer Tokens]].

Basic auth is not allowed. API keys must not be accepted in query strings; credentials go in the `Authorization` header only.

## Governance

New endpoints must match these conventions. Existing endpoints that drift are flagged in the weekly wiki lint review and fixed.

## See also

- [[API Versioning]]
- [[OAuth2 Bearer Tokens]]
- [[HTTP Error Format]]
- [[Pagination]]
