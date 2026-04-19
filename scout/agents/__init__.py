from scout.agents.code_explorer import code_explorer
from scout.agents.compiler import compiler
from scout.agents.doctor import doctor
from scout.agents.engineer import engineer
from scout.agents.explorer import explorer

# Legacy alias — `from scout.agents import navigator` still resolves during
# the migration. Removed when app/main.py drops the legacy agent list in 1m.
navigator = explorer

__all__ = ["explorer", "navigator", "engineer", "doctor", "compiler", "code_explorer"]
