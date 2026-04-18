---
source: local:raw:api-design-principles.md
source_url: file:///app/context/raw/api-design-principles.md
source_hash: cccf594dc168b69f1232cc804d4924ca6711b089b8eb5c0a900668f3f90cf66a
compiled_at: 2026-04-18T08:08:55Z
compiled_by: scout-compiler-v3
user_edited: false
needs_split: false
tags:
backlinks:
---

# API Design Principles

ACME HTTP APIs use consistent conventions for resource shape, errors, versioning, and authentication. New endpoints must follow these rules, and existing endpoints that drift are corrected through weekly wiki lint review.

## Resource shape

- Model resources as nouns; actions belong in the HTTP method.
- Use JSON only.
- Send `Content-Type: application/json; charset=utf-8`.
- Use `snake_case` for field names.
- Do not return `null`; omit absent fields instead.

## Pagination

All list endpoints are paginated. Use `limit` and `cursor`, never offset-based pagination.

## Errors

Use 4xx responses for caller mistakes and 5xx responses for server failures.

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

Error codes are stable `UPPER_SNAKE` strings. They are not renumbered.

## Versioning

Breaking changes require a new URL version prefix, such as `/v1/...` to `/v2/...`. Additive changes do not require a version bump.

Deprecated endpoints must return a `Sunset` header for 90 days before removal.

## Authentication

- Internal services use mTLS.
- External clients use OAuth2 bearer tokens.
- Do not use basic auth.
- Do not accept API keys in query strings.
- Send credentials in the `Authorization` header only.

## Enforcement

New endpoints must match these principles. Existing endpoints that diverge are flagged in weekly wiki lint review and fixed.

## See also

- [[API versioning]]
- [[HTTP error model]]
- [[OAuth2 authentication]]
- [[Pagination]]
