import { getPortfolio, getTrades, getPrice } from "../api.js";
import { useAsync } from "../components/useAsync.js";
import { KpiCard } from "../components/KpiCard.jsx";
import { Loading, ErrorState } from "../components/States.jsx";
import { usd, pct, signClass } from "../components/format.js";
import { realizedFromTrades } from "../components/perf.js";

// Win rate + realized P&L come from the trade ledger; unrealized P&L from open
// positions joined with live prices. Sharpe ratio and max drawdown need a daily
// returns series the backend doesn't serve yet, so they show as stubs.
// NOTE: frontend-beta omits this tab entirely.
async function loadPerformance() {
  const [portfolio, trades] = await Promise.all([getPortfolio(), getTrades()]);
  const quotes = await Promise.all(portfolio.positions.map((p) => getPrice(p.symbol)));
  const priceBySymbol = Object.fromEntries(quotes.map((q) => [q.symbol, q.price]));

  const realized = realizedFromTrades(trades);

  // Per-position unrealized P&L from live prices.
  const unrealizedBySymbol = {};
  let totalUnrealized = 0;
  for (const p of portfolio.positions) {
    const price = priceBySymbol[p.symbol];
    const u = (price - p.avg_cost) * p.shares;
    unrealizedBySymbol[p.symbol] = u;
    totalUnrealized += u;
  }

  // One row per symbol that ever traded or is still held.
  const symbols = [
    ...new Set([...Object.keys(realized.bySymbol), ...portfolio.positions.map((p) => p.symbol)]),
  ].sort();
  const rows = symbols.map((sym) => ({
    symbol: sym,
    realized: realized.bySymbol[sym]?.realized ?? 0,
    unrealized: unrealizedBySymbol[sym] ?? 0,
    open: sym in unrealizedBySymbol,
  }));

  const winRate = realized.closed ? realized.wins / realized.closed : null;
  return { rows, winRate, closed: realized.closed, totalRealized: realized.totalRealized, totalUnrealized };
}

export default function Performance() {
  const { data, loading, error } = useAsync(loadPerformance);

  if (loading) return <Loading label="Computing performance…" />;
  if (error) return <ErrorState error={error} />;

  return (
    <>
      <div className="kpi-row">
        <KpiCard
          label="Win Rate"
          value={data.winRate == null ? "—" : `${(data.winRate * 100).toFixed(0)}% (${data.closed})`}
        />
        <KpiCard label="Realized P&L" value={usd(data.totalRealized)} tone={signClass(data.totalRealized)} />
        <KpiCard label="Unrealized P&L" value={usd(data.totalUnrealized)} tone={signClass(data.totalUnrealized)} />
        <KpiCard label="Total P&L" value={usd(data.totalRealized + data.totalUnrealized)} tone={signClass(data.totalRealized + data.totalUnrealized)} />
      </div>

      <div className="panel">
        <h2>Realized vs Unrealized P&amp;L by Position</h2>
        <table>
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Status</th>
              <th>Realized P&amp;L</th>
              <th>Unrealized P&amp;L</th>
              <th>Total</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r) => (
              <tr key={r.symbol}>
                <td>{r.symbol}</td>
                <td style={{ textAlign: "left" }}>{r.open ? "Open" : "Closed"}</td>
                <td className={`mono ${signClass(r.realized)}`}>{usd(r.realized)}</td>
                <td className={`mono ${signClass(r.unrealized)}`}>{r.open ? usd(r.unrealized) : "—"}</td>
                <td className={`mono ${signClass(r.realized + r.unrealized)}`}>{usd(r.realized + r.unrealized)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid-2">
        <div className="panel">
          <h2>Sharpe Ratio</h2>
          <div className="state">Needs daily returns — pending history endpoint.</div>
        </div>
        <div className="panel">
          <h2>Max Drawdown</h2>
          <div className="state">Needs daily portfolio values — pending history endpoint.</div>
        </div>
      </div>
    </>
  );
}
