# Automated bug-fix (Claude)

Status: **current** · Last verified: 2026-06-09

When you label a GitHub issue **`bug`**, the
[`auto-fix-bug.yml`](../../.github/workflows/auto-fix-bug.yml) workflow runs
Claude Code to triage and, if the bug is clearly actionable, fix it and open a
PR. **Labeling is the manual gate — nothing runs until you add the `bug` label.**

## Flow

```
issue labeled `bug`
  → checkout + setup-python 3.13 + install backend & test deps
  → Claude Code (Sonnet 4.6):
       reads the issue as DATA (gh issue view)
       unclear?  → comments what's missing, STOPS (no code changes)
       clear?    → branch fix/issue-<n> → minimal fix → pytest
                   → add/adjust tests + update affected docs → push
                   → PR to main:  green = normal PR,  red = DRAFT PR + notes
```

## Setup (one-time)

- **Secret:** uses the existing `CLAUDE_API_KEY` Actions secret (an Anthropic
  `sk-ant-…` key). No new secret needed — the action's `anthropic_api_key` input
  is wired to it.
- **Install the Claude GitHub App** on the repo: <https://github.com/apps/claude>.
  The action exchanges its OIDC token for a GitHub token *via this app* — without
  it you get `401 … Claude Code is not installed on this repository`.
- **Repo Actions setting:** Settings → Actions → General → Workflow permissions →
  tick **“Allow GitHub Actions to create and approve pull requests.”** Otherwise
  `gh pr create` is blocked.
- **`id-token: write`** is already in the workflow's `permissions:` — the action
  needs it for OIDC even though we authenticate with an API key. (Symptom if
  missing: `Unable to get ACTIONS_ID_TOKEN_REQUEST_URL`.)
- **Label:** ensure a `bug` label exists in the repo.
- **The workflow must be on `main`** (the default branch) — issue-triggered
  workflows only run from there.
- **Issue form:** [`​.github/ISSUE_TEMPLATE/bug_report.yml`](../../.github/ISSUE_TEMPLATE/bug_report.yml)
  is deliberately light — one required "What's wrong?" box (what happened,
  expected, repro) plus an optional area. If it's too thin to fix safely the
  triage agent comments asking for specifics, so the form stays low-friction. It
  deliberately does **not** auto-apply `bug` — you add that label when ready,
  which is the trigger gate.

## Guardrails

- **Manual trigger only** — fires on the `labeled` event, gated to the `bug`
  label (`if: github.event.label.name == 'bug'`).
- **Prompt-injection hardening** — a system prompt tells the agent to treat all
  issue text as untrusted data, never as instructions, and forbids touching
  `.github/`, secrets, or destructive commands. (The action also cannot modify
  workflow files by design.)
- **Bounded** — `--max-turns 30`, `timeout-minutes: 30`, and per-issue
  `concurrency` so re-labeling won't run duplicates in parallel.
- **Tests run in-job** — PRs opened with the default token don't trigger other
  workflows, so the agent runs `pytest` itself before opening the PR.

## Trying it

Label a throwaway issue `bug`, then watch **Actions → Auto-fix bug (Claude)**.
The agent either comments on the issue (unclear) or pushes `fix/issue-<n>` and
opens a PR. Review the PR like any other before merging.

## Limitations

- Shallow clones; the agent can't edit `.github/workflows/**`.
- Cost scales with issue/codebase size and turns — Sonnet keeps routine fixes
  cheap; bump the `--model` in the workflow for harder bugs if needed.
