# 🎃🎄 Skellington

> *"What's this? What's this? There's agents everywhere!"*

A multi-agent AI orchestration framework where each agent is a **Halloween-ized Christmas character**. Skellington is a hands-on learning playground for cutting-edge AI engineering patterns — agentic workflows, subagent decomposition, MCP server development, multi-provider LLM support, and more.

---

## 🧠 What You'll Learn

| # | Skill | Where |
|---|-------|--------|
| 1 | **Agent Orchestration** | Jack routes tasks, manages handoffs, maintains workflow state |
| 2 | **Subagent Decomposition** | Each agent spawns focused subagents for specialized subtasks |
| 3 | **MCP Server Development** | Build 6+ Model Context Protocol servers from scratch |
| 4 | **Tool-Use Loops** | Agents call tools → observe results → decide next steps |
| 5 | **Multi-Provider LLM Support** | Abstracted LLM layer: Claude, OpenAI, Gemini, local models |
| 6 | **RAG Patterns** | Oogie's research pipeline teaches retrieval-augmented generation |
| 7 | **Multi-Agent Consensus** | Lock/Shock/Barrel demonstrate voting, critic, and debate patterns |
| 8 | **Streaming & Async** | Real-time agent output, parallel subagent execution |
| 9 | **State & Memory** | SQLite-backed agent memory, conversation context management |
| 10 | **CLI + Web UI** | Typer/Rich CLI first, then FastAPI + web frontend |

---

## 🎭 The Characters

### Main Agents

| Agent | Character | Role |
|-------|-----------|------|
| 🎃👔 **Jack Skellington** | The Pumpkin King who discovered Christmas | **Orchestrator** — routes tasks, plans workflows, manages agent handoffs |
| 🧟‍♀️🎁 **Sally Claus** | The rag doll who sews Christmas magic | **Builder** — code generation, project scaffolding, file creation |
| 🎰🎅 **Oogie Boogie (Sandy Claws)** | The boogeyman running Christmas research | **Researcher** — web search, RAG, documentation lookup |
| 👻🔴 **Zero** | The ghost dog with a glowing red nose | **Navigator** — file system exploration, codebase analysis, context gathering |
| 👹🧝 **Lock, Shock & Barrel** | The trick-or-treat trio as Christmas elves | **Validators** — multi-agent code review, testing, linting (consensus-based) |
| 🎭📊 **The Mayor** | Two-faced Mayor of Halloween/Christmas Town | **Reporter** — summarizes results, generates reports, tracks status |

### Subagents

Each main agent orchestrates domain-specific subagents:

| Parent | Subagents |
|--------|-----------|
| **Jack** | `PlannerSubagent`, `RouterSubagent` |
| **Sally** | `CodeGenSubagent`, `RefactorSubagent`, `ScaffoldSubagent` |
| **Oogie** | `SearchSubagent`, `SummarySubagent`, `CompareSubagent` |
| **Zero** | `FileExplorerSubagent`, `DependencySubagent`, `ContextSubagent` |
| **Lock/Shock/Barrel** | `LintSubagent`, `TestSubagent`, `SecuritySubagent` (each IS a subagent) |
| **Mayor** | `FormatSubagent`, `DiffSubagent`, `StatusSubagent` |

---

## 🏗️ Architecture

```
User Request
     │
     ▼
Orchestrator.run()
  └─ jack._orchestrator = self   ← injects delegation path
     │
     ▼
Jack.run()                        ✅ live
  ├─ PlannerSubagent.run()        ✅ live — extract_json() handles LLM formatting quirks
  │    └─ Plan(steps=[...])
  │
  ├─ RouterSubagent.run() × N     ✅ live — parallel via asyncio.gather
  │    └─ RoutingDecision(assigned_agent="sally"|"oogie"|...)
  │
  ├─ Orchestrator.delegate(step, agent) × N
  │    ├─ Zero    ✅ Phase 3      (file explorer / dependency / context subagents)
  │    ├─ Sally   ✅ Phase 4      (codegen / scaffold / refactor subagents)
  │    ├─ Oogie   ✅ Phase 5      (search → summary → compare; Brave/Tavily or LLM fallback)
  │    └─ Mayor   ✅ Phase 8      (status → optional diff → format; reads state.metadata)
  │
  ├─ ValidatorCoordinator         ✅ Phase 6 — parallel multi-agent consensus
  │    ├─ Lock   → LintSubagent
  │    ├─ Shock  → TestSubagent
  │    └─ Barrel → SecuritySubagent
  │         └─ ConsensusResult (majority vote + average score)
  │
  └─ Jack._synthesize()           ✅ live — weaves all results into final answer
       └─ AgentResponse
```

### MCP Servers Built in This Project

| Server | Purpose | Agent User |
|--------|---------|-----------|
| `filesystem` | Read/write/search files | Zero, Sally |
| `websearch` | Brave/Tavily web search | Oogie |
| `git_server` | Git ops, diff analysis | Zero, Mayor |
| `code_exec` | Sandboxed code execution | Lock/Shock/Barrel |
| `database` | SQLite agent memory/state | All agents |
| `docs` | Fetch & parse documentation | Oogie |

---

## 📁 Project Structure

```
skellington/
├── README.md
├── .gitignore
├── pyproject.toml
├── requirements.txt
├── .env.example
│
├── src/
│   └── skellington/
│       ├── __init__.py
│       ├── main.py                    # CLI entry point
│       │
│       ├── core/                      # Foundation layer  ✅ implemented
│       │   ├── agent.py               # Base Agent class + tool-use loop
│       │   ├── subagent.py            # Base SubAgent class + run_subagents_parallel()
│       │   ├── orchestrator.py        # AgentRegistry + Orchestrator.delegate()
│       │   ├── llm.py                 # AnthropicClient, OpenAIClient, LLMClientFactory
│       │   ├── memory.py              # SQLite-backed agent memory (SQLAlchemy async)
│       │   ├── config.py              # Pydantic Settings + per-agent model overrides
│       │   └── types.py               # All shared Pydantic models
│       │
│       ├── agents/                    # Main character agents
│       │   ├── jack.py                # ✅ Orchestrator — plan → route → delegate → synthesize
│       │   ├── sally.py               # ✅ Builder (Phase 4)
│       │   ├── oogie.py               # ✅ Researcher (Phase 5)
│       │   ├── zero.py                # ✅ Navigator (Phase 3)
│       │   ├── validators.py          # ✅ Lock/Shock/Barrel + ValidatorCoordinator (Phase 6)
│       │   └── mayor.py               # ✅ Reporter (Phase 8)
│       │
│       ├── subagents/                 # Specialized subagents
│       │   ├── planner.py             # ✅ Plan decomposition with JSON fallback
│       │   ├── router.py              # ✅ Step routing with agent validation + fallback
│       │   ├── codegen.py             # ✅ (Phase 4)
│       │   ├── refactor.py            # ✅ (Phase 4)
│       │   ├── scaffold.py            # ✅ (Phase 4)
│       │   ├── search.py              # ✅ (Phase 5) — toolkit-injectable + LLM fallback
│       │   ├── summary.py             # ✅ (Phase 5)
│       │   ├── compare.py             # ✅ (Phase 5)
│       │   ├── file_explorer.py       # ✅ (Phase 3)
│       │   ├── dependency.py          # ✅ (Phase 3)
│       │   ├── context.py             # ✅ (Phase 3)
│       │   ├── lint.py                # ✅ (Phase 6)
│       │   ├── test_runner.py         # ✅ (Phase 6)
│       │   ├── security.py            # ✅ (Phase 6)
│       │   ├── formatter.py           # ✅ (Phase 8)
│       │   ├── diff.py                # ✅ (Phase 8) — difflib-deterministic; LLM only narrates
│       │   └── status.py              # ✅ (Phase 8) — counts from state, LLM narrates
│       │
│       ├── mcp_servers/               # MCP server implementations  ✅ all scaffolded
│       │   ├── filesystem/            # ✅ read/write/list/search
│       │   ├── websearch/             # ✅ Brave + Tavily with fallback
│       │   ├── git_server/            # ✅ status/log/diff
│       │   ├── code_exec/             # ✅ sandboxed Python + pytest runner
│       │   ├── database/              # ✅ SQLite key-value store
│       │   └── docs/                  # ✅ HTML fetch + PyPI lookup
│       │
│       ├── ui/
│       │   ├── cli.py                 # ✅ Rich/Typer CLI with Halloween theming
│       │   └── web/
│       │       ├── app.py             # ✅ FastAPI + WebSocket streaming
│       │       ├── static/
│       │       └── templates/
│       │           └── index.html     # ✅ dark-mode Halloween UI
│       │
│       └── utils/
│           ├── json_utils.py          # ✅ extract_json() — 4-strategy LLM JSON parser
│           ├── logging.py             # ✅ structlog configuration
│           └── themes.py              # ✅ Halloween Rich theming
│
├── tests/
│   ├── test_agents/
│   │   ├── test_jack.py               # ✅
│   │   ├── test_jack_phase2.py        # ✅ planner/router/full orchestration flow
│   │   ├── test_zero.py               # ✅ Phase 3: navigation flow + orthodox MCP smoke test
│   │   ├── test_sally.py              # ✅ Phase 4: all three intent paths + MCP smoke test
│   │   ├── test_oogie.py              # ✅ Phase 5: research + compare + LLM-fallback paths
│   │   ├── test_validators.py         # ✅ Phase 6: each validator + consensus + failure isolation
│   │   └── test_mayor.py              # ✅ Phase 8: digest + diff + format + multi-format output
│   ├── test_subagents/
│   │   ├── test_parallel.py           # ✅ parallel execution + exception isolation
│   │   ├── test_file_explorer.py      # ✅ Phase 3
│   │   ├── test_dependency.py         # ✅ Phase 3
│   │   ├── test_context.py            # ✅ Phase 3
│   │   ├── test_codegen.py            # ✅ Phase 4
│   │   ├── test_scaffold.py           # ✅ Phase 4
│   │   ├── test_refactor.py           # ✅ Phase 4
│   │   ├── test_search.py             # ✅ Phase 5: toolkit + LLM fallback paths
│   │   ├── test_summary.py            # ✅ Phase 5
│   │   ├── test_compare.py            # ✅ Phase 5
│   │   ├── test_lint.py               # ✅ Phase 6
│   │   ├── test_test_runner.py        # ✅ Phase 6
│   │   ├── test_security.py           # ✅ Phase 6
│   │   ├── test_formatter.py          # ✅ Phase 8
│   │   ├── test_diff.py               # ✅ Phase 8: difflib determinism + no-change short-circuit
│   │   └── test_status.py             # ✅ Phase 8: counts from state, empty-workflow fast path
│   ├── test_core/
│   │   ├── test_types.py              # ✅
│   │   ├── test_config.py             # ✅
│   │   └── test_json_utils.py         # ✅ all 8 extraction strategies tested
│   └── test_mcp_servers/
│       ├── test_filesystem.py         # ✅
│       ├── test_filesystem_client.py  # ✅ stdio MCP client
│       └── test_filesystem_tools.py   # ✅ pure tool functions + access gating
│
└── docs/
    ├── architecture.md
    ├── learning_guide.md
    ├── mcp_guide.md
    └── agents/
        └── jack.md
```

---

## 🚀 Quick Start

```bash
# Clone & install
git clone https://github.com/skazler/skellington.git
cd skellington
pip install -e ".[dev]"

# Configure API keys
cp .env.example .env
# Edit .env with your API keys

# Run the CLI
skellington "research the best Python async libraries and scaffold a project using the top pick"

# Run the web UI
skellington web
```

---

## 🛠️ Configuration

Copy `.env.example` to `.env` and configure your providers:

```env
# LLM Providers (configure at least one)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...

# Default provider/model
DEFAULT_LLM_PROVIDER=anthropic
DEFAULT_LLM_MODEL=claude-opus-4-5

# Web Search
BRAVE_SEARCH_API_KEY=...
TAVILY_API_KEY=...

# Optional: Local models
OLLAMA_BASE_URL=http://localhost:11434
```

---

## 📚 Learning Guide

### ✅ Phase 1: Core Foundation — *complete*
- `core/types.py` — all Pydantic models: `Task`, `WorkflowState`, `AgentResponse`, `ConsensusResult`, `LLMConfig`
- `core/agent.py` — `BaseAgent` with tool registration and the observe→think→act loop
- `core/subagent.py` — `BaseSubAgent[T]` (generic typed) + `run_subagents_parallel()` via `asyncio.gather`
- `core/llm.py` — `AnthropicClient`, `OpenAIClient`, `LLMClientFactory` registry
- `core/config.py` — Pydantic Settings with per-agent model overrides, `populate_by_name=True`

### ✅ Phase 2: Jack — Orchestrator — *complete*
- `agents/jack.py` — full plan→route→delegate→synthesize flow
- `subagents/planner.py` — `PlannerSubagent` with `extract_json()` and graceful fallback
- `subagents/router.py` — `RouterSubagent` with agent name validation and fallback to `mayor`
- `utils/json_utils.py` — `extract_json()`: 4-strategy LLM JSON parser (direct → ```json fence → any fence → balanced brace scan)
- **Key fix:** `Orchestrator` injects `self` into Jack so `delegate()` reaches real specialist agents

### ✅ Phase 3: Zero + Filesystem MCP — *complete*
- `agents/zero.py` wired to `mcp_servers/filesystem/` (both direct `tools.py` and stdio `MCPFilesystemToolkit`)
- `FileExplorerSubagent`, `DependencySubagent`, `ContextSubagent` — all live with `fs=None` injection
- Navigation metadata published to `state.metadata["navigation"]` for downstream agents

### ✅ Phase 4: Sally the Builder — *complete*
- `agents/sally.py` with keyword-heuristic intent routing: `codegen` / `scaffold` / `refactor`
- `CodeGenSubagent`, `ScaffoldSubagent`, `RefactorSubagent` — pure structured-output; Sally owns all filesystem writes
- Works against both the in-process filesystem toolkit and the orthodox stdio MCP client
- Build metadata published to `state.metadata["builds"]`
- Side-quest fix: `NoDecode` + `field_validator` on `FILESYSTEM_ALLOWED_PATHS` so comma-delimited env values work

### ✅ Phase 5: Oogie + Web Search — *complete*
- `agents/oogie.py` with intent routing: `research` (default) vs `compare` (keyword: `vs`, `versus`, `compare`, `pros and cons`, ...)
- `SearchSubagent` accepts a `search=` toolkit (default: `mcp_servers/websearch/tools.py` → Brave then Tavily). Toolkit failure (no API key, network error) silently falls back to LLM-imagined results so the pipeline always runs
- `SummarySubagent` distills the top N hits in sequence; `CompareSubagent` runs only when intent is `compare` and at least 2 items are extractable from `task.context['items']` or by splitting on `vs`/`versus`
- Research findings published to `state.metadata["research"]` for downstream agents (Mayor) to consume
- `mcp_servers/websearch/server.py` refactored into a thin stdio adapter over `tools.py` (mirrors the filesystem split)
- 🔜 **Next:** wire `fetch_url` into the pipeline so Oogie summarizes full page content, not just snippets; add an orthodox MCP client (`websearch/client.py`) like `MCPFilesystemToolkit`

### ✅ Phase 6: Multi-Agent Consensus (Lock/Shock/Barrel) — *complete*
- `Lock` → `LintSubagent`, `Shock` → `TestSubagent`, `Barrel` → `SecuritySubagent` — each validator is thin, subagent does the analysis
- Each `run()` produces a `ValidationVerdict` packed in `AgentResponse.metadata["verdict"]`
- `ValidatorCoordinator.validate()` runs all three in parallel via `run_subagents_parallel`; majority rules (2/3 = pass)
- Exception isolation: a broken validator becomes a failed verdict — the panel keeps voting
- Consensus published to `state.metadata["validation"]`
- 🔜 Next: wire `TestSubagent`/`Shock` to the `code_exec` MCP server for real pytest runs

### 🔜 Phase 7: Streaming Web UI
- Enhance the WebSocket handler in `ui/web/app.py` with per-step agent updates
- Show which agent is active in the dark-mode UI

### ✅ Phase 8: Mayor + Reporting — *complete*
- `agents/mayor.py` collects findings from `state.metadata` (navigation/builds/research/validation) and weaves them into one digest
- `StatusSubagent` — counts come from the workflow state itself (deterministic); LLM only writes the narrative + next-steps. Empty workflow short-circuits without a single LLM call
- `DiffSubagent` — unified-diff text comes from `difflib`, not the LLM (LLMs hallucinate diffs). Identical before/after short-circuits. LLM only narrates the change in one sentence
- `FormatSubagent` — `extract_json` + sensible fallbacks; respects `task.context['format']` (markdown/html/json/cli)
- Mayor publishes its rendered report to `state.metadata["reports"]` so the web UI can re-render without re-running the LLM
- Pattern note: each subagent uses the LLM for *judgement* (narrative, summary) and pure-Python for *facts* (counts, diff text). Cuts hallucination surface area dramatically

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=skellington

# Run specific test suite
pytest tests/test_agents/
```

---

## 🤝 Contributing

This is a learning project — experiments, wild ideas, and Halloween puns all welcome.

---

## 📄 License

MIT — go build something spooky 🎃