"""Tool assembly — per-agent tool lists + Leader tools.

- Navigator: source dispatch (manifest-gated), SQL, files, Parallel web
  search, Gmail/Calendar (conditional). Navigator does NOT get a FileTools
  pointed at SCOUT_RAW_DIR — `local:raw` is compile-only and the Manifest
  refuses `source_read` on it from any non-Compiler role.
- Researcher: Parallel search + extract, ingest tools writing to raw/.
- Compiler: compile dispatch + raw-source read + voice-guide reads.
  Handles lint responsibilities at the end of every compile pass.
- Leader: SlackTools (conditional on SLACK_TOKEN).
"""

from __future__ import annotations

from agno.knowledge import Knowledge
from agno.tools.file import FileTools
from agno.tools.sql import SQLTools

# ParallelTools / MCPTools are imported lazily inside the builders —
# ParallelTools pulls in the optional `parallel-web` package, and
# MCPTools opens a network handshake we don't want on import.
from db import SCOUT_SCHEMA, get_sql_engine
from scout.config import (
    EXA_MCP_URL,
    GOOGLE_INTEGRATION_ENABLED,
    PARALLEL_API_KEY,
    SCOUT_CONTEXT_DIR,
    SCOUT_RAW_DIR,
)
from scout.tools.compile_tools import create_compile_tools
from scout.tools.ingest import create_ingest_tools
from scout.tools.knowledge import create_update_knowledge
from scout.tools.manifest_tools import create_manifest_tool
from scout.tools.sources import create_source_tools


def _web_search_tools() -> list:
    """Web search backend selection.

    Parallel is the premium path (better extraction, higher rate limits)
    when PARALLEL_API_KEY is set. Otherwise we fall back to Exa's public
    MCP endpoint, which works keyless — this is what lets a freshly-cloned
    Scout with only OPENAI_API_KEY answer "tell me about X" questions.
    """
    if PARALLEL_API_KEY:
        from agno.tools.parallel import ParallelTools  # lazy — optional dep

        return [ParallelTools()]

    from agno.tools.mcp import MCPTools  # lazy — opens network on init

    return [MCPTools(url=EXA_MCP_URL)]


def build_navigator_tools(knowledge: Knowledge) -> list:
    """Tools for the Navigator — SQL, context files (READ-ONLY), source
    dispatch, plus Parallel (if configured) and Gmail/Calendar (if
    Google configured).

    Navigator's FileTools is read-only on purpose: spec §9 governance
    says Navigator does not write compiled articles or voice guides
    (that's the Compiler's exclusive domain), does not hand-edit any
    context file, and does not delete files. Writes/overwrites/deletes
    on `context/` paths are the refusal path — Navigator refuses with
    no tool call rather than silently editing.
    """
    tools: list = [
        SQLTools(db_engine=get_sql_engine(), schema=SCOUT_SCHEMA),
        FileTools(
            base_dir=SCOUT_CONTEXT_DIR,
            enable_save_file=False,
            enable_read_file=True,
            enable_list_files=True,
            enable_search_files=True,
            enable_delete_file=False,
        ),
        create_update_knowledge(knowledge),
        create_manifest_tool("navigator"),
        *create_source_tools("navigator"),
        *_web_search_tools(),
    ]

    if GOOGLE_INTEGRATION_ENABLED:
        # Spec §9 governance: Gmail read-only + drafts, Calendar read-only.
        # Agno's Toolkit `exclude_tools=[...]` strips tool functions before
        # they reach the model.
        from agno.tools.gmail import GmailTools  # type: ignore[import-not-found]
        from agno.tools.googlecalendar import GoogleCalendarTools  # type: ignore[import-not-found]

        tools.append(GmailTools(exclude_tools=["send_email", "send_email_reply"]))
        tools.append(
            GoogleCalendarTools(
                # allow_update=False keeps the OAuth scope read-only, so
                # even if a tool slips through it will fail at API time.
                allow_update=False,
                exclude_tools=["create_event", "update_event", "delete_event"],
            )
        )

    return tools


def build_researcher_tools(knowledge: Knowledge) -> list:
    """Tools for the Researcher — web search/extract + ingest to context/raw/.

    Uses Parallel if PARALLEL_API_KEY is set, Exa MCP otherwise. The
    Researcher is always instantiated; the backend choice is transparent
    to its instructions.
    """
    ingest_url, ingest_text, _read_manifest_legacy, _ = create_ingest_tools(SCOUT_RAW_DIR)
    return [
        FileTools(base_dir=SCOUT_CONTEXT_DIR, enable_delete_file=False),
        *_web_search_tools(),
        create_update_knowledge(knowledge),
        ingest_url,
        ingest_text,
        create_manifest_tool("researcher"),
        *create_source_tools("researcher"),
    ]


def build_compiler_tools(knowledge: Knowledge) -> list:
    """Tools for the Compiler — compile dispatch + raw-source read + voice reads.

    Post-compile lint responsibilities (broken backlinks, stale articles,
    `needs_split` surfacing, user-edit conflicts) are bundled into the
    Compiler's instructions — no separate Linter agent.
    """
    return [
        FileTools(base_dir=SCOUT_CONTEXT_DIR, enable_delete_file=False),
        create_update_knowledge(knowledge),
        create_manifest_tool("compiler"),
        *create_source_tools("compiler"),
        *create_compile_tools(knowledge),
    ]


def build_leader_tools() -> list:
    """Leader tools — Slack posting only (conditional on SLACK_TOKEN)."""
    from scout.config import SLACK_TOKEN

    if not SLACK_TOKEN:
        return []

    from agno.tools.slack import SlackTools

    return [
        SlackTools(
            enable_send_message=True,
            enable_list_channels=True,
            enable_send_message_thread=True,
            enable_get_channel_history=False,
            enable_upload_file=False,
            enable_download_file=False,
        ),
    ]
