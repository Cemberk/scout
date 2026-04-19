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
    # Navigator — Wiki (via source dispatch — read_wiki_index is retired,
    # wiki access is uniform with every other source).
    {"input": "What does our knowledge base say about context engineering?", "expected_tools": ["source_find"]},
    # Navigator — Exa web search (keyless fallback) / Parallel (when configured)
    {"input": "Research the latest trends in AI agent frameworks", "expected_tools": ["web_search_exa"]},
    # Compiler — Ingest (moved from Researcher; Compiler owns raw/ writes)
    {"input": "Ingest this article: https://example.com/article-on-rag", "expected_tools": ["ingest_url"]},
    # Compiler
    {"input": "Compile any new sources into the wiki", "expected_tools": ["read_manifest"]},
    # Engineer — SQL writes (scout_* tables)
    {"input": "Track a new project called 'Mobile Relaunch' — status planning.", "expected_tools": ["run_sql_query"]},
    # Doctor — self-diagnosis
    {"input": "Why isn't Drive showing up as a source?", "expected_tools": ["health_ping"]},
    # CodeExplorer — repo-qualified code questions
    {"input": "In agno-agi/scout, where is the compile pipeline defined?", "expected_tools": ["clone_repo"]},
]
