from pathlib import Path

CONTEXT_DIR = Path(__file__).parent.parent / "context"

# raw/ is user-writable intake, compiled/ is agent-writable wiki.
CONTEXT_RAW_DIR = CONTEXT_DIR / "raw"
CONTEXT_COMPILED_DIR = CONTEXT_DIR / "compiled"
CONTEXT_VOICE_DIR = CONTEXT_DIR / "voice"
