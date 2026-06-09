"""Unit tests for agent.tools — tool schema shape + dispatcher."""

from types import SimpleNamespace

from agent import tools
from agent.tools import DEEPDIVE_TOOLS, run_tool


def test_symbol_tool_schema_shape():
    t = tools._symbol_tool("get_quote", "Live price.")
    assert t["name"] == "get_quote"
    assert t["description"] == "Live price."
    assert t["input_schema"]["required"] == ["symbol"]
    assert "symbol" in t["input_schema"]["properties"]


def test_deepdive_tools_expose_expected_names():
    names = {t["name"] for t in DEEPDIVE_TOOLS}
    assert names == {
        "get_quote", "get_fundamentals", "get_news", "get_insider_sentiment",
        "get_analyst_recommendation", "get_price_target", "get_earnings",
    }


def test_run_tool_dispatches_and_uppercases_symbol():
    fc = SimpleNamespace(get_quote=lambda symbol: {"got": symbol})
    assert run_tool(fc, "get_quote", {"symbol": "aapl"}) == {"got": "AAPL"}


def test_run_tool_unknown_tool_returns_error():
    fc = SimpleNamespace()
    assert run_tool(fc, "does_not_exist", {"symbol": "AAPL"}) == {"error": "unknown tool does_not_exist"}
