---
source: local:raw:api-design-principles.md
source_url: file:///app/context/raw/api-design-principles.md
source_hash: cccf594dc168b69f1232cc804d4924ca6711b089b8eb5c0a900668f3f90cf66a
compiled_at: 2026-04-18T09:27:53Z
compiled_by: scout-compiler-v3
user_edited: false
needs_split: false
tags:
---

# API Design Principles

ACME HTTP APIs use consistent resource-oriented conventions for request shape, error handling, versioning, and authentication. New endpoints must follow these rules, and drift in existing endpoints is reviewed in the weekly wiki lint process and corrected.

## Request and resource shape

- Model resources as nouns; actions belong in the HTTP method.
- Use JSON only with `Content-Type: application/json; charset=utf-8`.
- Use `snake_case` for field names.
- Do not return `null`; omit absent fields instead.
- Paginate all list endpoints with `limit` and `cursor`.
- Do not use offset-based pagination.

## Errors

Use 4xx responses for caller errors and 5xx responses for server errors.

Error bodies use this shape:

```json
{ "error": { "code": "...", "message": "...", "details": {} } }
```

Error codes are stable `UPPER_SNAKE` strings. They are not renumbered.

## Versioning

Breaking changes require a new URL version prefix, such as `/v1/...` to `/v2/...`. Additive changes do not require a version bump.

Deprecated endpoints return `Sunset` headers for 90 days before removal. This defines the deprecation window for clients.

## Authentication

- Internal services use [[mutual-tls]].
- External clients use OAuth2 bearer tokens.
- Basic authentication is not allowed.
- API keys must not be accepted in query strings.
- Credentials are sent in the `Authorization` header only.

## Enforcement

New endpoints must match these conventions. Existing endpoints that drift are flagged in the weekly wiki lint review and fixed.

## See also

- [[http-api-guidelines]]
- [[error-response-format]]
- [[api-versioning]]
- [[oauth2]]
- [[mutual-tls]]
