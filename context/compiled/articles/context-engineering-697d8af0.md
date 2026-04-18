---
source: local:raw:context-engineering-primer.md
source_url: file:///app/context/raw/context-engineering-primer.md
source_hash: 5f19a85deb79d7595d38e55eeb047480d526ac135eb5a73ef630dd36a732f45b
compiled_at: 2026-04-18T07:40:22Z
compiled_by: scout-compiler-v3
user_edited: false
needs_split: true
tags:
backlinks:
---

# Context engineering

Context engineering is the practice of shaping what an agent knows at the moment of decision. It includes [[prompt-engineering]], [[retrieval-engineering]], [[tool-design]], and [[memory-design]].

## Core levers

Context engineering operates through four levers:

1. What is in the context window now, including the system prompt, current turn, scratchpad, and hydrated knowledge.
2. What is reachable on demand, including tools, retrieval over wikis and document corpora, and structured queries.
3. What persists across turns, including short-term state, long-term memory, and learned preferences or corrections.
4. What is redacted or gated, including access control, secret stripping, and refusal paths for out-of-scope reads.

## Wiki-first pattern

A wiki-first pattern compiles raw inputs once into clean, navigable articles, then serves those compiled articles to the agent at runtime. This avoids repeated reading of noisy raw sources and reduces format drift, cross-document inconsistency, and accidental secret exposure.

In Scout, `context/raw/` is the intake layer processed by the Compiler, and `context/compiled/` is the wiki read by the Navigator. The separation is enforced by tools rather than left to convention.

## See also

- [[prompt-engineering]]
- [[retrieval-engineering]]
- [[tool-design]]
- [[memory-design]]
