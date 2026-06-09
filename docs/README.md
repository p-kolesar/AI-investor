# Documentation

This is the map of the AI Portfolio Manager docs. It is written for **two
audiences at once** — humans onboarding to the project, and AI agents making
changes. Keep entries short and link out; this page should stay scannable.

> **Guideline (not a gate):** when you change behaviour, schemas, infra, or
> workflows, try to update the matching doc in the same PR and bump its
> `Last verified:` date. It's a strong recommendation, not an enforced rule —
> but stale docs mislead, and an agent will trust them.

## Start here

| You want to… | Read |
| --- | --- |
| Understand the whole system in 5 min | [architecture/overview.md](architecture/overview.md) |
| **Know the shape of data in storage** | [data/README.md](data/README.md) ← most-used reference |
| Run it locally | [guides/local-development.md](guides/local-development.md) |
| Deploy it | [guides/deployment.md](guides/deployment.md) |
| Add a feature / fix a bug safely | [guides/adding-a-feature.md](guides/adding-a-feature.md) |
| Run / write the tests | [guides/testing.md](guides/testing.md) → [tests/](../tests/README.md) |
| Auto-fix a bug from a labeled issue | [guides/automated-bug-fix.md](guides/automated-bug-fix.md) |
| Build a feature from issue → PR with agents | [guides/feature-workflow.md](guides/feature-workflow.md) |
| Stand up blue/green competition repos | [guides/competition-setup.md](guides/competition-setup.md) |
| Know *why* something is the way it is | [decisions/](decisions/) |
| Browse / add rough ideas (not yet decided) | [ideas.md](ideas.md) |

## Layout

```
docs/
  README.md                 # this map
  ideas.md                  # backlog of rough ideas, not yet decided
  architecture/             # how the system is built (components + flows)
    overview.md
    backend.md
    frontend.md
    infrastructure.md
  data/                     # THE DATA LAYER — what lives in the storage account
    README.md               #   container map + the data contract
    storage-account.md      #   accounts, containers, auth, naming, formats
    schemas/                #   field-by-field schema per blob
      papertrading.md
    samples/                #   representative sample rows (CSV mirrors)
      papertrading/
  guides/                   # task-oriented how-tos
    local-development.md
    deployment.md
    adding-a-feature.md
    testing.md
    automated-bug-fix.md
    feature-workflow.md
    competition-setup.md
  decisions/                # Architecture Decision Records (the "why")
    README.md
    0001-record-architecture-decisions.md
```

> The test suite itself lives at the repo root in [`tests/`](../tests/README.md)
> (with `pytest.ini`), alongside the code it covers — `docs/guides/testing.md` is
> the pointer to it.

## Conventions

- **One source of truth.** Operational facts (endpoints, secrets, deploy order)
  live in the root [README.md](../README.md); docs here link to it, not copy it.
- **The data layer is the exception** — it is *not* discoverable from the repo
  (blobs live in Azure, written at runtime). So `data/` documents it in full,
  with sample rows committed alongside.
- Sample data is **synthetic but schema-accurate and realistic**. It must never
  contain real secrets or personal data.
- Each doc carries a `Status:` line (`stub` / `draft` / `current`) and a
  `Last verified:` date so readers know how much to trust it.
