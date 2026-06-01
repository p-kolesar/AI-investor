# AI Portfolio Manager — Kompletná špecifikácia

## Kontext a účel

Edukačný projekt ako živá demonštrácia GenAI pre hands-on workshop v capital markets / FS prostredí. Účastníci sú IT profesionáli (developeri, funkční konzultanti, testeri) s FS background-om. Systém beží 2 týždne autonómne pred workshopom — Claude každý deň obchoduje, píše investment memo, buduje históriu. Účastníci pracujú s živým systémom s reálnymi dátami. Prevádzkové náklady ~$0.25 za 2 týždne.

-----

## Stack

|Vrstva       |Technológia                                           |
|-------------|------------------------------------------------------|
|Backend      |Python Flex Function App (Consumption)                |
|AI Agent     |Claude API — claude-sonnet-4-6                        |
|Market Data  |Finnhub (primary)                                     |
|Storage      |Polars + Parquet → Azure Blob Storage                 |
|Secrets      |Azure Key Vault (manuálne zadané)                     |
|DevOps       |GitHub + GitHub Actions (4 workflows)                 |
|Frontend Prod|React SPA → Azure Static Web Apps                     |
|Frontend Beta|React SPA → Azure Static Web Apps (separátna instance)|

-----

## Repo štruktúra

```
ai-portfolio-manager/
├── backend/
│   ├── function_app.py
│   ├── agent/
│   │   ├── loop.py
│   │   ├── tools.py
│   │   └── prompts.py
│   ├── market/
│   │   └── finnhub.py
│   ├── storage/
│   │   └── blobs.py
│   ├── requirements.txt
│   └── local.settings.json.example
├── frontend-prod/
│   ├── src/
│   │   ├── App.jsx
│   │   └── views/
│   ├── package.json
│   └── staticwebapp.config.json
├── frontend-beta/
│   ├── src/
│   │   ├── App.jsx
│   │   └── views/
│   ├── package.json
│   └── staticwebapp.config.json
└── .github/
    └── workflows/
        ├── deploy-backend.yml
        ├── deploy-frontend-prod.yml
        ├── deploy-frontend-beta.yml
        └── daily-agent.yml
```

-----

## Backend Endpoints

|Endpoint          |Metóda|Popis                                                        |
|------------------|------|-------------------------------------------------------------|
|`/agent/run`      |POST  |Manuálny trigger agent run                                   |
|`/agent/log`      |GET   |Posledné agent runy (memo, tokeny, cost) + kumulatívny spend |
|`/portfolio`      |GET   |Aktuálne pozície + cash                                      |
|`/trade`          |POST  |Zaznamenať trade                                             |
|`/trades`         |GET   |História tradov                                              |
|`/watchlist`      |GET   |Aktuálny (agentom spravovaný) watchlist                      |
|`/prices/{symbol}`|GET   |Live quote (cez cache)                                       |
|`/setup`          |GET   |Inicializácia — vytvorí Parquet súbory, $100K cash, watchlist|

-----

## Finnhub — použité endpointy

- `/quote` — live cena
- `/stock/metric` — fundamentals (P/E, EPS, ROE…)
- `/company-news` — posledné správy
- `/stock/insider-sentiment` — MSPR signál
- `/stock/recommendation` — analyst consensus
- `/stock/price-target` — analyst price target
- `/calendar/earnings` — earnings calendar
- `/indicator` — RSI, MACD

-----

## Parquet súbory v Azure Blob

```
papertrading/
├── portfolio.parquet       # pozície + cash
├── trades.parquet          # append-only ledger
├── watchlist.parquet       # 10 symbolov + rotácia
├── agent_log.parquet       # memo + reasoning + token usage per deň
├── prices_cache.parquet    # quotes TTL 15 min
└── benchmark.parquet       # SPY daily close
```

-----

## Agent — Mandát

```
Si autonómny portfolio manažér spravujúci paper trading portfólio
s počiatočným kapitálom $100,000.

UNIVERZUM: US equities + ETFs. Agent si spravuje vlastný watchlist (max 30).
POZÍCIE: Min 5, max 10 otvorených pozícií.
SIZING: Max 15% portfólia v jednej pozícii. Min 10% cash rezerva vždy.
WATCHLIST: Agent môže pridať/odobrať symboly s odôvodnením (nie tie s otvorenou
  pozíciou); validuje sa cez Finnhub quote. Nové symboly sa skenujú nasledujúci deň.
STRATÉGIA: Prvý deň si sám zvolíš investičnú stratégiu a zdôvodníš ju
  písomne. Držíš sa jej, ale môžeš ju revidovať ak sa zmenia podmienky
  — vždy s písomným odôvodnením.
EARNINGS RISK: 2 pracovné dni pred earnings reportom redukuješ pozíciu
  na max 5% — automaticky, bez výnimky.
ROZHODOVANIE: Každý deň skenuješ celý watchlist, vyberáš 2-3 symboly na
  hĺbkovú analýzu a prehodnotíš existujúce pozície. Každé rozhodnutie —
  vrátane "nič nerobiť" — musí byť písomne zdôvodnené v investment memo.
BENCHMARK: Porovnávaš sa voči SPY. Cieľ je dlhodobý outperformance.
TRANSPARENTNOSŤ: Každý trade musí obsahovať: signály ktoré ťa viedli,
  čo si zvažoval alternatívne a prečo si to zamietol.
```

-----

## Agent — 2-level loop

```
Level 1 — Screening (max_tokens: 1024)
  → loop pre-fetchne quotes + analyst recommendation pre celý watchlist
  → Claude v jednom volaní zoradí, vyberie 2-3 do deep dive + upraví watchlist
  → ~1,500-2,500 input tokenov

Level 2 — Deep dive (max_tokens: 4096)
  → fundamentals + news + insider sentiment + earnings calendar
  → kompaktný trades JSON (najprv) + investment memo (voľný text, potom)
  → ~3,500-7,000 tokenov

Daily budget cap: 15,000 tokenov (screening-runaway guard; reálny strop je $5)
Kumulatívny spend cap: ekvivalent $5 → agent sa vypne
```

-----

## Watchlist

Agent-managed (max 30). Sektorovo diverzifikovaný seed (14):

`AAPL, MSFT, NVDA, AMZN, GOOGL, JPM, BRK.B, UNH, LLY, XOM, CAT, PG, SPY, QQQ`

Agent počas behu pridáva/odoberá symboly (validované cez Finnhub quote).

-----

## Cost Guardrails

### Claude API

- Per-call max_tokens: Screening 1024 / Deep dive 4096
- Daily token budget cap: 15,000 tokenov (guard; reálny strop je kumulatívny $5)
- Kumulatívny cap: $5 ekvivalent → agent vypnutý
- Anthropic Console: manuálne spending limit $10

### Finnhub

- Rate limiter: max 42 calls/min (~70% free tier of 60/min)
- Daily call counter v Blob: cap 200 calls/deň
- Cache TTL: 15 minút

### Azure

- Cost Alert: email pri $5, hard stop pri $10
- `FUNCTIONS_WORKER_PROCESS_COUNT=1`

-----

## Token Logging (do agent_log.parquet)

```
run_date, level1_input_tokens, level1_output_tokens,
level2_input_tokens, level2_output_tokens,
total_tokens, estimated_cost_usd
```

```python
cost = (input_tokens * 3.00 + output_tokens * 15.00) / 1_000_000
```

-----

## GitHub Actions — 4 workflows

|Workflow                  |Trigger                                                      |
|--------------------------|-------------------------------------------------------------|
|`deploy-backend.yml`      |Push to main → Function App                                  |
|`deploy-frontend-prod.yml`|Push to main → Static Web Apps prod                          |
|`deploy-frontend-beta.yml`|Push to main → Static Web Apps beta                          |
|`daily-agent.yml`         |Cron 08:30 UTC Mon-Fri + US holiday check + email pri failure|

-----

## GitHub — Branch Protection & Permissions

- Direct push na `main` zakázaný
- Všetko cez Pull Request (1 approval = ty)
- GitHub Actions musia prejsť pred merge
- Účastníci: `Write` access (branches, nie main)
- `workflow_dispatch` na `daily-agent.yml` len pre owner

### Participant branch konvencia

```
feature/participant-A-bug-fix
feature/participant-B-audit
feature/participant-C-tokens
```

-----

## Frontend Prod — 4 taby, dark mode

|Tab        |Obsah                                                                                                         |
|-----------|--------------------------------------------------------------------------------------------------------------|
|Dashboard  |KPI row (Portfolio Value / Cash / Total Return % / vs SPY) + line chart portfolio vs SPY + bar chart daily P&L|
|Positions  |Tabuľka: symbol / shares / avg cost / live price / market value / unrealized P&L / P&L%                       |
|Agent Log  |Timeline denných run-ov + klik → detail karta s investment memo                                               |
|Performance|Sharpe ratio / max drawdown / win rate / realized vs unrealized P&L per pozícia                               |

-----

## Frontend Beta — 3 taby, 2 zámerné bugy

|Tab          |Obsah                                                |
|-------------|-----------------------------------------------------|
|Dashboard    |Identický s prod                                     |
|Positions    |**BUG: Math.abs() navyše → P&L vždy kladné**         |
|Agent Log    |**BUG: karty sorted ASC namiesto DESC → zlé poradie**|
|~Performance~|Chýba úplne                                          |

-----

## Export pred workshopom

Nahrať na SharePoint pred sessionou:

- `agent_log.csv`
- `performance.csv`
- `token_usage.csv`

-----

## Workshop Zadania

### Zadanie A — Debug & Extend

*Developeri | VS Code + GitHub Copilot*

- Nájdi a oprav 2 zámerné bugy vo `frontend-beta`
- Zdokumentuj v MD: čo si našiel, kde bol bug, ako si ho opravil
- Vytvor PR na `main`
- **Bonus:** Kvantifikuj dopad — o koľko % sa líšil buggy P&L od reálneho?

### Zadanie B — Audit Claudových rozhodnutí

*Konzultanti + Testeri | M365 Copilot (Word + Excel)*

- Analyzuj `agent_log.csv` a `performance.csv` zo SharePointu
- Napíš investment committee memo: stratégia, správne/nesprávne rozhodnutia, performance vs SPY
- **Bonus:** 1-page číselný scorecard — win rate / % dní outperformance / avg holding period / denná volatilita vs SPY

### Zadanie C — Token Usage Optimisation

*Mix | GitHub Copilot + M365 Copilot*

- Analyzuj `token_usage.csv` — token consumption per run za 2 týždne
- Navrhni a zdokumentuj optimalizáciu promptov (bez straty kvality rozhodnutí)
- **Bonus:** Graf spotreby, odhad úspory v % aj USD za rok pri dennom rune

### Debriefing formát — každý tím prezentuje 1 číslo

- Tím A: *“Bug spôsoboval zobrazenie P&L o X% vyššie než realita”*
- Tím B: *“Claude outperformoval SPY v Y z 14 dní, win rate Z%”*
- Tím C: *“Optimalizácia ušetrí N tokenov/deň = $X za rok”*

-----

## Pre-workshop Checklist (účastníci)

- [ ] Git nakonfigurovaný (user.email, user.name)
- [ ] GitHub účet + pozvánka do repo
- [ ] VS Code + GitHub Copilot extension aktívny
- [ ] Python 3.10+
- [ ] Node.js 18+
- [ ] `git clone` repo
- [ ] `cd frontend-beta && npm install`
- [ ] `cd backend && pip install -r requirements.txt`
- [ ] Otestovať GitHub Copilot v VS Code (aspoň 1 suggestion)

-----

## Cheat Sheet pojmov (priložiť k Zadaniu B)

|Pojem          |Vysvetlenie                                               |
|---------------|----------------------------------------------------------|
|P&L            |Profit and Loss — rozdiel medzi nákupnou a aktuálnou cenou|
|Benchmark      |Referenčný index (SPY = S&P 500 ETF)                      |
|Sharpe ratio   |Výnos / riziko — čím vyšší tým lepší                      |
|Max Drawdown   |Najväčší pokles portfólia od vrcholu                      |
|Win rate       |% tradov ktoré skončili v zisku                           |
|Position sizing|Koľko % portfólia je investovaných v jednej akcii         |
|Unrealized P&L |Zisk/strata na stále otvorených pozíciách                 |
|Holding period |Ako dlho Claude držal danú pozíciu                        |
|Outperformance |Portfólio rastie rýchlejšie ako benchmark (SPY)           |

-----

## Poradie generovania kódu

1. `backend/` — storage → market data → agent → endpoints
1. `.github/workflows/` — 4 workflows
1. `frontend-prod/` — plný dark mode React
1. `frontend-beta/` — kópia prod + 2 bugy − Performance tab
1. `README.md` + Deployment guide (vrátane branch protection setup)

-----

## Poznámky

- **Routines (Claude Code):** research preview, edukačný talking point na workshope — nie v produkcii
- **Auth:** frontend je verejná URL, žiadna autentifikácia
- **Cold start:** Consumption plan má ~2-3s cold start — OK pre demo
- **US sviatky:** daily-agent.yml obsahuje holiday check pred spustením
- **Init:** pred prvým agent runom zavolať `GET /setup`