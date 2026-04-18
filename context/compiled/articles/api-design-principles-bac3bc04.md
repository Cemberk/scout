---
source: local:raw:api-design-principles.md
source_url: file:///app/context/raw/api-design-principles.md
source_hash: cccf594dc168b69f1232cc804d4924ca6711b089b8eb5c0a900668f3f90cf66a
compiled_at: 2026-04-18T07:11:30Z
compiled_by: scout-compiler-v3
user_edited: false
needs_split: false
tags:
backlinks:
---

# API design principles

ACME public and internal HTTP APIs must follow these conventions. New endpoints must comply; existing drift is flagged in the weekly wiki lint review and fixed.

## Shape

- Use nouns for resources; actions belong in the HTTP method.
- Return JSON only with `Content-Type: application/json; charset=utf-8`.
- Use `snake_case` field names.
- Do not return `null`; omit the key instead.
- Paginate all list endpoints with `limit` and `cursor`. Never use offset pagination.

## Errors

- Use 4xx for caller errors and 5xx for server errors.
- Error body format:
  ```json
  { "error": { "code": "...", "message": "...", "details": {} } }
  ```
- Error codes are stable `UPPER_SNAKE` strings. Never renumber them.

## Versioning

- Breaking changes require a new URL prefix, for example `/v1/...` to `/v2/...`.
- Additive changes do not change the version.
- Deprecated endpoints must return `Sunset:` headers for 90 days before removal.

## Auth

- Internal services use mTLS.
- External clients use OAuth2 bearer tokens.
- Do not use basic auth.
- Accept credentials only in the `Authorization` header. Never accept API keys in query strings.

## See also

- [[HTTP API versioning]]
- [[API error format]]
- [[OAuth2 bearer tokens]]
- [[Cursor pagination]]
