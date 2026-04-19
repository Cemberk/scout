"""
Engineer Cases
==============

Engineer owns SQL writes: picks the right ``scout_*`` table (or creates
one), inserts the user's data, and records any schema change back to
Knowledge.

Eval type: AgentAsJudgeEval (binary)
"""

CRITERIA = (
    "The response must confirm a concrete write — either an INSERT into "
    "one of the shipped tables (scout_contacts / scout_projects / "
    "scout_notes / scout_decisions) or a CREATE TABLE in the scout schema, "
    "plus an update_knowledge call describing the schema. If the user asks "
    "to save a note/fact/contact/decision and the Leader did not route to "
    "Engineer, that fails. Engineer must NEVER write to public.* or ai.*; "
    "if the response describes touching those schemas, that fails."
)

CASES: list[str] = [
    "Save a note titled 'Q3 PRD review' — key points were to defer the mobile rollout and accelerate the API migration.",
    "Add a contact: Priya Patel, emails priya@example.com and p.patel@work.com, phone +1-415-555-0182, tag her 'design-partner'.",
    "Track a new project called 'Mobile Relaunch' — status is planning, tag it 'mobile' and 'q4'.",
    "Record my decision to pick Postgres over SQLite. Rationale: we need write concurrency and the hosted managed option.",
    "Create a new table scout_readings to track articles I've read — title, url, read_at (date), rating (int 1-5), notes.",
]
