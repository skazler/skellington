"""
Assemble a model-adapted system prompt by appending fragments selected from
the model's capability flags.

Add a new adaptation in two places:
1. A flag on ModelCard ([core/models.py](../core/models.py))
2. A branch in `assemble_prompt` that loads the matching fragment

Fragments are .md files in [fragments/](fragments/) — one file per quirk, not
per model. The flag is what tells you whether the quirk applies.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from skellington.core.models import ModelCard

_FRAGMENTS_DIR = Path(__file__).parent / "fragments"


@lru_cache(maxsize=None)
def load_fragment(name: str) -> str:
    """Read a fragment file by stem (without .md). Cached for the process lifetime."""
    path = _FRAGMENTS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8").strip()


def assemble_prompt(base: str, card: ModelCard) -> str:
    """Compose `base` with fragments appropriate to the model's capabilities."""
    parts: list[str] = [base.strip()]

    if not card.supports_native_json:
        parts.append(load_fragment("json_via_prose"))
    if card.prefers_xml_tags:
        parts.append(load_fragment("xml_tagging"))
    if card.max_parallel_tools <= 1:
        parts.append(load_fragment("serial_tools"))

    return "\n\n".join(parts)
