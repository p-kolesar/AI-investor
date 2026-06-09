# Ideas backlog

Status: **draft** · Last verified: 2026-06-09

A scratchpad for ideas not yet committed to. Nothing here is decided or built —
it's a place to capture a concept while it's fresh so it isn't lost. Promote an
idea to a real doc / ADR / issue when it graduates from "interesting" to
"we're doing this".

Each idea: a short pitch, the shape of it, open questions. Keep it skimmable.

---

## 1. Agent–human GitHub workflow for new features

> **Status: BUILT (2026-06-09).** Promoted to a real guide —
> [guides/feature-workflow.md](guides/feature-workflow.md) — with four workflows
> under `.github/workflows/feature-*.yml` and a `feature_request.yml` issue
> template. The notes below are the original pitch, kept for context.

**Pitch:** Drive a feature from a GitHub issue through spec-review, build, QA,
and merge using Claude agents at each stage, with humans at just two gates. The
issue *is* the spec; labels are the state; PR comments are the conversation.

**Core idea — two decoupled loops:**

- **Pipeline state machine** (issue labels) — runs *once*, forward:
  `new-feature → needs-spec-fixes → ready-to-build → in-qa → qa-passed`.
- **PR revision loop** (lives on the open PR, branch stays alive) — runs *as
  many times as you want*, and never touches the issue labels.

**The stages:**

1. **Spec-quality agent.** Fires on `issues: labeled` (`new-feature`). Evaluates
   the description, posts suggested improvements as a comment, sets
   `needs-spec-fixes`. Human edits the issue.
2. **Build gate (human).** Human re-reads the improved spec and applies
   `ready-to-build`. *The label is the approval* — no blocking job.
3. **Dev agent.** Fires on `ready-to-build`. **Single agent**, routed by scope
   labels (`area:backend` / `area:frontend` / `area:infra`) telling it which
   subtree to touch. Opens a **draft PR**; backend changes must pass `pytest`
   (a gate *inside* the dev stage, not a separate stage) before the PR is marked
   ready-for-review.
4. **QA agent.** Fires when the PR leaves draft (`pull_request: ready_for_review`)
   or on `in-qa`. Posts a **structured PR review**: each acceptance criterion
   from the spec → ✅/❌ + evidence (test name, line, screenshot).
   - On fail → label `needs-fixes`, `@`-mention the dev agent, loop back. **Cap
     the loop** (e.g. 2 round-trips → `needs-human`) so two agents don't ping-pong.
   - On pass → `qa-passed`, request human review.
5. **Merge gate (human).** Human-approved PR to `main`. **An agent never merges
   `main` unattended.**

**Iterating on a PR without restarting the pipeline (the key trick):**

Once a PR is open, the branch is a long-lived workspace and the PR review
threads are the worklist. A human review comment doesn't rewind anything — it
adds an item to the worklist and pokes the dev agent to push another commit to
the *same* branch.

- Human leaves **inline review comments** (attached to code, threaded,
  individually resolvable) — not loose issue comments.
- Trigger re-fires the dev agent on the same PR: `@claude` mention, a `revise`
  label, or a "Request changes" review.
- Agent scopes itself to **unresolved threads only** (read via GraphQL
  `reviewThreads { isResolved }`), addresses each, pushes to the existing
  branch, re-runs `pytest`, replies under each thread. **Touch only what a
  comment asks for** — same "Surgical Changes" rule as the repo guide.
- Human clicks "Resolve conversation" as the done-signal. Per-comment
  granularity: fix three notes now, leave two for discussion, no restart.

**The one distinction that makes it work:** *review comment = scalpel on the
open PR* (cheap, stay on branch) vs *re-labeling the issue `needs-spec-fixes` =
the only thing that rewinds the pipeline* (use when the requirements themselves
were wrong; consider a `spec-change` label to mark this explicitly).

**Mechanics / primitives:**

| Primitive | Role |
| --- | --- |
| Labels | The state; `labeled` events are the cleanest triggers |
| Comments / PR review threads | The human↔agent message bus; resolvable per-thread |
| `workflow_dispatch` | Manual button / fallback to kick a stage by hand |
| Draft → ready-for-review | Free signal to trigger QA |
| Claude Code GitHub Action | Runs the agents — posts comments, pushes branches, opens PRs |
| Environment + required reviewer | (Unused for now) the only *blocking* human gate, if a stage ever needs one |

**Decided so far:** single dev agent + scope labels · label-as-approval build
gate · human-approved PR to `main`.

**Open questions:**

- Does QA re-run fully on every PR push, or only re-validate the criteria
  touched by the changed threads? (Full re-run is simplest for a demo.)
- Where do acceptance criteria live so the QA agent can check them — a fixed
  section in the issue template?
- How does the dev agent know the feature is "done enough" to open the PR vs
  keep iterating in draft?
