# Agent feature workflow (Claude)

Status: **current** · Last verified: 2026-06-09

An issue-driven pipeline that takes a **`new-feature`** issue through spec-review,
build, and QA to a human-approved PR — Claude agents do the work at each stage,
humans hold just two gates. Implements idea #1 in [../ideas.md](../ideas.md).

The design rests on **two decoupled loops**: the *pipeline* (issue labels, runs
once forward) and the *PR revision loop* (lives on the open PR, runs as often as
you like and never rewinds the pipeline).

## Flow

```
issue labeled `new-feature`            → feature-spec-review.yml
   → spec agent: sharpen criteria, apply area:* label(s), post "Likely change
     surface" + "Validation plan" (proposed tests OR alternative), set
     `needs-spec-fixes` (writes NO code)
human edits issue (incl. choosing which tests to keep/waive),
       applies `ready-to-build`                    ← GATE #1 (label = approval)
   → feature-build.yml
   → dev agent: scoped to area:* subtrees, branch feat/issue-<n>, smallest diff,
     implement the AGREED validation plan, open PR to main ("Closes #<n>" +
     criteria + "Files changed & why" + "Validation").
     normal PR = ready for QA;  draft PR = needs finishing (no QA)
PR ready-for-review                    → feature-qa.yml
   → QA agent: validate each criterion + gates (validation plan / scope / docs),
     post a PASS/FAIL checklist as a PR review (approve OR request-changes).
     NEVER merges.
human reviews ──┬─ apply `revise` (after QA fail or own comments)  → feature-revise.yml
                │     → dev agent: address UNRESOLVED review threads on the SAME
                │       branch, push, re-run pytest, reply under threads. Re-apply
                │       `revise` for another round.
                └─ approve + merge to main                          ← GATE #2 (human PR approval)
```

## Walkthrough — using it (for the human)

You touch the process at exactly **four moments**: file the request, approve the
spec, review the PR, and merge. Everything else is the agents. Step by step:

**1. File the feature request.**
GitHub → **Issues → New issue → "Feature request"**. Fill the one required box
("What do you want, and why?"). Optionally fill the per-area boxes if you already
know the split. Submit. *Nothing runs yet* — submitting does not start anything.

**2. Start the pipeline.**
When the request is worth pursuing, add the **`new-feature`** label to the issue.
Within a minute or two the **spec agent** comments with: a sharper version of the
criteria, a **"Likely change surface"** (the files it expects to touch), and a
**"Validation plan"** (the unit tests it proposes, or an alternative). It also
tags the issue with `area:*` labels. It writes no code.

**3. Sharpen and approve (GATE #1).**
Read that comment. Adjust anything by **editing the issue body or replying in a
comment** — especially the Validation plan: say which tests to keep, trim, or
waive. When you're happy, add the **`ready-to-build`** label. *That label is your
go-ahead* — the **dev agent** now branches `feat/issue-<n>`, implements the change
in the labeled areas only, and opens a **PR to `main`**.
   - A **normal PR** means it's done and ready for QA.
   - A **draft PR** means it couldn't finish (e.g. tests not green) — read the body
     for what remains.

**4. QA runs automatically.**
On a ready (non-draft) PR, the regression suite runs and the **QA agent** posts a
**PR review**: a PASS/FAIL checklist against each acceptance criterion, plus
scope/tests/docs gates. It either **approves** or **requests changes**. It never
merges.

**5. Review the PR — you have three moves:**
   - **Happy?** Approve and **merge to `main`** yourself (GATE #2). Done.
   - **Want tweaks?** Leave **inline review comments** on the code, then add the
     **`revise`** label. The dev agent addresses *only* your unresolved comments on
     the same branch and replies under each. Click "Resolve conversation" on the
     ones you're satisfied with; re-apply `revise` for another round. Repeat as
     often as needed — this never restarts the pipeline.
   - **Realise the spec itself was wrong?** Don't use `revise`. Edit the issue and
     re-apply `needs-spec-fixes` / `new-feature` — that's the only thing that
     rewinds to the spec stage.

**6. Merge.** When the PR is right and approved, merge it. The issue closes via the
PR's "Closes #<n>".

### Who applies which label

| Label | Applied by | Effect |
| --- | --- | --- |
| `new-feature` | **you** | Starts the spec agent |
| `area:backend` / `area:frontend` / `area:infra` | spec agent (you can adjust) | Scopes the dev agent |
| `needs-spec-fixes` | spec agent | Marks "spec not build-ready yet" (no effect on its own) |
| `ready-to-build` | **you** (GATE #1) | Starts the dev agent + PR |
| `revise` | **you** | Pokes the dev agent to address PR review comments |
| *(merge)* | **you** (GATE #2) | The final human approval — agents never merge |

> **Rule of thumb:** if it changes code or `main`, a human pressed the button
> (`ready-to-build`, `revise`, or Merge). Agents only act *between* those buttons.

## The two gates (and why)

- **Gate #1 — `ready-to-build`.** A human re-reads the agent-improved spec —
  including its **Validation plan**, deciding which tests to keep, trim, or waive —
  and applies the label; that *is* the build approval. No blocking job, fits the demo.
- **Gate #2 — merge.** A human approves and merges the PR. **No agent ever merges
  `main`.** QA can *approve* a PR, but the merge is yours.

## Iterating without restarting (the `revise` loop)

Once the PR is open, the branch is a long-lived workspace and the review threads
are the worklist. Leave **inline review comments**, then apply **`revise`**: the
dev agent addresses only the *unresolved* threads (read via the GraphQL
`reviewThreads { isResolved }` API), pushes to the same branch, and replies under
each. You click "Resolve conversation" as the done-signal. Re-apply `revise` as
many times as needed.

> **One distinction that matters:** a review comment + `revise` is a *scalpel on
> the open PR*. If the **requirements** were wrong, that's different — edit the
> issue and re-apply `needs-spec-fixes`/`new-feature`; that is the only thing that
> rewinds the pipeline.

**Note — QA failure does not auto-trigger the build.** By design the loop is
poked by a human applying `revise`, not auto-chained from QA. Auto-looping two
app-token workflows is fragile (GitHub's recursion guard) and a cost risk; the
manual poke is also the natural loop-cap.

## Precision funnel — each stage narrows the blast radius

The pipeline is designed so the *change surface* shrinks monotonically; nothing
re-widens it later:

```
free-text issue
  → SPEC:   testable criteria + area:* labels + "Likely change surface"
            (named file.py:symbol touch-points) + a Validation plan
  → BUILD:  smallest diff in only the labeled subtrees, no drive-by edits,
            PR body lists "Files changed & why" (every line traces to a criterion)
  → QA:     enforces it — out-of-area hunks, drive-by refactors, or over-testing
            are FAILs, not nits
  → REVISE: touches only the unresolved review threads
```

The two enforcement points that keep it honest: the **build agent** must justify
each file in the PR body, and the **QA agent** treats **scope creep as a defect**
(including tests added beyond the agreed plan).

## Tests are a spec-phase decision, not a blanket rule

Whether a feature gets unit tests — and which — is **decided before code**, with
a human in the loop. It is *mandatory to decide, optional to apply*:

1. **Spec** proposes a **Validation plan**: it spells out the backend impact and
   either a minimal, named set of `tests/unit/` tests (one per new behaviour,
   `test_<unit>_<expectation>`, covering *only* what the feature adds) **or** a
   concrete alternative validation if tests aren't warranted, with reasoning.
2. **You decide at the `ready-to-build` gate** — keep, trim, or waive the proposed
   tests (edit the issue or reply in a comment) before applying the label. You're
   never forced to carry a test you don't think earns its place in `main`.
3. **Build** implements *exactly* the agreed plan — the kept tests and no more
   (adding tests for pre-existing untested code is itself scope creep), or the
   agreed alternative if tests were waived.
4. A **deterministic pipeline step** (`Regression tests`, a plain `run: python -m
   pytest` — *not* the agent) is the **regression gate**: the full existing suite
   must be green regardless of the plan or area changed. In QA it runs *before* the
   agent (red ⇒ job fails, agent never runs); in build it runs *after* the agent as
   a backstop on the produced code. The **QA agent** then does only the
   *qualitative* check on a known-green suite — do the kept tests actually exercise
   the new behaviour, or was the agreed alternative performed.

**Scope note:** only the **backend** has an offline unit-test harness
(`tests/unit/`, `FakeBlobStore` — see [testing.md](testing.md)). **Frontend and
infra have no unit tests by design** (workshop app); their criteria are validated
by QA reading the diff. Agents are told never to scaffold a test harness for them.

## Setup (one-time)

Same prerequisites as the [automated bug-fix](automated-bug-fix.md) — they share
the action and secret:

- **Secret `CLAUDE_API_KEY`** (Anthropic `sk-ant-…`), wired to the action's
  `anthropic_api_key`.
- **Install the Claude GitHub App** (<https://github.com/apps/claude>) so the
  action's OIDC token exchanges for a GitHub token.
- **Settings → Actions → General → Workflow permissions →** tick *"Allow GitHub
  Actions to create and approve pull requests."*
- **Workflows must be on `main`** — issue/PR-triggered workflows only run from the
  default branch.
- **Create the labels** the pipeline uses:

  ```bash
  gh label create new-feature     --color 0e8a16 --description "Start the agent feature workflow"
  gh label create needs-spec-fixes --color fbca04 --description "Spec needs improvement before build"
  gh label create ready-to-build  --color 1d76db --description "Human-approved spec; build it (GATE #1)"
  gh label create revise          --color d93f0b --description "Poke the dev agent to address PR review threads"
  gh label create area:backend    --color 5319e7
  gh label create area:frontend   --color 5319e7
  gh label create area:infra      --color 5319e7
  ```

- **Issue form:** [`feature_request.yml`](../../.github/ISSUE_TEMPLATE/feature_request.yml)
  is light — one required "What do you want, and why?" box plus three **optional**
  per-area requirement boxes (backend / frontend / infra) you fill only if you
  already know the split. The **spec-review agent** sharpens it all into testable
  acceptance criteria (what QA later validates against) and applies one `area:*`
  label per area the feature touches. It deliberately does **not** auto-apply
  `new-feature` — a maintainer adds that, which is the trigger gate.

## Guardrails

- **Manual trigger gates** — spec-review needs `new-feature`, build needs
  `ready-to-build`, revise needs `revise`. Nothing autonomous starts itself.
- **Scope discipline** — the dev agent is told to stay inside the subtree named by
  the issue's `area:*` label; the revise agent is told to touch only what an
  unresolved thread asks for. Same "surgical changes" rule as CLAUDE.md.
- **Prompt-injection hardening** — every agent's system prompt treats issue/PR/
  review text as untrusted data, forbids `.github/` edits, secrets, destructive
  commands, and (for QA) any merge.
- **Bounded** — per-stage `--max-turns`, `timeout-minutes`, and per-issue/PR
  `concurrency`.
- **Tests run in-job** — PRs from the default token don't trigger a separate CI
  workflow, so the suite runs *inside* these jobs. The authoritative regression
  gate is a **deterministic `python -m pytest` step** in the build and QA jobs (QA:
  before the agent; build: after); the agent also runs `pytest` during build to
  iterate, and during revise.

## Files

| Stage | Workflow |
| --- | --- |
| Spec review | [`feature-spec-review.yml`](../../.github/workflows/feature-spec-review.yml) |
| Build | [`feature-build.yml`](../../.github/workflows/feature-build.yml) |
| QA | [`feature-qa.yml`](../../.github/workflows/feature-qa.yml) |
| Revise | [`feature-revise.yml`](../../.github/workflows/feature-revise.yml) |

## Limitations

- Shallow setup means agents can't edit `.github/workflows/**` (by design).
- Single dev agent, but it may carry several `area:*` labels and build all of
  them in one branch/PR. It works sequentially (not parallel per-area); a very
  large cross-area feature is still better split into separate issues.
- Cost scales with feature/codebase size and turns; Sonnet keeps it cheap, bump
  `--model` per stage for harder work.

## Troubleshooting (lessons from the first live run)

- **QA fails: `Workflow initiated by non-human actor: claude (type: Bot)`.**
  The build agent opens the PR as `claude[bot]`, so the QA trigger's actor is a
  bot, and `claude-code-action` blocks bot-initiated events by default. Fixed by
  `allowed_bots: "claude"` on the QA action — already set. (Only QA needs it; the
  other stages are triggered by labels a human applies.)
- **QA fails: `401 … workflow file must … have identical content to the version
  on the default branch`.** The Claude app refuses to issue a token unless the
  *running* QA workflow file is byte-identical to the copy on `main`, and
  `pull_request` runs use the PR **branch's** copy. So **don't edit the workflow
  files while a feature PR is open** — the open PR's branch falls behind `main` and
  QA can't validate. If it happens: rebase the PR branch onto `main` (and
  force-push) so the files match, or just close the PR and run a fresh feature
  (its branch is born from current `main`). In normal use this never triggers,
  because build branches are created from `main` after the workflows are stable.
- **QA can't `--approve` — "bot cannot approve its own PR".** Build and QA run as
  the same `claude[bot]`, and GitHub blocks self-approval. By design QA posts its
  verdict as a `--comment` review; **the human merge is Gate #2**, so no formal
  bot approval is needed or wanted.
