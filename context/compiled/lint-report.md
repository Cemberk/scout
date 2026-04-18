# Wiki Lint Report

Generated: 2026-04-18T09:25:33Z

## Stale articles

Stale means the file's frontmatter `source_hash` matches the current compile record for its source entry, but the file is **not** the current `wiki_path` recorded in compile records for that entry. These are superseded compiled outputs still present on disk.

- `compiled/articles/api-design-principles-bac3bc04.md` — stale; current record for `api-design-principles.md` points to `compiled/articles/api-design-principles-dcd10767.md` with same `source_hash` `cccf594dc168...`
- `compiled/articles/api-design-principles-c18d1b29.md` — stale; current record for `api-design-principles.md` points to `compiled/articles/api-design-principles-dcd10767.md` with same `source_hash` `cccf594dc168...`
- `compiled/articles/context-engineering-4026abf4.md` — stale; current record for `context-engineering-primer.md` points to `compiled/articles/context-engineering-cc64d35e.md` with same `source_hash` `5f19a85deb79...`
- `compiled/articles/context-engineering-697d8af0.md` — stale; current record for `context-engineering-primer.md` points to `compiled/articles/context-engineering-cc64d35e.md` with same `source_hash` `5f19a85deb79...`
- `compiled/articles/context-engineering-8f87c9bf.md` — stale; current record for `context-engineering-primer.md` points to `compiled/articles/context-engineering-cc64d35e.md` with same `source_hash` `5f19a85deb79...`
- `compiled/articles/company-goals-20271285.md` — stale; current record for `quarterly-goals-q2-2026.md` points to `compiled/articles/company-goals-q2-2026-8ea4c685.md` with same `source_hash` `e5e65fc73f33...`
- `compiled/articles/company-goals-q2-2026-ae271a97.md` — stale; current record for `quarterly-goals-q2-2026.md` points to `compiled/articles/company-goals-q2-2026-8ea4c685.md` with same `source_hash` `e5e65fc73f33...`
- `compiled/articles/new-hire-onboarding-eb9d9c7a.md` — stale; current record for `onboarding-checklist.md` points to `compiled/articles/onboarding-checklist-4b0751b3.md` with same `source_hash` `a5c05e0c3648...`
- `compiled/articles/onboarding-checklist-188ffcd8.md` — stale; current record for `onboarding-checklist.md` points to `compiled/articles/onboarding-checklist-4b0751b3.md` with same `source_hash` `a5c05e0c3648...`
- `compiled/articles/pto-policy-0093959b.md` — stale; current record for `sample-handbook.md` points to `compiled/articles/pto-policy-868bbc00.md` with same `source_hash` `b1864cb0f407...`
- `compiled/articles/security-policy-6b77e628.md` — stale; current record for `security-policy.md` points to `compiled/articles/security-policy-8aaf2cf8.md` with same `source_hash` `658b395dc93c...`
- `compiled/articles/security-policy-8914bc30.md` — stale; current record for `security-policy.md` points to `compiled/articles/security-policy-8aaf2cf8.md` with same `source_hash` `658b395dc93c...`
- `compiled/articles/source-manifest-5a914bef.md` — stale; current record for `.manifest.json` points to `compiled/articles/source-manifest-55eb35fe.md` with same `source_hash` `37517e5f3dc6...`
- `compiled/articles/team-directory-975ef17c.md` — stale; current record for `team-directory.md` points to `compiled/articles/team-directory-35bcddf9.md` with same `source_hash` `8ee35a7f216e...`
- `compiled/articles/team-directory-a7a58747.md` — stale; current record for `team-directory.md` points to `compiled/articles/team-directory-35bcddf9.md` with same `source_hash` `8ee35a7f216e...`

## Broken backlinks / internal links

Broken means a `[[wikilink]]` target slug has no corresponding article file slug under `compiled/articles/`.

### Current-record articles
- `compiled/articles/api-design-principles-dcd10767.md`
  - broken: `[[API versioning]]` → no slug `api-versioning`
  - broken: `[[HTTP error model]]` → no slug `http-error-model`
  - broken: `[[OAuth2 authentication]]` → no slug `oauth2-authentication`
  - broken: `[[Pagination]]` → no slug `pagination`
- `compiled/articles/context-engineering-cc64d35e.md`
  - broken: `[[Context engineering]]` → no slug `context-engineering` exact page slug exists only as hashed file title variant; no separate target article
  - broken: `[[prompt-engineering]]`
  - broken: `[[retrieval-engineering]]`
  - broken: `[[tool-design]]`
  - broken: `[[memory-design]]`
- `compiled/articles/source-manifest-55eb35fe.md`
  - broken: `[[raw-document]]`
  - broken: `[[source-ingestion]]`
  - broken: `[[document-manifest]]`
- `compiled/articles/onboarding-checklist-4b0751b3.md`
  - broken: `[[employee-handbook]]`
  - broken: `[[runbooks]]`
  - broken: `[[onboarding-buddy]]`
- `compiled/articles/company-goals-q2-2026-8ea4c685.md`
  - broken: `[[Scout v3]]`
  - broken: `[[Onboarding process]]`
  - broken: `[[Bug reduction]]`
  - broken: `[[Engineering status checks]]`
- `compiled/articles/pto-policy-868bbc00.md`
  - broken: `[[paid-time-off]]`
  - broken: `[[public-holidays]]`
  - broken: `[[contractor-leave]]`
  - broken: `[[Workday]]`
  - broken: `[[parental-leave]]`
- `compiled/articles/security-policy-8aaf2cf8.md`
  - broken: `[[agent-safety]]`
  - broken: `[[credential-management]]`
  - broken: `[[data-handling]]`
  - broken: `[[incident-response]]`
- `compiled/articles/team-directory-35bcddf9.md`
  - broken: `[[engineering-teams]]`
  - broken: `[[leadership-team]]`
  - broken: `[[office-locations]]`
  - broken: `[[internal-channels]]`

### Additional broken links found in stale articles still on disk
These stale files can still pollute navigation/search if exposed:
- `compiled/articles/new-hire-onboarding-eb9d9c7a.md`: `[[security-training]]`, `[[developer-environment-setup]]`, `[[employee-handbook]]`, `[[onboarding-buddy]]`
- `compiled/articles/onboarding-checklist-188ffcd8.md`: `[[1password]]`, `[[employee-handbook]]`, `[[security-training]]`, `[[onboarding-buddy]]`
- `compiled/articles/company-goals-20271285.md`: `[[Scout v3]]`, `[[Onboarding]]`, `[[Bug reduction]]`, `[[#eng-status]]`
- `compiled/articles/company-goals-q2-2026-ae271a97.md`: `[[Scout v3]]`, `[[Onboarding]]`, `[[Incident Postmortem]]`, `[[API Contract Tests]]`
- `compiled/articles/api-design-principles-bac3bc04.md`: `[[HTTP API versioning]]`, `[[API error format]]`, `[[OAuth2 bearer tokens]]`, `[[Cursor pagination]]`
- `compiled/articles/security-policy-8914bc30.md`: `[[credential-management]]`, `[[data-handling]]`, `[[security-incidents]]`, `[[agent-safety]]`
- `compiled/articles/security-policy-6b77e628.md`: `[[credential-management]]`, `[[personally-identifiable-information]]`, `[[security-incidents]]`, `[[agent-safety]]`
- `compiled/articles/team-directory-975ef17c.md`: `[[engineering-team]]`, `[[operations-team]]`, `[[leadership-team]]`, `[[office-locations]]`
- `compiled/articles/team-directory-a7a58747.md`: `[[Engineering teams]]`, `[[Operations teams]]`, `[[Leadership team]]`, `[[Office locations]]`
- `compiled/articles/source-manifest-5a914bef.md`: `[[source-ingestion]]`, `[[document-manifest]]`, `[[raw-source]]`

## Recommended fixes

### Critical
1. **Hide or exclude stale compiled files from wiki navigation/search immediately.** There are many superseded articles on disk with valid-looking frontmatter and broken links. If your reader indexes all `compiled/articles/*.md`, users can land on obsolete pages.
2. **Normalize wikilink generation to actual compiled slugs/titles.** Current articles frequently link to conceptual pages that do not exist. This is the main source of broken backlinks.

### High
3. **Re-run compile after tightening link resolution rules** so `See also` sections only emit links when a target article actually exists, otherwise render plain text.
4. **Add a lint gate**: fail compile/lint when an article introduces unresolved `[[wikilink]]` targets in current-record articles.

### Medium
5. **Choose a single canonical slug per source entry and suppress historical siblings from discovery.** The current runner leaves many old siblings that appear stale even when source content is unchanged.
6. **Create missing target pages for repeated concepts** if they are intended as first-class wiki nodes, especially: `agent-safety`, `employee-handbook`, `onboarding-buddy`, `prompt-engineering`, `retrieval-engineering`, `tool-design`, `memory-design`.

### Low
7. **Review self-link behavior** for `[[Context engineering]]`; either resolve self-links correctly to the current article slug or avoid self-links.