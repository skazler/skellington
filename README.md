# 🎃🎄 Skellington

> *"What's this? What's this? There's agents everywhere!"*

A multi-agent AI orchestration framework where each agent is a Halloween-ized Christmas character. Jack plans your request, routes subtasks to specialists, and weaves the results into a final answer — streamed live over WebSockets.

```bash
skellington "research the top Python async libraries and scaffold a demo project"
```

*A personal learning project. Not production-ready, not affiliated with any LLM provider. [![CI](https://github.com/skazler/skellington/actions/workflows/ci.yml/badge.svg)](https://github.com/skazler/skellington/actions/workflows/ci.yml)*

---

## 🎭 The Crew

- 🎃 **Jack Skellington** — orchestrator: plans and routes
- 🧟‍♀️ **Sally Claus** — builder: codegen, scaffold, refactor
- 🎰 **Oogie Boogie** — researcher: web search + RAG
- 👻 **Zero** — navigator: codebase exploration
- 👹 **Lock, Shock & Barrel** — validators: 2/3 consensus code review
- 🎭 **The Mayor** — reporter: summarizes and formats

---

## 🚀 Quick Start

```bash
git clone https://github.com/skazler/skellington.git
cd skellington
pip install -e ".[dev]"

cp .env.example .env   # set API_KEY

skellington "research the best Python async libraries and scaffold a demo"
skellington web        # local port: 8000
```

### Python API

```python
from skellington.agents import Jack, Sally, Oogie, Zero, Mayor
from skellington.core.orchestrator import AgentRegistry, Orchestrator

for agent_cls in (Jack, Sally, Oogie, Zero, Mayor):
    AgentRegistry.register(agent_cls())

state = await Orchestrator().run("your request here")
print(state.tasks[0].result)
```

---

## 🏗️ How it works

**Plan → route → delegate → synthesize.** Jack runs a `PlannerSubagent` to break the request into steps, a `RouterSubagent` picks the specialist for each step (in parallel), each specialist runs its subagents, and Jack synthesizes the final answer.

Every transition emits a typed event — `workflow.start`, `plan.created`, `route.decided`, `agent.start/complete/fail`, `synthesis.start`, `result.final` — which is what powers the live web UI.

```python
async def on_event(event: dict) -> None:
    print(event)

state = await Orchestrator(on_event=on_event).run("your request")
```

**Six MCP servers** ship in-tree: `filesystem`, `websearch`, `git_server`, `code_exec`, `database`, `docs`. Each is a pair — a pure-Python `tools.py` for in-process use and a stdio `server.py` for orthodox MCP clients. Agents accept a `fs=` / `search=` kwarg so tests pass mock toolkits the same way production passes real ones.

**A few deliberate choices** worth knowing about:

- **LLM for judgement, Python for facts.** Diffs come from `difflib`; counts from `WorkflowState`. The LLM only narrates. Cuts hallucination surface.
- **Skill-per-file.** Specialist agents live in packages where each tool is its own file under `skills/`. Adding a skill = one new file + one line in `__init__.py`.
- **Graceful degradation.** No search API key → Oogie falls back to LLM-imagined results. Empty workflow → short-circuit without an LLM call.
- **Consensus with isolation.** Lock/Shock/Barrel run in parallel; a crashing validator is a failed vote, not a panel-wide failure.

---

## 🛠️ Configuration Examples

```env
# At least one provider
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

DEFAULT_LLM_PROVIDER=anthropic
DEFAULT_LLM_MODEL=claude-opus-4-7

# Optional — Oogie falls back if absent
BRAVE_SEARCH_API_KEY=...
TAVILY_API_KEY=...

# Filesystem sandbox
FILESYSTEM_ALLOWED_PATHS=/tmp/skellington,./workspace
```

Per-agent overrides: set `JACK_MODEL=claude-opus-4-7` and `SALLY_MODEL=claude-sonnet-4-6` to put heavy planning on Opus and fast codegen on Sonnet.

---

## 📁 Layout

```
src/skellington/
├── core/           # BaseAgent, BaseSubAgent, Orchestrator, LLM clients, types
├── agents/         # Jack, Sally, Oogie, Zero, Mayor, Lock/Shock/Barrel
├── subagents/      # Planner, Router, CodeGen, Search, Lint, …
├── mcp_servers/    # filesystem, websearch, git_server, code_exec, database, docs
├── ui/             # Typer CLI + FastAPI/WebSocket web UI
└── utils/          # extract_json (4-strategy LLM JSON parser), logging, themes
tests/              # 158 tests, one file per agent / subagent / server
```

---

## 🧪 Testing

```bash
pytest                        # full suite (158 tests)
pytest tests/test_agents/     # one layer
pytest -k mayor               # one agent
```

---

## 📄 License

MIT — go build something spooky 🎃
