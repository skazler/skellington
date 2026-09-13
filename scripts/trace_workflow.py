"""
Trace one request through the whole Skellington pipeline — offline, no API key.

Run:  python scripts/trace_workflow.py

What is real here: the Orchestrator, Jack, PlannerSubagent, RouterSubagent,
WorkflowState, and the event bus. Every line of that code path executes for
real. What is faked: the LLM (a canned responder that dispatches on the system
prompt) and the five specialist agents (stubs that report what they received).

The point is to watch the shape of a workflow — plan, route, delegate,
synthesize — without spending anything. The agent wiring below deliberately
mirrors ui/cli.py exactly, warts included.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time

import structlog

from skellington.agents.jack import Jack
from skellington.core.orchestrator import Orchestrator
from skellington.core.types import (
    AgentName,
    AgentResponse,
    LLMProvider,
    LLMResponse,
    Task,
    WorkflowState,
)
from skellington.core.usage import UsageRecorder, UsageTrackingClient

REQUEST = (
    "Research online the top Python async frameworks, write code for a small demo, "
    "check the demo is correct, and summarize the results."
)

# What the fake planner "decides". Chosen so three steps hit the router's
# keyword short-circuit and one has to fall through to an LLM call.
PLAN = {
    "goal": "Compare async frameworks and ship a demo",
    "steps": [
        "Research online the top 3 Python async frameworks",
        "Write code for a minimal asyncio demo",
        "Check the demo for logic errors",
        "Summarize the results for the user",
    ],
    "estimated_agents": ["oogie", "sally", "lock", "mayor"],
}

SYNTHESIS = (
    "The frameworks were weighed, the demo was written, the review was called for, "
    "and the report was made. A fine night's work."
)


# ---------------------------------------------------------------------------
# The fake LLM
# ---------------------------------------------------------------------------


class TracingLLM:
    """Canned LLM that answers based on which system prompt it was handed.

    Keeps a per-call ledger of who asked for what. The token totals come
    from the real UsageRecorder below, not from this ledger — the ledger only
    attributes each call to a caller, which the recorder does not track.
    """

    provider = LLMProvider.ANTHROPIC

    def __init__(self) -> None:
        self.ledger: list[dict] = []

    async def complete(self, messages, config) -> LLMResponse:
        system = config.system_prompt or ""
        user = messages[-1].content if messages else ""

        if "precise task planner" in system:
            caller, content = "PlannerSubagent", json.dumps(PLAN)
        elif "routing expert" in system:
            caller = "RouterSubagent"
            content = json.dumps(
                {
                    "step": user,
                    "assigned_agent": "lock",
                    "reasoning": "correctness review is Lock's specialty",
                }
            )
        else:
            caller, content = "Jack (synthesis)", SYNTHESIS

        self.ledger.append(
            {
                "caller": caller,
                "model": config.model,
                "input_tokens": len(system + user) // 4,
                "output_tokens": len(content) // 4,
            }
        )
        return LLMResponse(
            content=content,
            model=config.model,
            provider=self.provider,
            input_tokens=len(system + user) // 4,
            output_tokens=len(content) // 4,
        )


# ---------------------------------------------------------------------------
# Stub specialists
# ---------------------------------------------------------------------------


class StubAgent:
    """Stands in for Sally/Oogie/Zero/Mayor. Reports what it was asked to do."""

    def __init__(self, name: AgentName) -> None:
        self.name = name

    async def run(self, task: Task, state: WorkflowState) -> AgentResponse:
        return AgentResponse(
            agent=self.name,
            task_id=task.id,
            content=f"[{self.name.value} handled] {task.description}",
        )


# ---------------------------------------------------------------------------
# Trace printing
# ---------------------------------------------------------------------------


class Trace:
    def __init__(self) -> None:
        self.seq = 0
        self.t0 = time.perf_counter()
        self.events: list[dict] = []

    def __call__(self, event: dict) -> None:
        self.seq += 1
        self.events.append(event)
        ms = (time.perf_counter() - self.t0) * 1000
        agent = event.get("agent") or "-"
        message = (event.get("message") or "").replace("\n", " ")
        if len(message) > 68:
            message = message[:65] + "..."
        print(f"  {self.seq:>2}  {ms:>7.1f}ms  {event['type']:<20} {agent:<8} {message}")
        extra = event.get("data") or {}
        for key, value in extra.items():
            if key == "steps":
                for i, step in enumerate(value, 1):
                    print(f"                                             step {i}: {step}")
            elif key == "reasoning":
                print(f"                                             why: {value}")


def rule(title: str) -> None:
    print(f"\n{title}\n{'-' * len(title)}")


# ---------------------------------------------------------------------------


async def main(verbose: bool = False) -> None:
    # structlog's own output interleaves with the trace and drowns it. structlog
    # defaults to its own PrintLogger, so this has to be set on structlog itself
    # rather than via logging.basicConfig. -v puts the internals log back.
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if verbose else logging.CRITICAL
        )
    )

    llm = TracingLLM()
    trace = Trace()

    # Mirrors agents.default_agents(), but with stubs in place of the real
    # specialists so nothing calls out. Drop a name from this tuple to watch
    # the orchestrator report that step as agent.fail rather than dropping it.
    specialists = (
        AgentName.SALLY,
        AgentName.OOGIE,
        AgentName.ZERO,
        AgentName.LOCK,
        AgentName.SHOCK,
        AgentName.BARREL,
        AgentName.MAYOR,
    )
    recorder = UsageRecorder()
    tracked = UsageTrackingClient(llm, recorder)
    agents = [Jack(llm_client=tracked), *(StubAgent(name) for name in specialists)]

    print(f"\nrequest: {REQUEST}")
    rule("events")
    orchestrator = Orchestrator(agents=agents, on_event=trace, usage=recorder)
    state = await orchestrator.run(REQUEST)

    rule("workflow state")
    print(f"  workflow id : {state.id}")
    print(f"  tasks       : {len(state.tasks)}")
    for task in state.tasks:
        kind = "root" if task.parent_task_id is None else "  +--"
        owner = task.assigned_to.value if task.assigned_to else "-"
        print(f"    {kind} [{task.status.value:<9}] {owner:<7} {task.title[:52]}")

    rule("llm calls")
    for i, call in enumerate(llm.ledger, 1):
        print(
            f"  {i}. {call['caller']:<18} {call['model']:<20} "
            f"in={call['input_tokens']:<5} out={call['output_tokens']}"
        )

    usage = state.usage
    print(f"\n  state.usage: {usage.calls} calls, "
          f"{usage.input_tokens} in / {usage.output_tokens} out "
          f"({usage.total_tokens} tokens)")
    for model, per in sorted(usage.by_model.items()):
        print(f"    {model:<24} {per.calls} calls, "
              f"{per.input_tokens} in / {per.output_tokens} out")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-v", "--verbose", action="store_true", help="show structlog output too")
    asyncio.run(main(parser.parse_args().verbose))
