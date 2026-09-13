"""
Declarative eval cases.

Learning goal: an eval suite is data, not code. Adding a case should be a
file edit, not a new test function — otherwise the suite only grows when
someone is already in the mood to write Python.

The shape borrows two ideas from Google ADK's evalset format:

1. A case names the *trajectory* it expects, not just the final answer. Two
   runs can produce equally good prose while routing completely differently,
   and for an orchestrator the routing is the part under test.
2. Cases live in a JSON file the runner discovers, so a suite is reviewable
   as a diff.

Everything scored here is deterministic — substring and sequence matching
over the event stream. An LLM judge would add both cost and variance to the
thing measuring variance, so it is deliberately not here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

from skellington.core.types import ModelUsage, Usage


class Expect(BaseModel):
    """What a case asserts about a run.

    Every field is optional: a case that only pins the agent trajectory is a
    perfectly good case, and so is one that only checks the answer mentions
    the right thing.
    """

    agents: list[str] | None = None
    """Ordered agent trajectory, one entry per delegated step.

    Scored position by position, so a run that routes the right agents in the
    wrong order scores below one that gets the order right. None means the
    trajectory is not under test.
    """

    agents_include: list[str] = Field(default_factory=list)
    """Agents that must each appear somewhere in the trajectory, order-free.

    Usually the right assertion for this system. Sampling parameters were
    removed from current Anthropic models, so nothing pins the planner: the
    same request decomposed into `sally, sally, sally, lock, mayor` on one run
    and `oogie, lock, sally, shock, lock, mayor` on the next. An exact ordered
    trajectory fails on variance rather than on regressions, which trains you
    to ignore the suite.

    Assert the part that is actually stable — that a build request reaches the
    builder — and use `agents` only where the plan really is fixed.
    """

    min_trajectory_score: float | None = None
    """Pass `agents` at partial credit instead of demanding an exact match.

    Only meaningful alongside `agents`. 1.0 is the implicit default.
    """

    contains: list[str] = Field(default_factory=list)
    """Substrings that must appear in final_output. Case-insensitive."""

    excludes: list[str] = Field(default_factory=list)
    """Substrings that must NOT appear in final_output. Case-insensitive."""

    succeeded: bool | None = None
    """Whether the workflow must report success. None means don't care."""

    max_llm_calls: int | None = None
    """Cost ceiling, in LLM calls. Catches a prompt change that quietly
    doubles the number of round trips."""

    max_total_tokens: int | None = None
    """Cost ceiling, in tokens."""

    allow_step_failures: bool = False
    """Whether an agent.fail mid-run is acceptable.

    Off by default, and deliberately so. Jack synthesizes whatever partial
    results come back, so a workflow whose validation step failed outright
    still reports success with plausible prose. Without this check a dropped
    specialist is invisible to every other assertion here: the trajectory
    still lists the agent (it was attempted), the stream is still well
    formed, and the answer still reads fine.

    Turn it on for a case that is deliberately exercising a failure path.
    """

    @property
    def is_empty(self) -> bool:
        """True when the case asserts nothing — always a mistake, never a pass."""
        return (
            self.agents is None
            and not self.agents_include
            and not self.contains
            and not self.excludes
            and self.succeeded is None
            and self.max_llm_calls is None
            and self.max_total_tokens is None
        )


class EvalCase(BaseModel):
    """One request and what it should produce."""

    id: str
    request: str
    expect: Expect = Field(default_factory=Expect)
    notes: str | None = None

    @model_validator(mode="after")
    def _reject_empty_expectations(self) -> EvalCase:
        if self.expect.is_empty:
            raise ValueError(
                f"case {self.id!r} asserts nothing; a case with no expectations "
                "always passes and measures nothing"
            )
        return self


class EvalSet(BaseModel):
    """A named collection of cases, loaded from one JSON file."""

    name: str
    description: str | None = None
    cases: list[EvalCase] = Field(default_factory=list)

    @model_validator(mode="after")
    def _reject_duplicate_ids(self) -> EvalSet:
        seen: set[str] = set()
        for case in self.cases:
            if case.id in seen:
                raise ValueError(f"duplicate case id {case.id!r} in eval set {self.name!r}")
            seen.add(case.id)
        return self

    @classmethod
    def from_file(cls, path: str | Path) -> EvalSet:
        """Load an eval set from a JSON file.

        The filename is the default name, so a set only needs to declare one
        if it wants to differ. Both ".evalset.json" and ".json" are stripped —
        Path.stem only removes the last suffix, which would leave "routing"
        as "routing.evalset".
        """
        p = Path(path)
        raw: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
        raw.setdefault("name", p.name.removesuffix(".json").removesuffix(".evalset"))
        return cls.model_validate(raw)

    @classmethod
    def from_dir(cls, directory: str | Path) -> list[EvalSet]:
        """Load every *.evalset.json under `directory`, sorted by filename."""
        d = Path(directory)
        return [cls.from_file(p) for p in sorted(d.glob("*.evalset.json"))]

    def get(self, case_id: str) -> EvalCase | None:
        return next((c for c in self.cases if c.id == case_id), None)


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


class Check(BaseModel):
    """One assertion's outcome, kept as data so a report can explain itself."""

    name: str
    passed: bool
    detail: str
    score: float | None = None
    """Graded checks report a 0..1 score; binary checks leave this None."""


class CaseResult(BaseModel):
    """What one case produced when run."""

    case_id: str
    checks: list[Check] = Field(default_factory=list)
    trajectory: list[str] = Field(default_factory=list)
    final_output: str | None = None
    usage: Usage = Field(default_factory=Usage)
    duration_s: float = 0.0
    error: str | None = None
    """Set when the run itself blew up, as opposed to failing its checks.
    A harness that reports those two the same way hides its own bugs."""

    @property
    def passed(self) -> bool:
        return self.error is None and all(c.passed for c in self.checks)

    @property
    def trajectory_score(self) -> float | None:
        check = next((c for c in self.checks if c.name == "trajectory"), None)
        return check.score if check else None


class EvalReport(BaseModel):
    """Every case in one set."""

    set_name: str
    results: list[CaseResult] = Field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def all_passed(self) -> bool:
        return self.total > 0 and self.passed == self.total

    @property
    def usage(self) -> Usage:
        """Cost of the whole set."""
        total = Usage()
        for result in self.results:
            total.calls += result.usage.calls
            total.input_tokens += result.usage.input_tokens
            total.output_tokens += result.usage.output_tokens
            for model, per in result.usage.by_model.items():
                agg = total.by_model.setdefault(model, ModelUsage())
                agg.calls += per.calls
                agg.input_tokens += per.input_tokens
                agg.output_tokens += per.output_tokens
        return total

    @property
    def trajectory_avg(self) -> float | None:
        """Mean trajectory score across cases that tested one."""
        scores = [r.trajectory_score for r in self.results if r.trajectory_score is not None]
        return sum(scores) / len(scores) if scores else None
