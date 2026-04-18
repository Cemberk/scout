---
title: "ACME API Design Principles"
source: local
fetched_at: 2026-04-18
tags: [engineering, api, design, principles]
type: engineering
---

# API Design Principles

Our public and internal HTTP APIs follow the conventions below. New
endpoints must match; existing endpoints that drift are flagged in the
weekly wiki lint review and fixed.

## Shape

- Resources are nouns; verbs live in the HTTP method.
- JSON only. `Content-Type: application/json; charset=utf-8`.
- `snake_case` field names. No nulls — omit the key instead.
- All list endpoints are paginated with `limit` and `cursor`; never
  offset.

## Errors

- 4xx for caller mistakes, 5xx for server problems.
- Body: `{ "error": { "code": "...", "message": "...", "details": {} } }`.
- Codes are stable `UPPER_SNAKE` strings — never renumber.

## Versioning

- Breaking changes bump the URL prefix (`/v1/...` → `/v2/...`).
- Additive changes do not bump the version.
- Deprecated endpoints return `Sunset:` headers for 90 days before
  removal.

## Auth

- Internal services use mTLS.
- External clients use OAuth2 bearer tokens; never basic auth.
- Never accept API keys in query strings — Authorization header only.
