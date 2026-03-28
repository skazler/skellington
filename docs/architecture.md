# Skellington Architecture

## System Overview

```
User Request
     │
     ▼
┌─────────────────────┐
│   CLI / Web UI      │  Entry point
└──────────┬──────────┘
           │
     ┌─────▼──────┐
     │ Orchestrator│  Workflow state management
     └─────┬──────┘
           │
     ┌─────▼──────┐
     │    Jack    │  🎃 Routes, plans, delegates
     └─────┬──────┘
           │ delegates via AgentRegistry
    ┌──────┼──────┬──────────┬──────────┐
    ▼      ▼      ▼          ▼          ▼
  Sally  Oogie  Zero   Lock/Shock/   Mayor
                        Barrel
    │      │      │          │          │
    ▼      ▼      ▼          ▼          ▼
Subagents (17 total, run in parallel where possible)
    │      │      │          │
    ▼      ▼      ▼          ▼
MCP Servers (6 servers, each a separate process)
```

## Key Design Patterns

### 1. Orchestrator Pattern (Jack)
Jack uses a planner subagent to decompose requests, a router subagent to assign
tasks, and the Orchestrator class to manage delegation and state across the workflow.

### 2. Subagent Decomposition
Each main agent spawns focused subagents for specific atomic tasks. Subagents:
- Have a single responsibility
- Return typed Pydantic models
- Can run in parallel via `asyncio.gather`

### 3. Multi-Agent Consensus (Lock/Shock/Barrel)
Three validators review code independently and in parallel. Majority voting
(2/3) determines pass/fail. This surfaces more issues than a single reviewer.

### 4. MCP Server Architecture
Each MCP server runs as a separate stdio process. Agents communicate with them
via the MCP SDK. This isolation means:
- Servers can be swapped without changing agent code
- Code execution is sandboxed in its own process
- Different servers can use different languages/runtimes

### 5. Multi-Provider LLM Abstraction
`LLMClientFactory` returns the right client based on config. Agents never
import `anthropic` or `openai` directly — only `LLMClient`.

## Data Flow

```
Task (Pydantic) → Agent.run() → LLM call(s) → Tool calls → AgentResponse
                                                    │
                                              MCP Server tools
                                            (filesystem, search, etc.)
```

## State Management

`WorkflowState` holds the entire state of a workflow:
- All tasks and their statuses
- Full message history
- Which agent is currently active
- Metadata for the UI to render

State is passed by reference through the agent call chain so all agents
share the same view of the workflow.