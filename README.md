# Skellington

*Multi-agent orchestration system. A coordinating agent decomposes incoming requests, routes subtasks to specialist agents, and synthesizes their output into a single response — streamed live over WebSockets.*

```bash
skellington "research the top Python async libraries and scaffold a demo project"
```

*A personal learning project. Not production-ready, not affiliated with any LLM provider.* [![CI](https://github.com/skazler/skellington/actions/workflows/ci.yml/badge.svg)](https://github.com/skazler/skellington/actions/workflows/ci.yml)

---

## Agents

Each agent is a specialist construct, internally designated after characters from *The Nightmare Before Christmas*. The names are identifiers, not flavor — they map directly to classes in [`src/skellington/agents/`](src/skellington/agents/).

| Designation | Role | Function |
| :--- | :--- | :--- |
| **Jack** | Orchestrator | Decomposes requests, routes subtasks, synthesizes results |
| **Sally** | Builder | Code generation, scaffolding, refactoring |
| **Oogie** | Researcher | Web search, multi-source summarization, RAG |
| **Zero** | Navigator | Codebase exploration, dependency mapping, context assembly |
| **Lock / Shock / Barrel** | Validators | Parallel lint / test / security review, resolved by 2/3 consensus |
| **Mayor** | Reporter | Formats, diffs, and summarizes final output |

---

## Quick Start

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

## Architecture

```mermaid
flowchart LR
    User([User request]) --> Entry["CLI / Web UI"]
    Entry --> Orchestrator["Orchestrator<br/>AgentRegistry + WorkflowState"]
    Orchestrator -.->|"typed events<br/>workflow.start → result.final"| Entry
    Orchestrator --> Jack

    subgraph JackLoop ["Jack — plan / route / synthesize"]
        direction LR
        Jack[Jack] --> Planner[PlannerSubagent] --> Router[RouterSubagent] --> Jack
    end

    Jack -- delegate --> Specialists["Specialist agents<br/>Sally · Oogie · Zero ·<br/>Lock/Shock/Barrel · Mayor"]
    Specialists -- results --> Jack
    Jack --> Result([Final response])

    style JackLoop fill:#f8fafc,stroke:#94a3b8,color:#1e293b

    classDef core fill:#1e293b,stroke:#38bdf8,color:#e0f2fe,font-weight:bold;
    classDef specialist fill:#334155,stroke:#94a3b8,color:#f1f5f9,font-weight:bold;
    classDef io fill:#ffffff,stroke:#334155,color:#334155,stroke-dasharray: 4 2;

    class User,Entry,Result io;
    class Orchestrator,Jack,Planner,Router core;
    class Specialists specialist;
```

Each specialist owns its own subagents and, for Sally/Zero/Oogie, an MCP toolkit:

```mermaid
flowchart TB
    subgraph SallyG ["Sally — Builder"]
        Sally[Sally] --> CodeGen[CodeGen]
        Sally --> Scaffold[Scaffold]
        Sally --> Refactor[Refactor]
    end

    subgraph OogieG ["Oogie — Researcher"]
        Oogie[Oogie] --> Search[Search]
        Oogie --> Summary[Summary]
        Oogie --> Compare[Compare]
    end

    subgraph ZeroG ["Zero — Navigator"]
        Zero[Zero] --> FileExplorer[FileExplorer]
        Zero --> Dependency[Dependency]
        Zero --> Context[Context]
    end

    subgraph ValG ["Lock / Shock / Barrel — Validators (2/3 consensus)"]
        ValCo[ValidatorCoordinator] --> Lock["Lock → Lint"]
        ValCo --> Shock["Shock → Test"]
        ValCo --> Barrel["Barrel → Security"]
    end

    subgraph MayorG ["Mayor — Reporter"]
        Mayor[Mayor] --> Format[Format]
        Mayor --> Diff[Diff]
        Mayor --> Status[Status]
    end

    subgraph MCPBox ["MCP toolkits (tools.py + server.py)"]
        FS[(filesystem)]
        WS[(websearch)]
        ExtraMCP[("git_server · code_exec ·<br/>database · docs<br/>standalone, not yet wired in")]
    end

    Sally -.-> FS
    Zero -.-> FS
    Oogie -.-> WS

    style SallyG fill:#f8fafc,stroke:#94a3b8,color:#1e293b
    style OogieG fill:#f8fafc,stroke:#94a3b8,color:#1e293b
    style ZeroG fill:#f8fafc,stroke:#94a3b8,color:#1e293b
    style ValG fill:#f8fafc,stroke:#94a3b8,color:#1e293b
    style MayorG fill:#f8fafc,stroke:#94a3b8,color:#1e293b
    style MCPBox fill:#f8fafc,stroke:#94a3b8,color:#1e293b

    classDef specialist fill:#334155,stroke:#94a3b8,color:#f1f5f9,font-weight:bold;
    classDef validator fill:#334155,stroke:#ef4444,color:#fecaca,font-weight:bold;
    classDef sub fill:#ffffff,stroke:#cbd5e1,color:#1e293b;
    classDef mcp fill:#0f172a,stroke:#10b981,color:#6ee7b7;

    class Sally,Oogie,Zero,Mayor specialist;
    class ValCo validator;
    class CodeGen,Scaffold,Refactor,Search,Summary,Compare,FileExplorer,Dependency,Context,Lock,Shock,Barrel,Format,Diff,Status sub;
    class FS,WS,ExtraMCP mcp;
```

**Plan → route → delegate → synthesize.** Jack runs a `PlannerSubagent` to decompose the request into ordered steps. A `RouterSubagent` assigns each step to a specialist, in parallel. Each specialist executes via its own subagents. Jack synthesizes the collected results into the final response.

Every transition emits a typed event — `workflow.start`, `plan.created`, `route.decided`, `agent.start/complete/fail`, `synthesis.start`, `result.final` — consumed by the web UI over WebSockets.

```python
async def on_event(event: dict) -> None:
    print(event)

state = await Orchestrator(on_event=on_event).run("your request")
```

**Six MCP servers ship in-tree:** `filesystem`, `websearch`, `git_server`, `code_exec`, `database`, `docs`. Each is a pair — a pure-Python `tools.py` for in-process use, a stdio `server.py` for orthodox MCP clients. Agents accept a `fs=` / `search=` kwarg so tests pass mock toolkits the same way production passes real ones.

**Operating principles:**

- **LLM for judgement, Python for facts.** Diffs come from `difflib`; counts from `WorkflowState`. The LLM only narrates.
- **Skill-per-file.** Specialist agents live in packages where each tool is its own file under `skills/`. Adding a skill = one new file + one line in `__init__.py`.
- **Graceful degradation.** No search API key → Oogie falls back to LLM-imagined results. Empty workflow → short-circuit without an LLM call.
- **Consensus with isolation.** Lock/Shock/Barrel run in parallel; a crashing validator is a failed vote, not a panel-wide failure.

---

## Configuration

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

## Layout

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

## Testing

```bash
pytest                        # full suite (158 tests)
pytest tests/test_agents/     # one layer
pytest -k mayor               # one agent
```

---

## License

MIT.
