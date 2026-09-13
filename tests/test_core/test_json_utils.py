"""Tests for the JSON extraction utility."""

import pytest

from skellington.utils.json_utils import extract_json


def test_direct_json():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_json_with_whitespace():
    assert extract_json('  \n{"a": 1}\n  ') == {"a": 1}


def test_json_fence():
    text = '```json\n{"a": 1}\n```'
    assert extract_json(text) == {"a": 1}


def test_plain_fence():
    text = '```\n{"a": 1}\n```'
    assert extract_json(text) == {"a": 1}


def test_json_embedded_in_prose():
    text = 'Here is the result: {"a": 1} — that is all.'
    assert extract_json(text) == {"a": 1}


def test_nested_json():
    text = '{"outer": {"inner": [1, 2, 3]}}'
    result = extract_json(text)
    assert result["outer"]["inner"] == [1, 2, 3]


def test_raises_on_no_json():
    with pytest.raises(ValueError, match="No valid JSON"):
        extract_json("this is just plain text with no JSON")


def test_raises_on_empty():
    with pytest.raises(ValueError):
        extract_json("")


# ---------------------------------------------------------------------------
# Raw control characters (markdown inside JSON)
# ---------------------------------------------------------------------------


def test_raw_newline_inside_a_string_is_tolerated():
    """Mayor's real failure: a markdown table with a literal newline.

    json.loads rejects that as "Invalid control character", so a well-formed
    report surfaced as "No valid JSON object found in LLM response".
    """
    raw = '{"format": "markdown", "content": "| Completed | 5 / 7 |\n| Rate | 71% |"}'

    result = extract_json(raw)

    assert result["format"] == "markdown"
    assert "Completed" in result["content"]
    assert "Rate" in result["content"], "content after the raw newline must survive"


def test_raw_newline_inside_a_fenced_block_is_tolerated():
    raw = '```json\n{"content": "line one\nline two"}\n```'

    assert extract_json(raw)["content"] == "line one\nline two"


def test_raw_tab_inside_a_string_is_tolerated():
    assert extract_json('{"code": "def f():\n\treturn 1"}')["code"].endswith("return 1")


def test_valid_json_still_takes_the_exact_path():
    """Leniency must not change how well-formed input is parsed."""
    assert extract_json('{"a": "b\\nc"}') == {"a": "b\nc"}


def test_genuinely_broken_json_still_raises():
    with pytest.raises(ValueError, match="No valid JSON object found"):
        extract_json("there is no json here at all")


# ---------------------------------------------------------------------------
# Repair pass: invalid escapes and trailing commas
# ---------------------------------------------------------------------------


def test_invalid_escape_from_generated_regex_is_repaired():
    r"""Sally's real failure: generated Python containing a regex like \d.

    A bare backslash is an invalid JSON escape, which strict=False does not
    help with — that only tolerates control characters.
    """
    result = extract_json(r'{"code": "re.match(\"\d+\", s)"}')

    assert result["code"] == r're.match("\d+", s)'


def test_windows_path_escapes_are_repaired():
    assert extract_json(r'{"path": "C:\Users\dev"}')["path"] == r"C:\Users\dev"


def test_trailing_comma_is_repaired():
    assert extract_json('{"a": 1, "b": 2,}') == {"a": 1, "b": 2}
    assert extract_json('{"a": [1, 2,]}') == {"a": [1, 2]}


def test_repair_applies_inside_a_code_fence_too():
    assert extract_json('```json\n{"code": "\\d+"}\n```')["code"] == r"\d+"


def test_valid_escapes_are_never_rewritten():
    """The repair pass must not touch input that already parses."""
    assert extract_json(r'{"a": "line\nbreak", "b": "quote\"inside", "c": "tab\there"}') == {
        "a": "line\nbreak",
        "b": 'quote"inside',
        "c": "tab\there",
    }


def test_unicode_escapes_survive_the_repair_pass():
    assert extract_json(r'{"a": "\u00e9"}')["a"] == "é"
