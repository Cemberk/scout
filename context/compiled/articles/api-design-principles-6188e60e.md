---
source: local:raw:api-design-principles.md
source_url: file:///app/context/raw/api-design-principles.md
source_hash: cccf594dc168b69f1232cc804d4924ca6711b089b8eb5c0a900668f3f90cf66a
compiled_at: 2026-04-18T07:19:06Z
compiled_by: scout-compiler-v3
user_edited: false
needs_split: false
tags:
backlinks:
---

# API Design Principles

ACME HTTP APIs use consistent resource-oriented conventions for payloads, errors, versioning, and authentication. New endpoints must follow these rules, and existing endpoints that drift are flagged in weekly wiki lint review and corrected.

## Shape

- Model resources as nouns; actions belong in the HTTP method.
- Use JSON only.
- Send `Content-Type: application/json; charset=utf-8`.
- Use `snake_case` for field names.
- Do not return `null`; omit the key instead.
- Paginate all list endpoints with `limit` and `cursor`.
- Do not use offset-based pagination.

## Errors

Use 4xx status codes for caller mistakes and 5xx for server-side failures.

Error responses use this body shape:

```json
{ "error": { "code": "...", "message": "...", "details": {} } }
```

Error `code` values are stable `UPPER_SNAKE` strings. They are not renumbered.

## Versioning

Breaking changes require a new URL version prefix, such as `/v1/...` to `/v2/...`. Additive changes do not require a version bump.

Deprecated endpoints return a `Sunset` header for 90 days before removal. The document does not specify any additional deprecation notice mechanism.

## Authentication

Internal services authenticate with mTLS. External clients use [[OAuth2 Bearer Tokens]].

Basic auth is not allowed. API keys are not accepted in query strings; credentials go in the `Authorization` header only.

## Governance

These principles apply to both public and internal APIs. Weekly wiki lint review identifies endpoints that drift from the standard.

## See also

- [[API Versioning]]
- [[HTTP Error Format]]
- [[OAuth2 Bearer Tokens]]
- [[Pagination]]
