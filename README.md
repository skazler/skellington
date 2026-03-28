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
┌─────────────────────┐
│   Jack Skellington  │  ← Orchestrator
│  (Orchestrator)     │    Routes, plans, manages state
└──────────┬──────────┘
           │ delegates to
    ┌──────┴──────┬──────────┬──────────┬──────────┐
    ▼             ▼          ▼          ▼          ▼
  Sally         Oogie      Zero    Lock/Shock/   Mayor
 (Builder)   (Researcher) (Nav)    Barrel (Val) (Report)
    │             │          │          │          │
    ▼             ▼          ▼          ▼          ▼
 subagents    subagents   subagents  subagents  subagents
    │             │          │          │
    ▼             ▼          ▼          ▼
 MCP Tools    MCP Tools   MCP Tools  MCP Tools
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
│       ├── core/                      # Foundation layer
│       │   ├── agent.py               # Base Agent class
│       │   ├── subagent.py            # Base SubAgent class
│       │   ├── orchestrator.py        # Agent routing & workflow engine
│       │   ├── llm.py                 # Multi-provider LLM abstraction
│       │   ├── memory.py              # SQLite-backed agent memory
│       │   ├── config.py              # Settings & configuration
│       │   └── types.py               # Shared types/models (Pydantic)
│       │
│       ├── agents/                    # Main character agents
│       │   ├── jack.py                # Jack Skellington — Orchestrator
│       │   ├── sally.py               # Sally Claus — Builder
│       │   ├── oogie.py               # Oogie Boogie — Researcher
│       │   ├── zero.py                # Zero — Navigator
│       │   ├── validators.py          # Lock/Shock/Barrel — Validators
│       │   └── mayor.py               # The Mayor — Reporter
│       │
│       ├── subagents/                 # Specialized subagents
│       │   ├── planner.py
│       │   ├── router.py
│       │   ├── codegen.py
│       │   ├── refactor.py
│       │   ├── scaffold.py
│       │   ├── search.py
│       │   ├── summary.py
│       │   ├── compare.py
│       │   ├── file_explorer.py
│       │   ├── dependency.py
│       │   ├── context.py
│       │   ├── lint.py
│       │   ├── test_runner.py
│       │   ├── security.py
│       │   ├── formatter.py
│       │   ├── diff.py
│       │   └── status.py
│       │
│       ├── mcp_servers/               # MCP server implementations
│       │   ├── filesystem/
│       │   ├── websearch/
│       │   ├── git_server/
│       │   ├── code_exec/
│       │   ├── database/
│       │   └── docs/
│       │
│       ├── ui/
│       │   ├── cli.py                 # Rich/Typer CLI (spooky theme 🎃)
│       │   └── web/
│       │       ├── app.py             # FastAPI server
│       │       ├── static/
│       │       └── templates/
│       │
│       └── utils/
│           ├── logging.py
│           └── themes.py              # Halloween theming
│
├── tests/
│   ├── test_agents/
│   ├── test_subagents/
│   ├── test_core/
│   └── test_mcp_servers/
│
└── docs/
    ├── architecture.md
    ├── learning_guide.md
    ├── mcp_guide.md
    └── agents/
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

Work through these phases in order:

### Phase 1: Core Foundation
- Understand `core/types.py` — the shared data models
- Study `core/agent.py` — the base agent contract
- Study `core/subagent.py` — how subagents differ from agents
- Implement `core/llm.py` — abstract away the LLM providers

### Phase 2: First Agent (Jack)
- Implement `agents/jack.py` using the orchestrator pattern
- Build `subagents/planner.py` and `subagents/router.py`
- Learn tool-use loops and state management

### Phase 3: MCP Servers
- Build `mcp_servers/filesystem/` from scratch
- Understand the MCP protocol (see `docs/mcp_guide.md`)
- Connect Zero to use your new MCP server

### Phase 4: Multi-Agent Consensus
- Implement Lock, Shock & Barrel as voting subagents
- Study debate and critic patterns

### Phase 5: RAG & Research
- Build the web search MCP server
- Implement Oogie's research pipeline
- Learn embedding and retrieval patterns

### Phase 6: UI Layer
- Build the Rich CLI with theming
- Add FastAPI web server
- Stream agent output to the UI

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