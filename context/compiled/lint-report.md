# Wiki Lint Report

Generated: 2026-04-19T11:04:32Z

## Stale articles

### `compiled/articles/scout-adoption-plan-1aafe84e.md`
- **Title:** Scout Adoption Plan
- **Source entry:** `local:raw/offsite-notes.md`
- **Why flagged:** Compiled article frontmatter `compiled_at` is `2026-04-18T18:35:08Z`, but compile record for the same source entry shows a later successful compile at `2026-04-18T18:35:37.441214+00:00`. The on-disk article appears older than the current compile state even though `source_hash` matches.
- **Remediation:** Re-run compile for `offsite-notes.md` and verify the article written to disk matches the latest compile record.

## Broken backlinks

### `compiled/articles/team-directory-753d470f.md`
- **Title:** Team Directory
- **Broken wikilinks:** `[[engineering]]`, `[[operations]]`, `[[leadership]]`, `[[office-locations]]`
- **Why flagged:** No compiled article slug exists for any of these backlink targets.
- **Remediation:** Either compile/create articles for these topics, or replace/remove the wikilinks if they are not intended wiki pages.

### `compiled/articles/scout-adoption-plan-1aafe84e.md`
- **Title:** Scout Adoption Plan
- **Broken wikilinks:** `[[scout-wiki]]`, `[[scout-sources]]`, `[[scout-operations]]`, `[[scout-security]]`
- **Why flagged:** No compiled article slug exists for any of these backlink targets.
- **Remediation:** Add compiled articles for these concepts or update the links to point at existing article slugs.

### `compiled/articles/article-on-rag-4c445d34.md`
- **Title:** Article on RAG
- **Broken wikilinks:** `[[knowledge-base]]`, `[[source-ingestion]]`, `[[document-compilation]]`
- **Why flagged:** No compiled article slug exists for any of these backlink targets.
- **Remediation:** Create the referenced wiki pages or remove the placeholder backlinks until supporting articles exist.

### `compiled/articles/pto-policy-aae2699b.md`
- **Title:** PTO Policy
- **Broken wikilinks:** `[[public-holidays]]`, `[[contractor-leave]]`, `[[workday]]`
- **Why flagged:** No compiled article slug exists for any of these backlink targets.
- **Remediation:** Create/compile articles for those referenced topics, or convert these to plain text if they are not separate wiki pages.