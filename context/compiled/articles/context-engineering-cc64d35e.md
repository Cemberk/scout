---
source: local:raw:context-engineering-primer.md
source_url: file:///app/context/raw/context-engineering-primer.md
source_hash: 5f19a85deb79d7595d38e55eeb047480d526ac135eb5a73ef630dd36a732f45b
compiled_at: 2026-04-18T08:09:03Z
compiled_by: scout-compiler-v3
user_edited: false
needs_split: false
tags:
backlinks:
---

# Context Engineering

[[Context engineering]] is the practice of shaping what an agent knows at the moment of decision. It includes [[prompt-engineering]], [[retrieval-engineering]], [[tool-design]], and [[memory-design]].

## Core levers

Context engineering works through four levers:

1. What is in the context window now: system prompt, current turn, scratchpad, and hydrated knowledge.
2. What is reachable on demand: tools, retrieval over wikis and document corpora, and structured queries.
3. What persists across turns: short-term state, long-term memory, and learned preferences or corrections.
4. What is redacted or gated: access control, secret stripping, and refusal paths for out-of-scope reads.

## Wiki-first pattern

A wiki-first pattern compiles raw inputs once into clean, navigable articles, then serves those compiled articles to the agent at runtime. This avoids repeated costs from noisy raw inputs, including format drift, cross-document inconsistency, and secret leakage.

In Scout, this split is explicit. `context/raw/` is intake for the Compiler, and `context/compiled/` is the wiki read by the Navigator. The separation is enforced at the tool layer rather than by convention.

## See also

- [[prompt-engineering]]
- [[retrieval-engineering]]
- [[tool-design]]
- [[memory-design]]
