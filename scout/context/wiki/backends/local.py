"""LocalWikiBackend — direct filesystem I/O for WikiContextProvider.

Single-container only. Not safe for multi-container deployments
(no concurrency coordination). Use ``GithubWikiBackend`` or
``S3WikiBackend`` in prod.
"""

from __future__ import annotations

from pathlib import Path

from scout.context.base import HealthState, HealthStatus


class LocalWikiBackend:
    """Dev-only backend that reads and writes straight to the filesystem."""

    kind: str = "local"

    def __init__(self, root: str = "./context") -> None:
        self.root = Path(root).resolve()

    def health(self) -> HealthStatus:
        if not self.root.exists():
            try:
                self.root.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                return HealthStatus(HealthState.DISCONNECTED, f"{self.root}: {exc}")
        if not self.root.is_dir():
            return HealthStatus(HealthState.DISCONNECTED, f"{self.root} is not a directory")
        return HealthStatus(HealthState.CONNECTED, str(self.root))

    def list_paths(self, prefix: str = "") -> list[str]:
        base = self._resolve(prefix) if prefix else self.root
        if not base.exists():
            return []
        out: list[str] = []
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            try:
                rel = p.relative_to(self.root)
            except ValueError:
                continue
            out.append(str(rel))
        return sorted(out)

    def read_bytes(self, path: str) -> bytes:
        return self._resolve(path).read_bytes()

    def write_bytes(self, path: str, content: bytes) -> None:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    def delete(self, path: str) -> None:
        target = self._resolve(path)
        if target.exists() and target.is_file():
            target.unlink()

    def _resolve(self, path: str) -> Path:
        # Normalize and guard against escapes out of root.
        target = (self.root / path).resolve()
        if self.root != target and self.root not in target.parents:
            raise ValueError(f"path {path!r} escapes backend root {self.root}")
        return target
