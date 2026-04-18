"""
Pure filesystem tool functions.

These are the actual implementations — plain async functions that return plain
Python values. The MCP server in `server.py` is a thin adapter that wraps
these for the stdio protocol. Agents (and the in-process MCP client) call
these directly so we don't pay the subprocess/transport cost when we don't
need the isolation.

Access is gated by `filesystem_allowed_paths` in settings — the same policy
applies whether a caller reaches us directly or through the MCP transport.
"""

from __future__ import annotations

import re
from pathlib import Path

from skellington.core.config import get_settings


class FilesystemAccessError(PermissionError):
    """Raised when a path falls outside the allowed roots."""


def _ensure_allowed(path: Path) -> Path:
    """Resolve `path` and verify it lives under an allowed root."""
    settings = get_settings()
    resolved = path.resolve()
    for allowed in settings.filesystem_allowed_paths:
        try:
            resolved.relative_to(Path(allowed).expanduser().resolve())
            return resolved
        except ValueError:
            continue
    raise FilesystemAccessError(f"path not in allowed roots: {path}")


async def read_file(path: str) -> str:
    """Read a UTF-8 text file under an allowed root."""
    p = _ensure_allowed(Path(path))
    return p.read_text(encoding="utf-8")


async def write_file(path: str, content: str) -> str:
    """Write `content` to `path`, creating parent dirs if needed. Returns the written path."""
    p = _ensure_allowed(Path(path))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return str(p)


async def list_directory(path: str, recursive: bool = False) -> list[str]:
    """List entries under `path`, as paths relative to `path`. Sorted."""
    p = _ensure_allowed(Path(path))
    pattern = "**/*" if recursive else "*"
    return sorted(str(f.relative_to(p)) for f in p.glob(pattern))


async def search_files(
    directory: str,
    pattern: str,
    file_glob: str = "**/*",
) -> list[str]:
    """
    Regex-search files under `directory`. Returns lines formatted as
    "<path>:<lineno>: <line>". Binary / unreadable files are silently skipped.
    """
    root = _ensure_allowed(Path(directory))
    rx = re.compile(pattern)
    results: list[str] = []
    for filepath in root.glob(file_glob):
        if not filepath.is_file():
            continue
        try:
            text = filepath.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                results.append(f"{filepath}:{i}: {line}")
    return results
