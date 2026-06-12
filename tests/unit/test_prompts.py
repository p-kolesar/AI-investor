"""Unit tests for agent.prompts builders.

Light structural checks — these are prompt strings, so assert the inputs and the
required output-format markers are present (the model relies on them).
"""

from agent import prompts


def test_mandate_is_nonempty_text():
    assert isinstance(prompts.MANDATE, str) and len(prompts.MANDATE) > 0


def test_screening_prompt_includes_symbols_and_json_contract():
    rows = [{"symbol": "AAPL", "price": 100,
             "recommendation": {"strong_buy": 1, "buy": 2, "hold": 0, "sell": 0, "strong_sell": 0}}]
    positions = [{"symbol": "AAPL", "shares": 5}]
    s = prompts.screening_user_prompt(rows, positions)
    assert "AAPL" in s
    assert '"selected"' in s          # the JSON keys the loop parses
    assert '"add"' in s and '"remove"' in s


def test_screening_prompt_handles_no_positions():
    s = prompts.screening_user_prompt([], [])
    assert "žiadne" in s  # "no positions" placeholder


def test_deepdive_prompt_includes_symbols_cash_and_trades_block():
    d = prompts.deepdive_user_prompt(["AAPL", "MSFT"], {"AAPL": 5}, 4_000.0)
    assert "AAPL" in d and "MSFT" in d
    assert '"trades"' in d         # the required trades JSON block
    assert "$4000.00" in d         # formatted cash


def test_screening_prompt_injects_prior_memo_for_continuity():
    s = prompts.screening_user_prompt([], [], prior_memo="Strategy: tech momentum tilt.")
    assert "Strategy: tech momentum tilt." in s
    assert "PREDCHÁDZAJÚCE MEMO" in s   # continuity / carry-over instruction present


def test_deepdive_prompt_renders_performance_alpha():
    perf = {
        "total": 101_000.0, "cash": 20_000.0, "inception_capital": 100_000.0,
        "portfolio_return_pct": 1.0, "spy_return_pct": 0.5, "alpha_pct": 0.5,
        "benchmark_days": 3,
        "positions": [{"symbol": "AAPL", "shares": 10, "avg_cost": 100.0,
                       "price": 110.0, "pnl": 100.0, "pnl_pct": 10.0}],
    }
    d = prompts.deepdive_user_prompt(["AAPL"], {"AAPL": 10}, 20_000.0, perf)
    assert "ALPHA" in d and "+0.50%" in d   # alpha surfaced
    assert "AAPL" in d                       # per-position P&L line


def test_deepdive_prompt_marks_spy_unavailable_when_no_baseline():
    perf = {
        "total": 100_000.0, "cash": 90_000.0, "inception_capital": 100_000.0,
        "portfolio_return_pct": 0.0, "spy_return_pct": None, "alpha_pct": None,
        "benchmark_days": 0, "positions": [],
    }
    d = prompts.deepdive_user_prompt(["AAPL"], {}, 90_000.0, perf)
    assert "ALPHA" not in d                   # never invents alpha
    assert "ešte sa zbiera" in d              # explicitly flags missing benchmark
