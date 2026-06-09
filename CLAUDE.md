# AI Portfolio Manager — agent guide

Autonomous paper-trading demo: a Claude agent (Python Azure Function App) trades a
$100K paper portfolio every weekday; a React SPA shows it. Operational facts
(endpoints, secrets, deploy order) live in [README.md](README.md).

## Read these first — most tasks need them

- **[docs/](docs/README.md)** — the documentation map. Start at `docs/README.md`.
  - **[docs/data/](docs/data/README.md)** — the single most important reference.
    State is stored as **Parquet blobs in Azure Blob Storage**, written at runtime
    — it is *not* discoverable from the source tree. The schemas and the **data
    contract** (the invariants the code assumes) live only here. **Read it before
    touching anything storage-related.**
  - [docs/architecture/](docs/architecture/overview.md) — backend (agent loop),
    frontend, infrastructure.
  - [docs/decisions/](docs/decisions/README.md) — ADRs (why things are the way
    they are).
- **[tests/](tests/README.md)** — offline unit tests for the key backend modules.

## Working agreements (this repo)

- **Before changing storage / schemas:** read the
  [data contract](docs/data/README.md#the-data-contract-read-before-touching-storage).
  Storage is schema-on-write Parquet with **no migration framework** — a careless
  column change corrupts state silently.
- **Run the tests:** `backend/.venv/Scripts/python.exe -m pytest` (config in
  [pytest.ini](pytest.ini)). They run fully offline (no Azure / Finnhub / Claude).
  Add or adjust a test for any behaviour change. See
  [docs/guides/testing.md](docs/guides/testing.md).
- **Keep docs current (guideline, not a gate):** when you change behaviour,
  schemas, infra, or workflows, update the matching doc under `docs/` and bump its
  `Last verified:` date.
- The single frontend↔backend seam is
  [frontend-prod/src/api.js](frontend-prod/src/api.js) — keep it that way.

## Gotchas (each documented in full under docs/)

- The daily agent run is the Azure Functions **timer trigger**
  (`daily_agent_timer` in `backend/function_app.py`), **not** a GitHub cron.
- Agent mandate rules (≤15%/position, ≥10% cash floor, 5–10 positions) are
  **prompt-only — not enforced in code**. Don't assume they hold.
- Stored `portfolio.market_value` is the **last-trade** value, not live; the
  frontend re-marks positions with live quotes.

---

## General working principles

Behavioral guidelines to reduce common LLM coding mistakes.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
