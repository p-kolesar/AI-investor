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
