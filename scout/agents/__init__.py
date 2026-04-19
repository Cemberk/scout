from scout.agents.code_explorer import code_explorer
from scout.agents.compiler import compiler
from scout.agents.doctor import doctor
from scout.agents.engineer import engineer
from scout.agents.explorer import explorer

# Legacy alias — `from scout.agents import navigator` still resolves during
# the migration. Removed in sub-step 1k when team.py switches to explorer.
navigator = explorer

__all__ = ["explorer", "navigator", "compiler", "code_explorer", "engineer", "doctor"]
