"""Tests for the declarative eval case schema."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from skellington.eval import EvalCase, EvalSet, Expect


def test_loads_a_set_from_a_file(tmp_path):
    path = tmp_path / "routing.evalset.json"
    path.write_text(
        json.dumps(
            {
                "description": "d",
                "cases": [
                    {"id": "a", "request": "do a thing", "expect": {"agents": ["sally"]}},
                ],
            }
        )
    )

    eval_set = EvalSet.from_file(path)

    assert eval_set.name == "routing", "filename stem is the default name"
    assert eval_set.get("a").expect.agents == ["sally"]
    assert eval_set.get("nope") is None


def test_explicit_name_wins_over_the_filename(tmp_path):
    path = tmp_path / "routing.evalset.json"
    path.write_text(
        json.dumps(
            {
                "name": "custom",
                "cases": [{"id": "a", "request": "r", "expect": {"succeeded": True}}],
            }
        )
    )

    assert EvalSet.from_file(path).name == "custom"


def test_plain_json_filenames_also_lose_only_their_extension(tmp_path):
    path = tmp_path / "smoke.json"
    path.write_text(
        json.dumps({"cases": [{"id": "a", "request": "r", "expect": {"succeeded": True}}]})
    )

    assert EvalSet.from_file(path).name == "smoke"


def test_from_dir_discovers_only_evalset_files(tmp_path):
    (tmp_path / "b.evalset.json").write_text(
        json.dumps({"cases": [{"id": "x", "request": "r", "expect": {"succeeded": True}}]})
    )
    (tmp_path / "a.evalset.json").write_text(
        json.dumps({"cases": [{"id": "y", "request": "r", "expect": {"succeeded": True}}]})
    )
    (tmp_path / "notes.json").write_text(json.dumps({"cases": []}))

    sets = EvalSet.from_dir(tmp_path)

    assert [s.name for s in sets] == ["a", "b"], "sorted, and plain .json ignored"


def test_duplicate_case_ids_are_rejected():
    with pytest.raises(ValidationError, match="duplicate case id"):
        EvalSet(
            name="s",
            cases=[
                EvalCase(id="same", request="r", expect=Expect(succeeded=True)),
                EvalCase(id="same", request="r", expect=Expect(succeeded=True)),
            ],
        )


def test_a_case_that_asserts_nothing_is_rejected():
    """An empty expectation always passes, which is worse than no case at all."""
    with pytest.raises(ValidationError, match="asserts nothing"):
        EvalCase(id="empty", request="r")


@pytest.mark.parametrize(
    "expect",
    [
        Expect(agents=["sally"]),
        Expect(contains=["x"]),
        Expect(excludes=["x"]),
        Expect(succeeded=False),
        Expect(max_llm_calls=1),
        Expect(max_total_tokens=1),
    ],
)
def test_any_single_expectation_is_enough(expect):
    assert not expect.is_empty
    EvalCase(id="ok", request="r", expect=expect)


def test_the_repos_own_eval_sets_are_valid():
    """The checked-in sets must load — they are the harness's own smoke test."""
    sets = EvalSet.from_dir("evalsets")

    assert sets, "expected at least one eval set in evalsets/"
    for eval_set in sets:
        assert eval_set.cases
        for case in eval_set.cases:
            assert case.request.strip()
