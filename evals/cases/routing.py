"""
Routing Cases
=============

Leader delegates to the right specialist and triggers the right tools.
Eval type: ReliabilityEval (expected tool calls)
"""

CASES: list[dict] = [
    # Navigator — SQL
    {
        "input": "Save a note: Met with the security team about the Q4 audit",
        "expected_tools": ["run_sql_query"],
    },
    {"input": "What notes do I have about Project Atlas?", "expected_tools": ["run_sql_query"]},
    # Navigator — Files (enterprise documents)
    {"input": "What's our PTO policy?", "expected_tools": ["read_file"]},
    {"input": "What voice guides do we have?", "expected_tools": ["list_files"]},
    # Navigator — Wiki
    {"input": "What does our knowledge base say about context engineering?", "expected_tools": ["read_wiki_index"]},
    # Navigator — Exa (web search fallback when Researcher not configured)
    {"input": "Research the latest trends in AI agent frameworks", "expected_tools": ["web_search_exa"]},
    # Researcher — Ingest (requires PARALLEL_API_KEY; skipped when Researcher not configured)
    {"input": "Ingest this article: https://example.com/article-on-rag", "expected_tools": ["ingest_url"]},
    # Compiler
    {"input": "Compile any new sources into the wiki", "expected_tools": ["read_manifest"]},
    # Syncer
    {"input": "What's the sync status?", "expected_tools": ["sync_status"]},
    {"input": "Push the latest changes to GitHub", "expected_tools": ["sync_push"]},
]
