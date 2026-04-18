---
source: local:raw:api-design-principles.md
source_url: file:///app/context/raw/api-design-principles.md
source_hash: cccf594dc168b69f1232cc804d4924ca6711b089b8eb5c0a900668f3f90cf66a
compiled_at: 2026-04-18T07:40:14Z
compiled_by: scout-compiler-v3
user_edited: false
needs_split: false
tags:
backlinks:
---

# API Design Principles

ACME public and internal HTTP APIs use a consistent set of conventions for resource shape, errors, versioning, and authentication. New endpoints must follow these rules, and drift in existing endpoints is reviewed in a weekly wiki lint process and corrected.

## Resource shape

- Model resources as nouns; actions belong in the HTTP method.
- Use JSON only.
- Set `Content-Type: application/json; charset=utf-8`.
- Use `snake_case` for field names.
- Do not return null-valued fields; omit the key instead.

## Pagination

All list endpoints are paginated. Use `limit` and `cursor`; do not use offset-based pagination.

See [[Pagination]].

## Errors

Use 4xx status codes for caller mistakes and 5xx status codes for server-side failures. Error responses use this body shape:

```json
{ "error": { "code": "...", "message": "...", "details": {} } }
```

Error codes are stable `UPPER_SNAKE` strings and are never renumbered. See [[HTTP Error Model]].

## Versioning

Breaking changes require a new URL version prefix, for example `/v1/...` to `/v2/...`. Additive changes do not require a version bump.

Deprecated endpoints return a `Sunset` header for 90 days before removal. See [[API Versioning]].

## Authentication

Internal services use mTLS. External clients use [[OAuth2 Bearer Tokens]].

Do not use basic auth. Do not accept API keys in query strings; send credentials in the `Authorization` header only.

## See also

- [[API Versioning]]
- [[OAuth2 Bearer Tokens]]
- [[Pagination]]
- [[HTTP Error Model]]
