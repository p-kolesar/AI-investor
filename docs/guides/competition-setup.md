# Blue / green competition setup

Status: **current** · Last verified: 2026-06-09

How to stand up **two standalone copies** of this app for a blue-vs-green
competition: separate repos, separate code, **one Azure subscription with one
resource group per team**, and **fully independent GitHub Actions**.

This repo is already parameterized for it — every resource name derives from
`uniqueString(resourceGroup().id)`, and the workflows read RG / base-name /
secrets from per-repo config. So this is mostly configuration, not code.

```
GitHub (personal account)        Azure (one subscription)
  aiinvestor-blue  ──Actions──►  rg-aiinvestor-blue   (Function App, Storage, SWA, …)
  aiinvestor-green ──Actions──►  rg-aiinvestor-green  (its own copy)
```

## What's per-team (no code edits — just config)

| Per-repo | Blue | Green |
| --- | --- | --- |
| Variable `AZURE_RESOURCE_GROUP` | `rg-aiinvestor-blue` | `rg-aiinvestor-green` |
| Variable `AZURE_BASE_NAME` | `aiinvblue` | `aiinvgreen` |
| Variable `AZURE_LOCATION` | `westeurope` | `westeurope` |
| Secret `AZURE_CREDENTIALS` | team-blue SP (RG-scoped) | team-green SP (RG-scoped) |
| Secrets `FINNHUB_API_KEY`, `CLAUDE_API_KEY` | blue's own keys | green's own keys |
| Claude GitHub App + `bug` label | on blue repo | on green repo |

## A. Prepare the template (once, in this repo)

1. Land the `infra.yml` "Ensure resource group exists" step on `main` (it tolerates
   an RG-scoped SP that can't create RGs — see [infrastructure.md](../architecture/infrastructure.md)).
2. **Settings → General → ✓ Template repository.**

## B. Azure (admin, once — needs subscription Owner)

```bash
SUB=<your-subscription-id>

# One resource group per team
az group create -n rg-aiinvestor-blue  -l westeurope
az group create -n rg-aiinvestor-green -l westeurope

# One service principal per team, scoped Contributor to ONLY its RG
az ad sp create-for-rbac --name gh-aiinvestor-blue  --role Contributor \
  --scopes /subscriptions/$SUB/resourceGroups/rg-aiinvestor-blue  --sdk-auth > blue-sp.json
az ad sp create-for-rbac --name gh-aiinvestor-green --role Contributor \
  --scopes /subscriptions/$SUB/resourceGroups/rg-aiinvestor-green --sdk-auth > green-sp.json
```

RG-scoped Contributor covers everything the workflows do (Bicep RG deployment,
`az functionapp list`, `az staticwebapp secrets list`). Neither SP can see or
touch the other team's RG.

## C. Create each team repo (from the template)

**Use this template → Create new repository** → `aiinvestor-blue`, then again for
`aiinvestor-green`. Add each team as a **collaborator with Write** on their repo
only (and optionally protect `main`).

## D. Configure each repo (independent CI)

Set each repo's variables + secrets — via **Settings → Secrets and variables →
Actions**, or with the `gh` CLI. Example for blue (repeat for green with its RG,
base name, SP file, and **separate keys**):

```bash
R=<you>/aiinvestor-blue
gh variable set AZURE_RESOURCE_GROUP -R $R -b rg-aiinvestor-blue
gh variable set AZURE_BASE_NAME      -R $R -b aiinvblue
gh variable set AZURE_LOCATION       -R $R -b westeurope
gh secret   set AZURE_CREDENTIALS    -R $R < blue-sp.json
gh secret   set FINNHUB_API_KEY      -R $R -b <blue-finnhub-key>
gh secret   set CLAUDE_API_KEY       -R $R -b <blue-claude-key>
```

Then, per repo: install the **Claude GitHub App** (<https://github.com/apps/claude>)
and ensure a `bug` label exists (needed for [automated-bug-fix.md](automated-bug-fix.md)).

## E. Deploy each team (per repo, same order as the root README)

Actions → **Infra (Bicep)** → **Deploy (Function code)** → call `GET /api/setup`
once → **Deploy Frontend (prod)**. Each repo's run summary prints its own
Function App + SWA hostnames.

## Why this meets the requirements

- **Standalone app + own code** — separate template-spawned repos, diverge freely.
- **Same subscription, different RGs** — `uniqueString(resourceGroup().id)`
  guarantees no resource-name collisions even with identical base names.
- **Independent Actions** — separate repos = separate runners, secrets, and run
  history; the RG-scoped SPs mean a misfired run **cannot** reach the other RG.
- **Fair competition** — separate Finnhub/Claude keys = independent rate limits
  and spend; per-team `/api/setup` = independent portfolio state.

## Notes

- `--sdk-auth` produces the legacy creds-JSON the repo's `azure/login@v2` expects.
  OIDC federated credentials are the modern alternative if you'd rather not store
  a long-lived secret — more setup, no secret to rotate.
- Set an Azure **budget per RG** for hard cost caps; the app's own guardrails
  ($10 Claude spend cap, 200 Finnhub calls/day) apply per deployment, so each team
  is independently bounded.
- Delete `blue-sp.json` / `green-sp.json` after uploading them — they contain
  credentials.
