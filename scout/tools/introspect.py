"""Runtime schema inspection for the Engineer.

Scout's Engineer writes only to the ``scout`` schema. The ``public``
schema is included for *read-only* introspection so the Engineer can
see any company-loaded tables that already exist and reference them
(never mutate them — the session-level write guard blocks that anyway).
"""

from agno.tools import tool
from agno.utils.log import logger
from sqlalchemy import Engine, inspect
from sqlalchemy.exc import DatabaseError, OperationalError

from db.session import SCOUT_SCHEMA

SCHEMAS = ["public", SCOUT_SCHEMA]


def create_introspect_schema_tool(engine: Engine):
    """Create an introspect_schema tool bound to a SQLAlchemy engine."""
    _engine = engine

    @tool
    def introspect_schema(table_name: str | None = None, schema: str | None = None) -> str:
        """Inspect database schema at runtime.

        Args:
            table_name: Table to inspect. If None, lists all tables.
            schema: Filter to a specific schema ("public" or "scout"). If None, shows both.
        """
        try:
            insp = inspect(_engine)
            schemas = [schema] if schema and schema in SCHEMAS else SCHEMAS

            if table_name is None:
                lines: list[str] = []
                for s in schemas:
                    tables = sorted(insp.get_table_names(schema=s))
                    label = "company data — read only" if s == "public" else "agent-managed"
                    lines.append(f"## {s} ({label})")
                    lines.append("")
                    if not tables:
                        lines.append("_(empty)_")
                    else:
                        for t in tables:
                            lines.append(f"- **{s}.{t}**")
                    lines.append("")
                return "\n".join(lines)

            # Find which schema it's in
            found_schema = next((s for s in schemas if table_name in insp.get_table_names(schema=s)), None)
            if found_schema is None:
                available = [f"{s}.{t}" for s in schemas for t in insp.get_table_names(schema=s)]
                return f"Table '{table_name}' not found. Available: {', '.join(sorted(available))}"

            label = "company data" if found_schema == "public" else "agent-managed"
            lines = [f"## {found_schema}.{table_name} ({label})", ""]

            cols = insp.get_columns(table_name, schema=found_schema)
            if cols:
                lines.extend(["### Columns", "", "| Column | Type | Nullable |", "| --- | --- | --- |"])
                for c in cols:
                    nullable = "Yes" if c.get("nullable", True) else "No"
                    lines.append(f"| {c['name']} | {c['type']} | {nullable} |")
                lines.append("")

            pk = insp.get_pk_constraint(table_name, schema=found_schema)
            if pk and pk.get("constrained_columns"):
                lines.append(f"**Primary Key:** {', '.join(pk['constrained_columns'])}")

            return "\n".join(lines)

        except OperationalError as e:
            logger.error(f"Database connection failed: {e}")
            return "Error: Database connection failed. Check that the database is running."
        except DatabaseError as e:
            logger.error(f"Database error: {e}")
            return "Error: A database error occurred. Check logs for details."

    return introspect_schema
