"""Tool assembly — builds tool lists for each agent role.

Phase 1 wiring:
- Navigator: source-dispatch tools (manifest-gated), Exa, SQL, Gmail/Calendar.
  No direct read of context/raw/. The compiled wiki is reached through
  source_list/source_read on `local:wiki`.
- Compiler: source-dispatch tools (compile-only sources) + compile_tools.
  Gets FileTools too so it can read its voice guide.
- Linter: source-dispatch tools (live-read sources) + lint report writing.
- Researcher: ingest tools + Parallel.
- Syncer: git tools.
"""

from __future__ import annotations

from agno.knowledge import Knowledge
from agno.tools.file import FileTools
from agno.tools.mcp import MCPTools
from agno.tools.parallel import ParallelTools
from agno.tools.sql import SQLTools

from db import SCOUT_SCHEMA, get_sql_engine
from scout.config import (
    DOCUMENTS_DIR,
    EXA_MCP_URL,
    GOOGLE_INTEGRATION_ENABLED,
    SCOUT_COMPILED_DIR,
    SCOUT_CONTEXT_DIR,
    SCOUT_RAW_DIR,
)
from scout.tools.compile_tools import create_compile_tools
from scout.tools.git import create_sync_tools
from scout.tools.ingest import create_ingest_tools
from scout.tools.knowledge import create_update_knowledge
from scout.tools.manifest_tools import create_manifest_tool
from scout.tools.sources import create_source_tools


def build_navigator_tools(knowledge: Knowledge) -> list:
    """Tools for the Navigator agent — uniform source dispatch + classic SQL/email/calendar.

    Crucially: Navigator does NOT get a FileTools pointed at SCOUT_RAW_DIR.
    The Manifest hides `local:raw` from the Navigator role (compile-only),
    so source_read on it returns 'refused'. context/compiled/ is reached
    via source tools rooted at `local:wiki`.
    """
    tools: list = [
        SQLTools(db_engine=get_sql_engine(), schema=SCOUT_SCHEMA),
        FileTools(base_dir=SCOUT_CONTEXT_DIR, enable_delete_file=False),
        FileTools(base_dir=DOCUMENTS_DIR, enable_save_file=False, enable_delete_file=False),
        create_update_knowledge(knowledge),
        MCPTools(url=EXA_MCP_URL),
        create_manifest_tool("navigator"),
        *create_source_tools("navigator"),
    ]

    if GOOGLE_INTEGRATION_ENABLED:
        from agno.tools.google.calendar import GoogleCalendarTools
        from agno.tools.google.gmail import GmailTools

        tools.append(GmailTools(send_email=False, send_email_reply=False, list_labels=True))
        tools.append(GoogleCalendarTools(allow_update=True))

    return tools


def build_researcher_tools(knowledge: Knowledge) -> list:
    """Tools for the Researcher agent — Parallel search/extract + ingest to context/raw/."""
    ingest_url, ingest_text, _read_manifest_legacy, _ = create_ingest_tools(SCOUT_RAW_DIR)
    return [
        FileTools(base_dir=SCOUT_CONTEXT_DIR, enable_delete_file=False),
        ParallelTools(),
        create_update_knowledge(knowledge),
        ingest_url,
        ingest_text,
        create_manifest_tool("researcher"),
        *create_source_tools("researcher"),
    ]


def build_compiler_tools(knowledge: Knowledge) -> list:
    """Tools for the Compiler — compile dispatch + raw-source dispatch + voice file reads."""
    return [
        # Voice guide + index lives under SCOUT_CONTEXT_DIR; deletion off.
        FileTools(base_dir=SCOUT_CONTEXT_DIR, enable_delete_file=False),
        create_update_knowledge(knowledge),
        create_manifest_tool("compiler"),
        *create_source_tools("compiler"),
        *create_compile_tools(knowledge),
    ]


def build_linter_tools(knowledge: Knowledge) -> list:
    """Tools for the Linter — live-read source dispatch + lint reports + Exa for gap research.

    Linter writes its lint reports under context/compiled/ via FileTools.
    """
    return [
        FileTools(base_dir=SCOUT_COMPILED_DIR, enable_delete_file=False),
        FileTools(base_dir=SCOUT_CONTEXT_DIR, enable_delete_file=False),
        MCPTools(url=EXA_MCP_URL),
        create_update_knowledge(knowledge),
        create_manifest_tool("linter"),
        *create_source_tools("linter"),
    ]


def build_syncer_tools() -> list:
    """Tools for the Syncer agent — git commit + push context/, pull remote."""
    return create_sync_tools()


def build_leader_tools() -> list:
    """Tools for the team Leader. Slack only (channel-allowlisted).

    The leader does not call sources directly — it triages and delegates.
    The Slack interface is wired via app/main.py; this is for cases where
    the Leader needs to actively post (scheduled tasks).
    """
    from scout.config import SLACK_CHANNEL_ALLOWLIST, SLACK_TOKEN

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
            channel_allowlist=list(SLACK_CHANNEL_ALLOWLIST) if SLACK_CHANNEL_ALLOWLIST else None,
        )
        if _slack_supports_allowlist()
        else SlackTools(
            enable_send_message=True,
            enable_list_channels=True,
            enable_send_message_thread=True,
            enable_get_channel_history=False,
            enable_upload_file=False,
            enable_download_file=False,
        )
    ]


def _slack_supports_allowlist() -> bool:
    """Return True if installed agno SlackTools accepts a channel_allowlist arg."""
    try:
        import inspect

        from agno.tools.slack import SlackTools

        sig = inspect.signature(SlackTools.__init__)
        return "channel_allowlist" in sig.parameters
    except Exception:
        return False
