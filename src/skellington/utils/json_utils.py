"""
JSON extraction utilities.

LLMs often wrap JSON responses in markdown code fences:

    ```json
    {"key": "value"}
    ```

Or add prose before/after the JSON block. This module handles all of that
so subagents can reliably parse structured output.
"""

from __future__ import annotations

import json
import re

# A backslash that does not begin a valid JSON escape. Generated Python is the
# usual source: a regex like \d, or a Windows path. json.loads rejects these
# even with strict=False, because it is an invalid escape rather than a stray
# control character.
_INVALID_ESCAPE = re.compile(r'\\(?!["\\/bfnrtu])')

# A comma before a closing brace or bracket.
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")


def _repair(candidate: str) -> str:
    """Fix the two malformations models produce most often.

    Escaping a stray backslash is the only coherent reading: if it does not
    begin a valid escape, the document is already invalid, and the author
    meant a literal backslash. Applied only after strict and lenient parsing
    have both failed, so well-formed input never passes through here.
    """
    return _TRAILING_COMMA.sub(r"\1", _INVALID_ESCAPE.sub(r"\\\\", candidate))


def _loads(candidate: str) -> dict:
    """Parse `candidate`, tolerating raw control characters inside strings.

    A model asked for JSON containing markdown routinely emits a real newline
    inside a string value instead of an escaped one — a markdown table is the
    reliable trigger. json.loads rejects that as "Invalid control character",
    which is how a perfectly well-formed report became "No valid JSON object
    found". strict=False accepts it and changes nothing else.

    Strict first, so genuinely valid JSON takes the fast, exact path.
    """
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(candidate, strict=False)
    except json.JSONDecodeError:
        return json.loads(_repair(candidate), strict=False)


def extract_json(text: str) -> dict:
    """
    Extract and parse a JSON object from LLM output.

    Tries in order:
    1. Parse the whole string directly (the happy path)
    2. Extract from a ```json ... ``` code fence
    3. Extract from any ``` ... ``` code fence
    4. Find the first {...} balanced block in the string

    Each attempt escalates: strict, then strict=False for the raw newlines a
    model emits when the JSON carries markdown, then a repair pass for invalid
    escapes and trailing commas.

    Raises:
        ValueError: if no valid JSON object can be found
    """
    # 1. Direct parse
    text = text.strip()
    try:
        return _loads(text)
    except json.JSONDecodeError:
        pass

    # 2. ```json fence
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        try:
            return _loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 3. Any ``` fence
    match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        try:
            return _loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 4. Find first balanced { ... } block
    start = text.find("{")
    if start != -1:
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return _loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break

    raise ValueError(f"No valid JSON object found in LLM response:\n{text[:300]}")
