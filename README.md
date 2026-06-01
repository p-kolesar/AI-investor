# AI-investor

Demo app shell: a Python Azure Function App deployed to Azure via two GitHub Actions
pipelines — one for infrastructure (Bicep), one for application code.

## Layout

```
.github/workflows/
  infra.yml     # provisions/updates Azure infra (runs on infra/** changes + manual)
  deploy.yml    # builds + deploys the Python function code (runs on backend/** changes + manual)
infra/
  main.bicep            # Storage, Log Analytics + App Insights, Flex Consumption plan, Function App
  main.parameters.json  # baseName / environmentName / pythonVersion
backend/
  function_app.py       # Python v2 model — GET /api/health
  host.json
  requirements.txt
  .funcignore
```

## One-time setup

### 1. Service principal → GitHub secret

Create a service principal with Contributor at **subscription** scope (so the infra job
can create the resource group), and save the JSON output as a GitHub Actions secret named
`AZURE_CREDENTIALS`:

```bash
az ad sp create-for-rbac \
  --name "gh-aiinvestor" \
  --role Contributor \
  --scopes /subscriptions/<SUBSCRIPTION_ID> \
  --sdk-auth
```

Copy the entire JSON object into **Repo → Settings → Secrets and variables → Actions →
Secrets → New repository secret**, name it `AZURE_CREDENTIALS`.

### 2. Repository variables

**Repo → Settings → Secrets and variables → Actions → Variables**, add:

| Variable | Value |
| --- | --- |
| `AZURE_RESOURCE_GROUP` | `rg-aiinvestor-dev` |
| `AZURE_LOCATION` | `westeurope` |
| `AZURE_BASE_NAME` | `aiinvestor` |

## First deployment

1. Run **Infra (Bicep)** manually (Actions → Infra → Run workflow). It creates the resource
   group and all resources; the run summary prints the generated Function App name + hostname.
2. Run **Deploy (Function code)** manually. It discovers the Function App in the resource
   group, deploys `src/`, then smoke-tests `GET /api/health`.

After that, merges to `main` trigger each pipeline automatically based on changed paths
(`infra/**` → infra, `src/**` → deploy).

## Local development

```bash
cd backend
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
func start    # requires Azure Functions Core Tools v4
# GET http://localhost:7071/api/health  ->  {"status": "ok"}
```

## Notes / future work

- **Storage auth:** deployment + WebJobs storage currently use a connection string for
  robustness. A later pass can switch to the Function App's managed identity.
- **Web layer:** naming/structure leaves room for a second app (Function App or Static Web
  App) without rework.
- **Hardening (later):** OIDC auth instead of an SP secret, a `prod` environment with
  approvals.
```
