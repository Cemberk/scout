"""Tool assembly — per-agent tool lists + Leader tools.

- Navigator: source dispatch (manifest-gated), SQL (READ-ONLY), files (read),
  Parallel/Exa web search, Gmail/Calendar (conditional on Google integration).
  Navigator does NOT get a FileTools pointed at CONTEXT_RAW_DIR — `local:raw`
  is compile-only and the Manifest refuses `source_read` on it from any
  non-Compiler role.
- Compiler: compile dispatch + raw-source read + voice-guide reads + ingest
  tools (URL/text → raw/). Ingest is the entry point to the compile
  pipeline; the Compiler decides when (or whether) to follow up with a
  compile pass. Post-compile lint responsibilities (broken backlinks,
  stale articles, `needs_split`, user-edit conflicts) are bundled into
  the Compiler's instructions — no separate Linter agent.
- Leader: SlackTools (conditional on SLACK_BOT_TOKEN).
"""

from __future__ import annotations

from agno.knowledge import Knowledge
from agno.tools.file import FileTools
from agno.tools.sql import SQLTools

# ParallelTools / MCPTools are imported lazily inside the builders —
# ParallelTools pulls in the optional `parallel-web` package, and
# MCPTools opens a network handshake we don't want on import.
from db import SCOUT_SCHEMA, db_url, get_readonly_engine, get_sql_engine
from scout.settings import (
    CONTEXT_DIR,
    CONTEXT_RAW_DIR,
    EXA_MCP_URL,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_PROJECT_ID,
    PARALLEL_API_KEY,
)
from scout.tools.compile_tools import create_compile_tools
from scout.tools.ingest import create_ingest_tools
from scout.tools.introspect import create_introspect_schema_tool
from scout.tools.knowledge import create_update_knowledge
from scout.tools.manifest_tools import create_manifest_tool
from scout.tools.sources import create_source_tools

_GOOGLE_READY = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_PROJECT_ID)


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
    """Tools for the Navigator — SQL (READ-ONLY), context files (read-only),
    source dispatch, web search, plus Gmail/Calendar (if Google configured).

    Navigator is the read-only specialist. Its SQLTools is bound to
    ``get_readonly_engine()`` so any INSERT/UPDATE/DELETE/DDL is rejected
    at the PostgreSQL level — instruction-based constraints are backed by
    database-level enforcement. Its FileTools is read-only for the same
    reason: spec §9 governance says Navigator does not write compiled
    articles, does not hand-edit context files, and does not delete files.
    Writes land with the Compiler (context/) or Engineer (SQL); Navigator
    refuses them with no tool call rather than silently editing.
    """
    tools: list = [
        SQLTools(db_engine=get_readonly_engine(), schema=SCOUT_SCHEMA),
        FileTools(
            base_dir=CONTEXT_DIR,
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

    if _GOOGLE_READY:
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


def build_compiler_tools(knowledge: Knowledge) -> list:
    """Tools for the Compiler — compile dispatch + raw-source read + voice
    reads + URL/text ingest.

    The Compiler owns every write path for the wiki: it ingests raw inputs
    (``ingest_url`` / ``ingest_text`` → ``context/raw/``), compiles them
    into ``context/compiled/``, and runs lint checks (broken backlinks,
    stale articles, ``needs_split`` surfacing, user-edit conflicts) at
    the end of every compile pass.

    Ingest does NOT auto-trigger compile — the Compiler decides, usually
    on an explicit "compile now" request from the user.
    """
    ingest_url, ingest_text, _read_manifest_legacy, _update_manifest_legacy = create_ingest_tools(CONTEXT_RAW_DIR)
    return [
        FileTools(base_dir=CONTEXT_DIR, enable_delete_file=False),
        create_update_knowledge(knowledge),
        create_manifest_tool("compiler"),
        *create_source_tools("compiler"),
        *create_compile_tools(knowledge),
        ingest_url,
        ingest_text,
    ]


def build_doctor_tools() -> list:
    """Tools for the Doctor — diagnostic + self-heal helpers + read-only SQL.

    The Doctor never modifies user content. Its SQL is bound to
    ``get_readonly_engine()`` so even malformed queries can't mutate
    ``scout_sources`` / ``scout_compiled``. It can delete files under
    ``REPOS_DIR`` (the CodeExplorer clone cache) via ``clear_repo_cache``
    — that tool internally refuses paths that resolve outside
    ``REPOS_DIR``.
    """
    from scout.tools.diagnostics import (
        clear_repo_cache,
        env_report,
        health_ping,
        reload_manifest_tool,
        retrigger_compile,
    )

    # Doctor reads setup guides (``docs/GOOGLE_AUTH.md`` /
    # ``docs/SLACK_CONNECT.md``) when suggesting fixes. Scope FileTools
    # tightly to ``docs/`` — NOT the repo root — so prompt-injected
    # content can't trick the Doctor into reading ``.env`` or anything
    # else in the bind-mounted work-tree.
    docs_dir = (CONTEXT_DIR / ".." / "docs").resolve()

    return [
        SQLTools(db_engine=get_readonly_engine(), schema=SCOUT_SCHEMA),
        FileTools(
            base_dir=docs_dir,
            enable_save_file=False,
            enable_read_file=True,
            enable_list_files=True,
            enable_search_files=True,
            enable_delete_file=False,
        ),
        create_manifest_tool("doctor"),
        reload_manifest_tool,
        health_ping,
        retrigger_compile,
        clear_repo_cache,
        env_report,
    ]


def build_engineer_tools(knowledge: Knowledge) -> list:
    """Tools for the Engineer — DDL + DML on ``scout``, schema introspection,
    Knowledge writes.

    The Engineer's SQLTools is bound to ``get_sql_engine()`` so it can
    CREATE / ALTER / INSERT / UPDATE / DELETE — but the session-level
    write guard rejects any statement that targets ``public`` or ``ai``.
    ReasoningTools is included because DDL work benefits from explicit
    plan → introspect → act → verify steps.
    """
    from agno.tools.reasoning import ReasoningTools

    return [
        SQLTools(db_engine=get_sql_engine(), schema=SCOUT_SCHEMA),
        create_introspect_schema_tool(db_url, engine=get_sql_engine()),
        create_update_knowledge(knowledge),
        ReasoningTools(),
    ]


def build_leader_tools() -> list:
    """Leader tools — outbound communication (Slack / Gmail / Calendar) +
    voice-guide reads + read-only contact lookup SQL.

    Gmail and Calendar are wired as drafts-only via ``exclude_tools=[...]``
    so send functions never reach the model. Slack posting is send-capable
    when a token is present — Slack's Scout integration is explicitly
    opt-in and the user already consented by setting ``SLACK_BOT_TOKEN``.

    FileTools is read-only on ``CONTEXT_VOICE_DIR`` so the Leader reads
    the matching voice guide (``voice/email.md``, ``voice/slack-message.md``,
    etc.) before drafting any outbound content.

    SQLTools uses ``get_readonly_engine()`` scoped to the ``scout``
    schema so the Leader can resolve a recipient name against
    ``scout_contacts`` without being able to write.
    """
    from scout.settings import CONTEXT_VOICE_DIR, SLACK_BOT_TOKEN

    tools: list = [
        FileTools(
            base_dir=CONTEXT_VOICE_DIR,
            enable_save_file=False,
            enable_read_file=True,
            enable_list_files=True,
            enable_search_files=True,
            enable_delete_file=False,
        ),
        SQLTools(db_engine=get_readonly_engine(), schema=SCOUT_SCHEMA),
    ]

    if SLACK_BOT_TOKEN:
        from agno.tools.slack import SlackTools

        tools.append(
            SlackTools(
                token=SLACK_BOT_TOKEN,
                enable_send_message=True,
                enable_list_channels=True,
                enable_send_message_thread=True,
                enable_get_channel_history=False,
                enable_upload_file=False,
                enable_download_file=False,
            )
        )

    if _GOOGLE_READY:
        # Drafts-only: strip send functions so they never reach the model.
        # The Leader drafts; the user approves and sends.
        from agno.tools.gmail import GmailTools  # type: ignore[import-not-found]
        from agno.tools.googlecalendar import GoogleCalendarTools  # type: ignore[import-not-found]

        tools.append(GmailTools(exclude_tools=["send_email", "send_email_reply"]))
        tools.append(
            GoogleCalendarTools(
                allow_update=False,
                exclude_tools=["create_event", "update_event", "delete_event"],
            )
        )

    return tools
