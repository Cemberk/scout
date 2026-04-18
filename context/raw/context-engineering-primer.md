---
title: "Context Engineering Primer"
source: local
fetched_at: 2026-04-18
tags: [context-engineering, rag, agents, primer]
type: primer
---

# Context Engineering Primer

Context engineering is the practice of shaping what an agent knows at the
moment of decision. It is the umbrella discipline that contains prompt
engineering, retrieval engineering, tool design, and memory design.

## The four levers

1. **What's in the context window right now** — system prompt, current
   turn, scratchpad, and any hydrated knowledge.
2. **What's reachable on demand** — tools, retrieval over wikis and
   document corpora, structured queries.
3. **What persists across turns** — short-term state, long-term memory,
   learned preferences and corrections.
4. **What's redacted or gated** — access control, secret stripping, and
   refusal paths for out-of-scope reads.

## Why the wiki-first pattern wins

Raw inputs are noisy. Agents that read raw repeatedly pay a tax on every
turn: format drift, cross-document inconsistency, and secrets leaking
through. The wiki-first pattern compiles raw inputs once into clean,
navigable articles — the agent reads those and only those at runtime.

The Scout repo implements this directly: `context/raw/` is intake (the
Compiler sees it), and `context/compiled/` is the wiki the Navigator
reads. This separation is enforced at the tool layer, not by convention.

## See also

- [ACME Sample Handbook](./sample-handbook.md)
- Scout spec: `tmp/spec.md`
