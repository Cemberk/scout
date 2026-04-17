"""
Wiki Cases
==========

Agent uses the v3 wiki tools: reads the manifest, finds + reads articles
through the source dispatch, triggers compilation. The legacy
read_wiki_index/read_wiki_state tools are gone — wiki access is uniform
through source_*.

Eval type: ReliabilityEval (expected tool calls)
"""

CASES: list[dict] = [
    {"input": "What's in the wiki right now?", "expected_tools": ["source_list"]},
    {"input": "What sources are reachable for me?", "expected_tools": ["read_manifest"]},
    {"input": "Find anything in the wiki about PTO", "expected_tools": ["source_find"]},
    {"input": "Compile any new sources into the wiki", "expected_tools": ["compile_all_sources"]},
    {"input": "Run a health check on the wiki", "expected_tools": ["read_manifest"]},
    {"input": "Are there any compile sources I can iterate?", "expected_tools": ["list_compile_sources"]},
]
