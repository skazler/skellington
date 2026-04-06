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


def extract_json(text: str) -> dict:
    """
    Extract and parse a JSON object from LLM output.

    Tries in order:
    1. Parse the whole string directly (the happy path)
    2. Extract from a ```json ... ``` code fence
    3. Extract from any ``` ... ``` code fence
    4. Find the first {...} balanced block in the string

    Raises:
        ValueError: if no valid JSON object can be found
    """
    # 1. Direct parse
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. ```json fence
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 3. Any ``` fence
    match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
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
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break

    raise ValueError(f"No valid JSON object found in LLM response:\n{text[:300]}")
