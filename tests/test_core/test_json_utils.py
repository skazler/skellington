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
