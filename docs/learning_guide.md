# Skellington Learning Guide

Work through these phases in order. Each builds on the previous.

---

## Phase 1: Core Foundation
**Files:** `src/skellington/core/`

**Goal:** Understand the data models and abstractions before writing agent logic.

1. Read `types.py` — every inter-agent message flows through these Pydantic models
2. Read `config.py` — learn Pydantic Settings for environment-driven configuration
3. Read `agent.py` — understand the BaseAgent contract and the tool-use loop
4. Read `subagent.py` — see how subagents differ: focused, typed, parallelizable
5. Run `pytest tests/test_core/` — all tests should pass before moving on

**Key concepts:** Pydantic v2, ABC pattern, asyncio, tool-use loop

---

## Phase 2: Your First Agent (Jack)
**Files:** `src/skellington/agents/jack.py`, `src/skellington/subagents/planner.py`, `src/skellington/subagents/router.py`

**Goal:** Implement a real orchestrator that plans and routes tasks.

1. Replace the stub `jack.py` with a full implementation:
   - Call `PlannerSubagent` to decompose the task
   - Call `RouterSubagent` to assign steps to agents
   - Use `Orchestrator.delegate()` for each step
2. Test with `skellington "explain the MCP protocol in 3 sentences"`

**Key concepts:** Orchestrator pattern, task decomposition, agent routing

---

## Phase 3: Filesystem MCP + Zero
**Files:** `src/skellington/mcp_servers/filesystem/`, `src/skellington/agents/zero.py`

**Goal:** Build a working MCP server and connect an agent to it.

1. The filesystem MCP server is already implemented — study it
2. Run it standalone: `python -m skellington.mcp_servers.filesystem.server`
3. Connect Zero to use it via `register_tool()`
4. Test: `skellington "explore the skellington source code structure"`

**Key concepts:** MCP protocol, stdio transport, tool registration

---

## Phase 4: Sally the Builder
**Files:** `src/skellington/agents/sally.py`, `src/skellington/subagents/codegen.py`

**Goal:** Generate real code and write it to disk using Sally + filesystem MCP.

1. Implement `CodeGenSubagent` to produce real Python code
2. Connect Sally to the filesystem MCP to write generated files
3. Test: `skellington "create a Python CLI tool that counts words in a file"`

**Key concepts:** Structured output, file writing, code generation patterns

---

## Phase 5: Oogie + Web Search
**Files:** `src/skellington/mcp_servers/websearch/`, `src/skellington/agents/oogie.py`

**Goal:** Real web search + RAG pipeline.

1. Get a Brave Search or Tavily API key
2. Test the websearch MCP server standalone
3. Connect Oogie's `SearchSubagent` to it
4. Build a simple RAG pipeline: search → fetch → summarize → synthesize
5. Test: `skellington "what are the best Python libraries for building MCP servers?"`

**Key concepts:** RAG, web search APIs, document chunking, context assembly

---

## Phase 6: Multi-Agent Consensus
**Files:** `src/skellington/agents/validators.py`, `src/skellington/core/subagent.py`

**Goal:** Understand parallel subagent execution and consensus voting.

1. Study `run_subagents_parallel()` in `subagent.py`
2. Implement `ValidatorCoordinator.validate()` fully
3. Connect it to the code_exec MCP server to run actual pytest
4. Test: ask Sally to write code, then validate it with Lock/Shock/Barrel

**Key concepts:** `asyncio.gather`, majority voting, critic pattern, parallel agents

---

## Phase 7: The Web UI
**Files:** `src/skellington/ui/web/`

**Goal:** Stream agent output to a real-time web interface.

1. Start the web UI: `skellington web`
2. Open http://localhost:8000
3. Enhance the WebSocket handler to stream intermediate steps
4. Add agent activity indicators (show which agent is currently running)

**Key concepts:** FastAPI, WebSockets, streaming, real-time UI

---

## Phase 8: Build Your Own MCP Server
**Goal:** Create a new MCP server for something Skellington doesn't have yet.

Ideas:
- GitHub MCP: search repos, read files from GitHub
- Calendar MCP: check your calendar for scheduling tasks
- Notion/Obsidian MCP: read your notes as knowledge base
- Weather MCP: real-time weather for context-aware responses

Follow the pattern in `mcp_servers/filesystem/server.py`:
1. Create a `Server` instance
2. Implement `list_tools()` and `call_tool()`
3. Register it with the relevant agent