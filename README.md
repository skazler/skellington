# 🎃🎄 Skellington

> *"What's this? What's this? There's agents everywhere!"*

A multi-agent AI orchestration framework where each agent is a **Halloween-ized Christmas character**. Give it a request in plain English — Jack plans it, routes subtasks to specialist agents, and weaves their results into a final answer. Streams the whole thing live over WebSockets.

```bash
skellington "research the top Python async libraries and scaffold a demo project"
```

---

## ✨ Features

- **Plan → route → delegate → synthesize** orchestration pipeline
- **Six specialist agents** — each owns a domain and its subagents
- **Multi-agent consensus** — three validators vote on code quality (majority rules)
- **Pluggable LLM providers** — Claude, OpenAI, Gemini, Ollama via one interface
- **Six MCP servers built-in** — filesystem, web search, git, code exec, sqlite, docs
- **Toolkit injection** — agents accept in-process tools *or* orthodox stdio MCP clients
- **Hallucination-resistant subagents** — LLM does judgement, Python does facts (diffs come from `difflib`, counts from state)
- **Live streaming web UI** — every plan/route/agent transition pushed to the browser in real time
- **Rich CLI** — dark-mode Halloween theming via Typer + Rich
- **Production-grade tests** — 115 tests covering orchestration, subagents, MCP, and the web UI

---

## 🎭 The Crew

| Agent | Character | Role | Subagents |
|-------|-----------|------|-----------|
| 🎃👔 **Jack Skellington** | Pumpkin King who discovered Christmas | **Orchestrator** — plans and routes | Planner, Router |
| 🧟‍♀️🎁 **Sally Claus** | Rag doll who sews Christmas magic | **Builder** — codegen, scaffold, refactor | CodeGen, Scaffold, Refactor |
| 🎰🎅 **Oogie Boogie** | Boogeyman running Christmas research | **Researcher** — web search + RAG | Search, Summary, Compare |
| 👻🔴 **Zero** | Ghost dog with a glowing red nose | **Navigator** — codebase exploration | FileExplorer, Dependency, Context |
| 👹🧝 **Lock, Shock & Barrel** | Trick-or-treat trio as Christmas elves | **Validators** — consensus-based code review | Lint, Test, Security |
| 🎭📊 **The Mayor** | Two-faced Mayor of Halloween/Christmas Town | **Reporter** — summarizes and formats | Status, Diff, Format |

---

## 🏗️ Architecture

```
User Request
     │
     ▼
Orchestrator.run()
  ├─ emits workflow.start
  └─ Jack.run()
       ├─ PlannerSubagent       → Plan(steps=[…])                emits plan.created
       ├─ RouterSubagent × N    → RoutingDecision(agent, step)   emits route.decided
       │                          (parallel via asyncio.gather)
       ├─ Orchestrator.delegate(step, agent) × N                 emits agent.start/complete/fail
       │    ├─ Zero   — navigation  (publishes state.metadata["navigation"])
       │    ├─ Sally  — builds      (publishes state.metadata["builds"])
       │    ├─ Oogie  — research    (publishes state.metadata["research"])
       │    ├─ Mayor  — reporting   (publishes state.metadata["reports"])
       │    └─ ValidatorCoordinator — runs Lock/Shock/Barrel in parallel
       │         └─ ConsensusResult (2/3 majority vote + avg score)
       │
       └─ Jack._synthesize()    → AgentResponse                  emits synthesis.start
                                                                  emits workflow.complete
```

### Event bus

Pass a callback to the orchestrator and every transition streams out:

```python
async def on_event(event: dict) -> None:
    print(event)  # {"type": "agent.start", "agent": "sally", "message": "...", "data": {…}}

state = await Orchestrator(on_event=on_event).run("your request")
```

Event vocabulary: `workflow.start/complete`, `plan.created/failed`, `route.decided/failed`, `agent.start/complete/fail`, `synthesis.start`, `result.final`.

### MCP servers

| Server | Purpose | Used by |
|--------|---------|---------|
| `filesystem` | read / write / list / search | Zero, Sally |
| `websearch` | Brave + Tavily with graceful fallback | Oogie |
| `git_server` | status / log / diff | Zero, Mayor |
| `code_exec` | sandboxed Python + pytest | Lock/Shock/Barrel |
| `database` | SQLite key-value store | all agents |
| `docs` | HTML fetch + PyPI lookup | Oogie |

Each server ships as a pair: pure-Python `tools.py` (in-process) and a thin stdio adapter (`server.py`) for orthodox MCP clients.

---

## 🚀 Quick Start

```bash
# Install
git clone https://github.com/skazler/skellington.git
cd skellington
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env — at minimum set ANTHROPIC_API_KEY or OPENAI_API_KEY

# CLI
skellington "research the best Python async libraries and scaffold a demo"

# Web UI (live streaming)
skellington web
# → open http://localhost:8000
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

## 🛠️ Configuration

Copy `.env.example` → `.env`:

```env
# LLM providers — configure at least one
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...

DEFAULT_LLM_PROVIDER=anthropic
DEFAULT_LLM_MODEL=claude-opus-4-5

# Web search (optional — Oogie falls back to LLM-imagined results if absent)
BRAVE_SEARCH_API_KEY=...
TAVILY_API_KEY=...

# Filesystem sandbox — comma-separated allowed roots
FILESYSTEM_ALLOWED_PATHS=/tmp/skellington,./workspace

# Local models (optional)
OLLAMA_BASE_URL=http://localhost:11434
```

Per-agent model overrides are supported: set `JACK_MODEL=claude-opus-4-5` and `SALLY_MODEL=claude-sonnet-4-5` in `.env` to run heavy planning on Opus and fast code generation on Sonnet.

---

## 📁 Project Structure

```
skellington/
├── src/skellington/
│   ├── core/                   # Foundation
│   │   ├── agent.py            # BaseAgent + tool-use loop
│   │   ├── subagent.py         # BaseSubAgent[T] + run_subagents_parallel()
│   │   ├── orchestrator.py     # AgentRegistry + delegate() + event bus
│   │   ├── llm.py              # Anthropic/OpenAI/Gemini client factory
│   │   ├── memory.py           # SQLite-backed agent memory
│   │   ├── config.py           # Pydantic Settings + per-agent overrides
│   │   └── types.py            # Task, WorkflowState, AgentResponse, …
│   │
│   ├── agents/                 # Main agents
│   │   ├── jack.py             # Orchestrator
│   │   ├── sally.py            # Builder
│   │   ├── oogie.py            # Researcher
│   │   ├── zero.py             # Navigator
│   │   ├── validators.py       # Lock/Shock/Barrel + ValidatorCoordinator
│   │   └── mayor.py            # Reporter
│   │
│   ├── subagents/              # Specialized subagents
│   │   ├── planner.py, router.py
│   │   ├── codegen.py, refactor.py, scaffold.py
│   │   ├── search.py, summary.py, compare.py
│   │   ├── file_explorer.py, dependency.py, context.py
│   │   ├── lint.py, test_runner.py, security.py
│   │   └── formatter.py, diff.py, status.py
│   │
│   ├── mcp_servers/            # MCP server implementations
│   │   ├── filesystem/, websearch/, git_server/
│   │   └── code_exec/, database/, docs/
│   │
│   ├── ui/
│   │   ├── cli.py              # Typer + Rich CLI
│   │   └── web/
│   │       ├── app.py          # FastAPI + WebSocket streaming
│   │       └── templates/index.html   # dark-mode UI + event timeline
│   │
│   └── utils/
│       ├── json_utils.py       # extract_json() — 4-strategy LLM JSON parser
│       ├── logging.py          # structlog config
│       └── themes.py           # Rich Halloween theming
│
├── tests/                      # 115 tests
│   ├── test_agents/            # one file per agent (jack, sally, oogie, zero, validators, mayor)
│   ├── test_subagents/         # parallel exec + every subagent
│   ├── test_core/              # types, config, json_utils, events
│   ├── test_ui/                # websocket streaming smoke test
│   └── test_mcp_servers/       # filesystem tools, stdio client, access gating
│
└── docs/
    ├── architecture.md
    ├── learning_guide.md
    ├── mcp_guide.md
    └── agents/jack.md
```

---

## 🧪 Testing

```bash
pytest                        # full suite (115 tests)
pytest --cov=skellington      # with coverage
pytest tests/test_agents/     # one layer
pytest -k mayor               # one agent
```

---

## 🧱 Design Patterns

A few deliberate choices worth calling out:

- **Toolkit injection** — agents accept a `search=` / `fs=` kwarg that defaults to the in-process `tools.py`. Pass an orthodox MCP stdio client instead and nothing else changes. Tests pass mock toolkits the same way.
- **LLM-for-judgement, Python-for-facts** — `DiffSubagent` uses `difflib` for the diff text; the LLM only narrates. `StatusSubagent` counts task statuses from `WorkflowState`; the LLM only writes the narrative. Cuts hallucination surface.
- **Graceful degradation** — no API key? Oogie falls back to LLM-imagined search results so pipelines keep running in dev. Empty workflow? `StatusSubagent` short-circuits without an LLM call.
- **Event-bus over polling** — orchestrator emits typed events; sync and async callbacks both work. Callback errors are swallowed so a broken UI can't crash the workflow.
- **Consensus with exception isolation** — `ValidatorCoordinator` runs three validators in parallel. A crashing validator becomes a failed verdict, not a panel-wide failure.
- **`extract_json()`** — 4-strategy LLM JSON parser (direct → ` ```json ` fence → any fence → balanced brace scan). Because LLMs cannot, in fact, return JSON.

---

## 📄 License

MIT — go build something spooky 🎃
