"""System mandate and per-level instructions for the portfolio agent."""

MANDATE = """Si autonómny portfolio manažér spravujúci paper trading portfólio
s počiatočným kapitálom $100,000.

UNIVERZUM: US equities + ETFs. Spravuješ vlastný watchlist (max 30 symbolov).
POZÍCIE: Min 5, max 10 otvorených pozícií.
SIZING: Max 15% portfólia v jednej pozícii. Min 10% cash rezerva vždy.
WATCHLIST: Watchlist si spravuješ sám — môžeš pridať sľubné symboly alebo
  odobrať nezaujímavé, vždy s písomným odôvodnením. Nemôžeš odobrať symbol,
  v ktorom máš otvorenú pozíciu. Nové symboly sa začnú skenovať nasledujúci deň.
STRATÉGIA: Prvý deň si sám zvolíš investičnú stratégiu a zdôvodníš ju
  písomne. Držíš sa jej, ale môžeš ju revidovať ak sa zmenia podmienky
  — vždy s písomným odôvodnením.
EARNINGS RISK: 2 pracovné dni pred earnings reportom redukuješ pozíciu
  na max 5% — automaticky, bez výnimky.
ROZHODOVANIE: Každý deň skenuješ celý watchlist, vyberáš 2-3 symboly na
  hĺbkovú analýzu a prehodnotíš existujúce pozície. Každé rozhodnutie —
  vrátane "nič nerobiť" — musí byť písomne zdôvodnené v investment memo.
BENCHMARK: Porovnávaš sa voči SPY. Cieľ je dlhodobý outperformance.
VÝKONNOSŤ: Každé investment memo MUSÍ začať porovnaním výkonnosti portfólia
  voči SPY od začiatku (alpha) — toto je primárna metrika úspechu. Čísla
  o výkonnosti máš dané vo vstupe; SPY nikdy nehádaj — ak benchmark dáta
  ešte nie sú k dispozícii, explicitne to uveď.
TRANSPARENTNOSŤ: Každý trade musí obsahovať: signály ktoré ťa viedli,
  čo si zvažoval alternatívne a prečo si to zamietol.

Dáta si vyžiadaš cez dostupné nástroje (tools). Nehádaj čísla — vždy
si over aktuálne dáta cez nástroje. Ceny pre obchody určuje systém
z live quotes, ty rozhoduješ symbol/stranu/počet kusov."""


def screening_user_prompt(rows: list[dict], positions: list[dict], prior_memo: str = "") -> str:
    lines = []
    for r in rows:
        rec = r.get("recommendation") or {}
        lines.append(
            f"- {r['symbol']}: price={r.get('price')}, "
            f"consensus buy={rec.get('strong_buy')}+{rec.get('buy')} / "
            f"hold={rec.get('hold')} / sell={rec.get('sell')}+{rec.get('strong_sell')}"
        )
    table = "\n".join(lines)
    held = ", ".join(f"{p['symbol']}({p['shares']})" for p in positions) or "žiadne"
    prior = (
        f"\nPREDCHÁDZAJÚCE MEMO (zachovaj kontinuitu stratégie):\n{prior_memo}\n"
        "Kandidáti, ktorých si v ňom označil na budúci vstup, majú prednosť pred "
        "novými — explicitne uveď v rationale, prečo si ich vybral alebo nevybral.\n"
        if prior_memo else ""
    )
    return (
        f"Screening celého watchlistu ({len(rows)} symbolov). Quote + analyst consensus:\n"
        f"{table}\n\n"
        f"Aktuálne pozície: {held}\n"
        f"{prior}\n"
        "Úlohy:\n"
        "1) Vyber 2-3 symboly z watchlistu na hĺbkovú analýzu (momentum, konsenzus, "
        "diverzifikácia voči pozíciám).\n"
        "2) Voliteľne uprav watchlist: pridaj sľubné US equities/ETF mimo zoznamu alebo "
        "odober nezaujímavé (nie tie s otvorenou pozíciou). Nové symboly sa skenujú zajtra.\n"
        'Odpovedz IBA JSON: {"selected": ["SYM", ...], '
        '"add": [{"symbol": "SYM", "reason": "..."}], '
        '"remove": [{"symbol": "SYM", "reason": "..."}], '
        '"rationale": "stručné zdôvodnenie"}. Polia add/remove môžu byť prázdne.'
    )


def _format_performance(p: dict | None) -> str:
    """Render the portfolio-vs-SPY feedback block for the deep-dive prompt.
    SPY/alpha lines appear only when a benchmark baseline exists — never invented."""
    if not p:
        return ""
    out = [
        "VÝKONNOSŤ PORTFÓLIA (feedback — použi v memo):",
        f"- Hodnota: ${p['total']:.2f} (z toho cash ${p['cash']:.2f}), "
        f"počiatočný vklad ${p['inception_capital']:.2f}",
    ]
    pr, sr, al = p.get("portfolio_return_pct"), p.get("spy_return_pct"), p.get("alpha_pct")
    out.append(f"- Výnos portfólia od začiatku: {pr:+.2f}%" if pr is not None
               else "- Výnos portfólia od začiatku: n/a")
    if sr is not None and al is not None:
        out.append(f"- SPY od začiatku: {sr:+.2f}%  →  ALPHA: {al:+.2f}%")
    else:
        out.append(f"- SPY benchmark: ešte sa zbiera ({p.get('benchmark_days', 0)} dní dát) "
                   "— SPY ani alpha NEUVÁDZAJ ako odhad")
    for pos in p.get("positions", []):
        pct = f"{pos['pnl_pct']:+.1f}%" if pos.get("pnl_pct") is not None else "n/a"
        out.append(f"  · {pos['symbol']}: {pos['shares']}ks @ ${pos['avg_cost']} → "
                   f"${pos['price']} ({pct}, ${pos['pnl']:+.0f})")
    return "\n".join(out) + "\n\n"


def deepdive_user_prompt(symbols: list[str], portfolio: dict, cash: float,
                         performance: dict | None = None) -> str:
    return (
        f"Hĺbková analýza pre: {', '.join(symbols)}.\n"
        f"Aktuálne pozície: {portfolio}\n"
        f"Voľný cash: ${cash:.2f}\n\n"
        f"{_format_performance(performance)}"
        "Vyžiadaj si fundamentals, news, insider sentiment, price target a earnings dátum "
        "(nástroje môžeš volať naraz). Dodrž SIZING a EARNINGS RISK pravidlá z mandátu. "
        "Rozhodni BUY/SELL/HOLD pre každý analyzovaný symbol aj pre existujúce pozície.\n\n"
        "FORMÁT ODPOVEDE — presne v tomto poradí:\n"
        "1) NAJPRV kompaktný JSON blok IBA s obchodmi (reasoning max 1 veta), aby sa "
        "neskrátil:\n"
        '```json\n{"trades": [{"symbol": "SYM", "side": "BUY", "shares": N, '
        '"reasoning": "1 veta"}]}\n```\n'
        '   Ak nič neobchoduješ: {"trades": []}.\n'
        "2) POTOM napíš investment memo ako voľný text. MUSÍ začať porovnaním výkonnosti "
        "portfólia voči SPY (alpha od začiatku) — ak SPY dáta chýbajú, uveď to. "
        "Potom: zvolená/revidovaná stratégia, kľúčové signály, zvažované alternatívy "
        "a prečo si ich zamietol."
    )
