---
source: local:raw:context-engineering-primer.md
source_url: file:///app/context/raw/context-engineering-primer.md
source_hash: 5f19a85deb79d7595d38e55eeb047480d526ac135eb5a73ef630dd36a732f45b
compiled_at: 2026-04-18T07:54:54Z
compiled_by: scout-compiler-v3
user_edited: false
needs_split: true
tags:
backlinks:
---

# Context engineering

[[Context engineering]] is the practice of shaping what an agent knows at the moment of decision. It includes [[prompt-engineering]], [[retrieval-engineering]], [[tool-design]], and [[memory-design]].

## Core levers

Context engineering works through four main levers:

1. What is in the context window now, including the system prompt, current turn, scratchpad, and any hydrated knowledge.
2. What is reachable on demand, including tools, retrieval over wikis and document corpora, and structured queries.
3. What persists across turns, including short-term state, long-term memory, and learned preferences or corrections.
4. What is redacted or gated, including access control, secret stripping, and refusal paths for out-of-scope reads.

## Runtime context

The immediate context window determines what the agent can directly reason over in the current step. This includes instructions, active conversation state, and any material explicitly inserted before the model produces an answer.

## Reachability

Not all useful knowledge needs to be preloaded. Tools and retrieval systems extend the agent's effective knowledge by making relevant information reachable when needed.

## Persistence

Some information should survive beyond a single turn. This includes conversational state, durable memory, and user-specific preferences that affect future decisions.

## Gating

Context engineering also controls what the agent must not see or use. Redaction, permission boundaries, and refusal behavior are part of the design, not afterthoughts.

## See also

- [[prompt-engineering]]
- [[retrieval-engineering]]
- [[tool-design]]
- [[memory-design]]
