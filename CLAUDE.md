# CLAUDE.md

Conventions and non-obvious patterns for working in this repo. The [README.md](README.md) covers the user-facing pitch; this file is what you need to ship code here without re-deriving the same lessons every session.

## Repo shape (one-paragraph orientation)

Multi-agent orchestrator. **Jack** plans + routes; specialist agents (**Sally**/builder, **Oogie**/researcher, **Zero**/navigator, **Mayor**/reporter, **Lock/Shock/Barrel**/validators) own subagents and skills. Code lives in [src/skellington/](src/skellington/); tests in [tests/](tests/) one-file-per-module. Pydantic v2 throughout. Async-first.

## Patterns to follow

- **Skill-per-file.** Specialist agents (Sally, Oogie, Mayor) live in packages where each registered tool gets its own file under `skills/`, exporting `func` and `SCHEMA`. Adding a skill = one new file + one line in `skills/__init__.py`. Do not put multiple tools in one file.
- **LLM for judgement, Python for facts.** Diffs come from `difflib`; counts from `WorkflowState`. The LLM only narrates. When you write a new subagent, ask "could a deterministic Python function compute this?" before reaching for the LLM.
- **Toolkit injection.** Agents accept a `fs=` / `search=` kwarg that defaults to the in-process module (e.g. `mcp_servers.filesystem.tools`). Pass an `MCPFilesystemToolkit` instead and nothing else changes. Tests pass mock toolkits the same way. Preserve this — don't import the default directly inside method bodies.
- **Event-bus over polling.** The orchestrator emits typed events; callback errors are swallowed by design so a broken UI can't crash a workflow. Don't add `raise` inside event callbacks.
- **Graceful degradation.** No API key → fall back (Oogie → LLM-imagined results). Empty workflow → short-circuit without an LLM call. Match this style for new external dependencies.
- **Model registry + prompt fragments.** Model capabilities live in [src/skellington/core/models.py](src/skellington/core/models.py) as `ModelCard` flags. Prompt fragments in [src/skellington/prompts/fragments/](src/skellington/prompts/fragments/) are selected by flag, not by model name. To add a model: one entry in `MODELS`. To add an adaptation: one flag + one branch in `assemble.py` + one `.md` fragment. Never key fragments by model id.
- **Request shaping is also flag-gated.** `LLMConfig.prefer_thinking` and `response_format="json"` are opt-ins; the LLM clients call `get_model_card()` and only honor them if the model supports them. Mirror this pattern for any new capability — opt-in on the config, gate by flag in the client.

## Anti-patterns (don't do these)

- **Don't write a fragment per model family** (`opus.md`, `gemini.md`). Fragments exist to *compensate for a specific capability gap*. The flag is what tells you whether the gap applies.
- **Don't bypass the toolkit interface.** Calling `Path(...).write_text(...)` directly inside an agent skips the allowed-roots check enforced by [mcp_servers/filesystem/tools.py](src/skellington/mcp_servers/filesystem/tools.py).
- **Don't put `output_dir` and `path` and `dest` and `dir` as separate context keys for the same thing.** Sally's `_resolve_output_dir` accepts both `path` and `output_dir` only because of legacy mismatch; don't extend that pattern elsewhere.
- **Don't add tiers as a load-bearing abstraction.** Tiers (`fast`, `reasoning_heavy`) are a UX shortcut layer; rules and behavior branch on capability flags, never on tier strings. (See the design discussion in commit history if you need the reasoning.)

## Where the gotchas live

- **`extract_json`** ([utils/json_utils.py](src/skellington/utils/json_utils.py)) — 4-strategy parser because LLMs can't reliably return JSON. Path #1 is direct `json.loads`, so native-JSON responses are already fast; don't add a separate "strict" path unless you're threading model cards down to all callers.
- **`AgentResponse` field names** — `agent` (not `agent_name`) and `content` (not `message`). Pydantic v2 will raise loudly if you mistype, but the historical Sally bug had wrong field names for a while; double-check when constructing one.
- **`get_settings()` is `lru_cache`d.** Use `get_settings.cache_clear()` in tests after monkeypatching env vars or you'll get a stale `Settings`.
- **Filesystem allowed-roots** — `tools._ensure_allowed` resolves paths against `filesystem_allowed_paths`. In tests, use the `allowed_tmp_path` fixture from [tests/conftest.py](tests/conftest.py), don't write bare filenames.
- **structlog kvs don't land in stdlib `LogRecord.getMessage()`.** When testing log output, assert on `capsys.readouterr().out` rather than `caplog.records[*].getMessage()`.

## Testing

- `pytest -q` — full suite (~124 tests, all should pass)
- `pytest tests/test_agents/` — one layer
- `pytest -k mayor` — one agent
- Mock LLMs via `tests/conftest.py::make_mock_llm` — returns a MagicMock with `provider` and an `AsyncMock` `complete`.
- Async tests work without `@pytest.mark.asyncio` only because `asyncio_mode = "auto"` is set in `pyproject.toml`. Don't change that.

## Cost-optimization levers (currently in the codebase)

Each workflow makes ~5–10 LLM calls (planner + router-per-step + each specialist + synthesis). The big knobs:

- **Per-subagent models** — `PLANNER_MODEL`, `ROUTER_MODEL` env vars route the highest-frequency subagents to cheaper models without changing main-agent models. See `Settings.get_model_for_subagent` in [core/config.py](src/skellington/core/config.py).
- **Anthropic prompt caching** — `AnthropicClient` automatically wraps the system block with `cache_control: ephemeral` when the model's `ModelCard` has `supports_prompt_caching=True`. ~90% discount on cached tokens after the first call in the 5-minute window. No user opt-in required.
- **Router keyword short-circuit** — `RouterSubagent` skips the LLM entirely for unambiguous routes (e.g. "write code" → sally). Conservative list in [subagents/router.py:_KEYWORD_ROUTES](src/skellington/subagents/router.py). Add patterns only when they're strong/unambiguous; over-eager keywords mis-route.
- **Workflow-level dedup** — `Orchestrator(cache_workflows=True)` enables an in-process LRU on the request string (whitespace + case normalized). Off by default. Cap via `cache_size` kwarg. Only successful workflows are cached.
- **Anthropic Batch API primitive** — `AnthropicBatchClient` in [core/batch.py](src/skellington/core/batch.py) wraps `messages.batches` for 50%-off bulk processing. 24h SLA. Gated by `ModelCard.supports_batch_api`. Submission preserves order; `submit_and_wait()` is the synchronous-style convenience. Example:

  ```python
  from skellington.core.batch import AnthropicBatchClient
  from skellington.core.types import LLMConfig, Message, MessageRole

  client = AnthropicBatchClient()
  calls = [
      ([Message(role=MessageRole.USER, content=q)], LLMConfig(model="claude-haiku-4-5-20251001"))
      for q in many_questions
  ]
  responses = await client.submit_and_wait(calls, poll_interval_s=60)
  ```

  Use for backlogs, nightly analysis, bulk scoring — not realtime. Integrating it into the realtime `Orchestrator` is deliberately deferred: the natural batching boundary (e.g. "batch all planner calls across requests") is opinionated and use-case-specific; build a `BatchOrchestrator` wrapper only once that pattern is clear.

## Not implemented (deliberate)

- **Embedding-based dedup** — current dedup is exact-match (whitespace + case normalized). Semantic dedup via embeddings would require an embedding provider, vector storage, and a similarity threshold. Probably premature.

## Commit hygiene

- Don't add backwards-compat shims for renames — just rename and update callers.
- Don't add emojis unless asked. (README already has them; new files don't need them.)
- Don't write `// removed code` or `# was: ...` comments. Git history is the changelog.
