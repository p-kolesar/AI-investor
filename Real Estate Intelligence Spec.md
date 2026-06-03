# Real Estate Intelligence — Specification

Companion to *AI Portfolio Manager Spec*. Covers the data model, ingestion, analytics, and the AI real-estate intelligence agent for nehnutelnosti.sk data.

**Status:** draft v1 (2026-06-03). Source of truth for the real-estate domain.

**Locked decisions (this session):**
- **Scope:** byty (apartments) only; Bratislava (17 districts) + Stupava corridor (stupava, marianka, borinka, lozorno); both `predaj` & `prenajom`.
- **Agent mode:** Both — autonomous daily brief **and** on-demand Q&A.
- **Primary outputs:** market trend report; rent-vs-buy / yield analysis; opportunity ranking.
- **Lens:** market research / monitoring — neutral analyst, **no buy/sell advice**. Surfaces signals, trends, yields; caveats excluded / low-coverage data.
- **Quality gate:** data-hygiene infrastructure (flag + skip, never delete), not a headline product.

---

## 1. Use cases (the driver)

| ID | Use case | Output type | Granularity (v1) |
|----|----------|-------------|------------------|
| UC1 | **Trend hot/cold** — how ppm², inventory, days-on-market move by area×segment over time | Trend report | district × category × week |
| UC2 | **Rent-vs-buy / yield** — gross yield per area×segment; where rent diverges from buy | Yield analysis | district × category |
| UC3 | **Opportunity ranking** — segments/listings standing out vs their area (low ppm², high yield, fresh+cheap) framed as *research signals*, not advice | Ranking | segment + listing |
| UC4 | **Data hygiene (supporting)** — exclude misleading/dirty entries (cadaster baiting, AI photos, dupes, outliers) so UC1–3 aren't polluted | Flags/exclusion | listing |
| UC5 | **Drill-down** — segment → district → (later) street, for context | Q&A / drill | district now; street later |

Everything below derives from these. Street/GPS/cadaster are **future** (phases 3–4); v1 delivers UC1–3 at district granularity with UC4 hygiene.

---

## 2. Data model

Three layers (medallion). **Bronze is immutable** — everything else is recomputable from it, so we never lose the ability to answer a question we didn't anticipate.

### 2.1 Grain & keys
| Layer | Grain (1 row = …) | Key | Mutability | Layout |
|-------|-------------------|-----|------------|--------|
| **bronze** | one listing as seen in one sweep (listing-snapshot) | (`detail_id`, `scraped_date`) | append-only, immutable | Hive-partitioned `type=/deal=/date=` Parquet |
| **silver** | one listing (lifecycle) | `detail_id` | rebuilt each run | Parquet (current snapshot) + `price_events` |
| **gold** | one segment per period | (`period`, `type`, `deal`, `district`, `category`) | rebuilt each run | Parquet |

### 2.2 Bronze schema (v1, ~16 cols; description prose **not** stored — copyright)
| Column | Type | Notes |
|--------|------|-------|
| `scraped_at` | datetime (UTC) | run timestamp |
| `scraped_date` | date | **partition** |
| `type` | str | `byty` (partition) |
| `deal` | str | `predaj`/`prenajom` (partition) |
| `detail_id` | str | **stable join key** |
| `title` | str | listing name |
| `category` | str | e.g. `3 izbový byt`, `Garsónka`, `Mezonet` |
| `rooms` | int? | derived from `category` (Garsónka/Dvojgarsónka→1, Mezonet→null) |
| `area_m2` | float | |
| `price_eur` | float? | null/0 → see `price_on_request` |
| `price_per_m2` | float? | computed `price_eur/area_m2` |
| `price_on_request` | bool | true when price missing/0 |
| `region` | str | from list `location` (kraj) |
| `district` | str | e.g. `okres Bratislava II` |
| `city` | str | e.g. `Bratislava-Ružinov` |
| `street` | str? | **parsed from description text** (best-effort, nullable) |
| `valid_from` | date? | listing publish date (JSON-LD `validFrom`) |
| `detail_url` | str | |

### 2.3 Silver (lifecycle) — adds, keyed on `detail_id`
`first_seen_date`, `last_seen_date`, `valid_to`, `is_active`, `days_on_market` (derived), `price_first`, `price_latest`, `n_price_changes`, `quality_flags` (list[str]), `is_excluded` (bool). Plus a `price_events(detail_id, observed_date, price_eur)` table for price-change history.

**`valid_to` — market-disappearance, derived (not site-provided).** The site exposes **no** end/expiry date (`validThrough`/`priceValidUntil` are absent), so `valid_to` is inferred from our snapshots: the run date a listing is first observed **gone** in the diff (≈ `last_seen_date`). `NULL` while `is_active`. With `valid_from` (site publish date) it gives the listing's market lifespan — the "how fast does it sell/vanish" signal:

> `days_on_market = (valid_to or today) − valid_from`

Caveats: resolution = scrape cadence (±1 day at daily); a re-posted flat may get a new `detail_id` and read as a fresh listing (inflates churn). The site's `created_at` / `updated_at` timestamps are also in the payload and can optionally be captured to refine re-list / price-change detection.

### 2.4 Gold (analytics)
- **`segment_weekly`** — grain (`week`, `type`, `deal`, `district`, `category`): `median_ppm2`, `p25_ppm2`, `p75_ppm2`, `listing_count`, `new_count`, `removed_count`, `median_days_on_market`, `median_price`, `median_area`, `ppm2_wow_pct`, `ppm2_mom_pct`.
- **`yield_segment`** — grain (`week`, `district`, `category`): `buy_median_ppm2`, `rent_median_ppm2_monthly`, `gross_yield_pct` (= rent_monthly_ppm2 × 12 / buy_ppm2), buy/rent sample sizes.

Gold **excludes `is_excluded` rows** and segments below a min sample size are marked low-confidence.

### 2.5 Quality framework (UC4)
- `quality_flags`: set of codes. Reserved (no detection logic yet): `cadaster_mismatch`, `ai_photos`, `duplicate`, `ppm2_outlier`, `price_on_request`, `street_unparsed`, `area_missing`.
- `is_excluded` = any *blocking* flag present → filtered from gold/analytics.
- **`quality_overrides`** table (`detail_id`, `flag`, `reason`, `added_by`, `added_at`) — manual, honored immediately. Delivers "flag & skip" today with zero detection code.
- **Rule hook:** pluggable functions `(row | dataset) -> flags`. Ships with none active; cadaster/AI rules added later. Cadaster detection will compare **claimed locality** vs **parsed street/village** (text-based, no GPS in v1).

---

## 3. Ingestion

### 3.1 Sweep
- Localities: 17 BA district slugs + corridor (`stupava`, `marianka`, `borinka`, `lozorno`). Types: `[byty]`. Deals: `[predaj, prenajom]`.
- Parse listings from the embedded schema.org JSON-LD + list app-data (`location`) in the `self.__next_f` payload — no detail-page fetches in v1.
- Page each search until empty **or the page-33 / ~990 cap guard**.

### 3.2 Cap guard (critical — see §6 volumetrics)
The site hard-caps pagination at **page 33 (~990 listings)** per search. If a search still returns a full page at the cap while `totalCount` implies more, log a **WARNING** and record under-coverage in run metadata. v1: warn only (all current segments are < cap). Future: auto-split the search by price band.

### 3.3 Dedup, snapshot & diff
- **Global dedup** by `detail_id` across all pages/localities in a run.
- Write the bronze partition (full snapshot).
- **Diff** vs prior active set → `new` (unseen ids) and `removed` (gone) → update silver lifecycle + `price_events`.

### 3.4 Politeness & resilience
- Sequential, single session; jittered delay ~20–40 s; randomized start in **05:45–07:45**; browser-like headers; robots honored (no `Crawl-delay` set).
- **Circuit-breaker:** on 403/429/challenge HTML or coverage collapse → stop & alert (honor `Retry-After`). Hard per-run request cap. Coverage canary (scraped vs summed `totalCount`).
- Runs on a **Timer trigger** (raise `functionTimeout` in `host.json`); the HTTP `/scrape-realestate` route stays for 1–2-district spot-checks.

### 3.5 Run metadata
`run_id, started_at, finished_at, n_searches, n_pages, n_rows, n_new, n_removed, cap_hits, coverage_pct`.

---

## 4. Analytics / gold build
Runs after each sweep (cheap at this scale): rebuild silver lifecycle → recompute gold aggregates + trend deltas in **Polars** (`scan_parquet(..., hive_partitioning=True)` + `group_by`). Never `.to_dicts()` raw rows. Trend grain = **weekly** (smooths daily noise; daily snapshots remain underneath).

---

## 5. AI agent

New agent, **separate** from the stock loop — own container (`realestate`), own `MANDATE`/prompts/tools. Reuses the proven skeleton from `agent/loop.py`: `_complete`/`_converse`, token logging, `DAILY_TOKEN_CAP`, `SPEND_CAP_USD`, `cache_control` on the system prompt, `MAX_TOOL_ROUNDS`.

### 5.1 Mandate (neutral lens)
A market analyst. Reports trends, yields, and notable segments/listings as **research signals with caveats**; **never** issues buy/sell recommendations. Always flags low-sample or low-coverage segments and notes how many listings were excluded and why.

### 5.2 Operating modes (Both)
- **Autonomous daily brief:** screen the compact gold segment table (pre-computed, in-prompt) → pick notable segments (hot/cold, yield-divergent, opportunity) → deep-dive via tools → write an intelligence memo. Stored + returned.
- **Interactive Q&A:** user question → tool-use conversation over the same tools → answer. Exposed via HTTP (`/realestate/ask`) and the front-end.

### 5.3 Guardrails
Token + spend caps (own budget); max tool rounds; **read-only** except `flag_listing`, which is code-validated. Arithmetic over rows happens in Polars, never in the model.

---

## 6. Tool catalog (three-tier)

**Tier A — pre-computed context (no call):** the current gold segment table, compact, injected into the screening prompt.

**Tier B — model-facing tools (Python methods → compact JSON, bounded results):**
| Tool | Input | Returns |
|------|-------|---------|
| `segment_stats` | `district, category, deal, period?` | median/p25/p75 ppm², count, new/removed, dom, `ppm2_wow_pct`, `ppm2_mom_pct` |
| `trend_series` | `district, category, deal, metric, weeks` | time-series points (capped length) |
| `yield_analysis` | `district, category` | buy ppm², rent monthly ppm², `gross_yield_pct`, sample sizes |
| `query_listings` | `filters{district,category,deal,rooms,price_max,ppm2_max,…}, sort, limit≤N, include_excluded=False` | small list of listing dicts (id, key facts, url) |
| `get_listing` | `detail_id` | full silver record for one listing |
| `compare_segments` | `segments[], metric` | small comparison table |
| `flag_listing` | `detail_id, flag, reason` | writes `quality_overrides` (validated, code-gated) |

**Tier C — deterministic pipeline (not model-facing):** ingestion sweep, dedup/diff, silver/gold build, exclusion application.

**Design rules:** few narrow well-named tools + one capped `query_listings`; every tool returns small bounded JSON; `limit` hard-capped; aggregations in Polars. Document Slovak enums (`deal∈{predaj,prenajom}`, `category∈{…izbový byt, Garsónka, Mezonet}`) and grain in the system prompt.

---

## 7. Phasing

| Phase | Deliverable |
|-------|-------------|
| **v0** (in progress) | List JSON-LD parser; HTTP spot-check route; `datain` container |
| **v1** (2-week validation) | Parser fixes (rooms-from-category, zero-price→on-request, cross-page dedup) + add `region/district/city/street/valid_from`; bronze partitioned snapshots; diff→silver; gold; politeness; timer trigger. **Validate UC1–3 on accumulating data.** |
| **v2** | RE agent (daily brief + Q&A) + Tier-B tools over gold/silver |
| **v3** | Street/GPS **detail-page enrichment for new listings only** (inflow-sized) + map |
| **v4** | Cadaster: external GIS (ZBGIS) join via GPS + automated `cadaster_mismatch` rule |

---

## 8. Volumetrics (measured 2026-06-03)
~6,123 active listings/sweep; ~226 page requests; **~0.65 MB Parquet/sweep** (zstd, 107 B/row); ~240 MB/year full-snapshot (far less if only changes stored). 2.2M rows/year is *small data* for Polars. **Pagination cap: page 33 / ~990 per search** → must partition (per-district sum 3,617 ≈ whole-city 3,613, all districts < cap).

---

## 9. Cost model & budget guardrails

**Principle: only the agent costs Claude tokens.** Ingestion, cleansing, dedup, and gold aggregation are pure Python/Polars/HTTP — **$0 Claude, regardless of data volume**. The model never sees raw rows, only pre-computed gold summaries + small tool results. Azure (a ~5-min daily Function + sub-GB blob) is pennies/month. So spend = agent only.

### 9.1 Estimates (Sonnet $3 / $15 per 1M in/out, with prompt caching; ±~2×)
| Component | Tokens (billable, cached) | ~Cost | Cadence | ~Per 2 weeks |
|---|---|---|---|---|
| Ingestion + gold build | 0 | **$0** | daily | **$0** |
| Daily brief | ~30k in / ~4k out | ~$0.15 | daily | **~$2** |
| Ad-hoc Q&A | ~20–40k in / ~1k out | ~$0.05–0.12 | per query | volume-driven |

Ingestion + daily brief ≈ **$2 / 2 weeks** (same order as the stock agent). **Ad-hoc Q&A is the only unbounded driver** (~5/day ≈ $7/2wk) → must be capped. The 2-week run measures actuals via the agent log.

### 9.2 Guardrails — a hard ceiling, not hope
- **Spend-cap auto-disable** per domain (reuse the `SPEND_CAP_USD` pattern from `agent/loop.py`) — agent stops at the cap.
- **Per-query + daily token caps** and a **daily Q&A count limit** on the interactive surface.
- **Token logging** to `realestate/agent_log.parquet` (mirror the stock agent) — exact cost from day one, not guesses.

### 9.3 Going lower (cost-minimization levers)
- **Prompt-cache** the system prompt + gold table (0.1× on re-reads) — biggest lever for the tool-use loop.
- **Model tiering:** Haiku (~$1 / $5) for simple lookups/routing and most Q&A; Sonnet for synthesis; avoid Opus (~5×).
- **Batch API (−50%)** for the daily brief — it isn't latency-sensitive.
- **Weekly deep brief + cheap daily "what-changed" delta** instead of a full brief every day.
- **Trim the screening context** — feed only notable/changed segments, not all ~180.
- **All arithmetic in Polars** — never pay the model to aggregate rows.

Combined, these pull the realistic run-rate toward **~$1–2 / 2 weeks** for ingestion + brief, with Q&A bounded by its cap.

---

## 10. Open decisions
1. **Memo/answer language** — Slovak (matches stock agent) vs English. *Proposed: Slovak.*
2. **Trend grain** — weekly vs daily. *Proposed: weekly over daily snapshots.*
3. **Agent model & budget** — Sonnet vs Opus; per-domain token/spend caps.
4. **Q&A surface** — HTTP endpoint + front-end integration details.
5. **Yield definition** — gross only (×12) vs net (costs/taxes). *Proposed: gross v1.*
6. **"Opportunity" thresholds** — how far below segment median counts as a signal (neutral framing, not advice).
