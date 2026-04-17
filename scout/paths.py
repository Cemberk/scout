from os import getenv
from pathlib import Path

CONTEXT_DIR = Path(__file__).parent.parent / "context"
DOCUMENTS_DIR = Path(getenv("DOCUMENTS_DIR", str(Path(__file__).parent.parent / "documents")))

# v3 layout — raw is user-writable intake, compiled is the agent-writable wiki
CONTEXT_RAW_DIR = CONTEXT_DIR / "raw"
CONTEXT_COMPILED_DIR = CONTEXT_DIR / "compiled"
CONTEXT_VOICE_DIR = CONTEXT_DIR / "voice"
