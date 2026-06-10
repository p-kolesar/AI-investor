import { getPortfolio, getPrice } from "../api.js";
import { useAsync } from "../components/useAsync.js";
import { Loading, ErrorState, Empty } from "../components/States.jsx";
import { usd, pct, num, signClass } from "../components/format.js";

// Load holdings, then a live quote per symbol. Market value, unrealized P&L and
// P&L% are computed client-side from the live price (the backend's stored
// market_value is the last-trade value, not live).
async function loadPositions() {
  const { positions, cash } = await getPortfolio();
  const quotes = await Promise.all(positions.map((p) => getPrice(p.symbol)));
  const enriched = positions.map((p, i) => {
    const price = quotes[i].price;
    const marketValue = price * p.shares;
    const unrealized = (price - p.avg_cost) * p.shares;
    const pnlPct = price / p.avg_cost - 1;
    return { ...p, price, marketValue, unrealized, pnlPct };
  });
  return { positions: enriched, cash };
}

export default function Positions() {
  const { data, loading, error } = useAsync(loadPositions);

  if (loading) return <Loading label="Loading positions & live prices…" />;
  if (error) return <ErrorState error={error} />;
  if (!data.positions.length) return <Empty label="No open positions." />;

  const { positions, cash } = data;

  return (
    <div className="panel">
      <h2>Positions</h2>
      <table>
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Shares</th>
            <th>Avg Cost</th>
            <th>Live Price</th>
            <th>Market Value</th>
            <th>Unrealized P&amp;L</th>
            <th>P&amp;L %</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((r) => (
            <tr key={r.symbol}>
              <td>{r.symbol}</td>
              <td className="mono">{num(r.shares)}</td>
              <td className="mono">{usd(r.avg_cost)}</td>
              <td className="mono">{usd(r.price)}</td>
              <td className="mono">{usd(r.marketValue)}</td>
              <td className={`mono ${signClass(r.unrealized)}`}>{usd(r.unrealized)}</td>
              <td className={`mono ${signClass(r.pnlPct)}`}>{pct(r.pnlPct)}</td>
            </tr>
          ))}
          <tr key="__cash__" className="cash-row">
            <td>Cash</td>
            <td />
            <td />
            <td />
            <td className="mono">{usd(cash)}</td>
            <td />
            <td />
          </tr>
        </tbody>
        <tfoot>
          {(() => {
            const equityValue = positions.reduce((s, r) => s + r.marketValue, 0);
            const totalMarketValue = equityValue + cash;
            const totalUnrealized = positions.reduce((s, r) => s + r.unrealized, 0);
            const totalCost = positions.reduce((s, r) => s + r.avg_cost * r.shares, 0);
            const totalPnlPct = totalCost ? totalUnrealized / totalCost : null;
            return (
              <tr>
                <td><strong>Total</strong></td>
                <td />
                <td />
                <td />
                <td className="mono"><strong>{usd(totalMarketValue)}</strong></td>
                <td className={`mono ${signClass(totalUnrealized)}`}><strong>{usd(totalUnrealized)}</strong></td>
                <td className={`mono ${signClass(totalPnlPct)}`}><strong>{pct(totalPnlPct)}</strong></td>
              </tr>
            );
          })()}
        </tfoot>
      </table>
    </div>
  );
}
