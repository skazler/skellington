# 🎃👔 Jack Skellington — Orchestrator

> *"And I, Jack, the Pumpkin King, have grown so tired of the same old thing..."*
> *Until he discovered multi-agent AI orchestration.*

## Role

Jack is the **Orchestrator**. He never does specialist work himself — he plans,
delegates, and synthesizes. His two subagents do the thinking:

- **PlannerSubagent**: Decomposes the user's request into ordered steps
- **RouterSubagent**: Assigns each step to the right specialist agent

## Implementation Pattern

```
User Request
     │
     ▼
PlannerSubagent → Plan (ordered steps)
     │
     ▼
RouterSubagent → RoutingDecision (step → agent)
     │
     ▼
Orchestrator.delegate(step, agent) × N  ← parallel where possible
     │
     ▼
Synthesize results → Final response
```

## Key Learning Goals

- Orchestrator pattern: separate planning from execution
- Task decomposition: one complex goal → many atomic tasks
- Agent routing: semantic matching of task to capability
- Result synthesis: aggregating multiple agent outputs into a coherent response