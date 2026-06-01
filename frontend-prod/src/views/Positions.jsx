import { getPortfolio, getPrice } from "../api.js";
import { useAsync } from "../components/useAsync.js";
import { Loading, ErrorState, Empty } from "../components/States.jsx";
import { usd, pct, num, signClass } from "../components/format.js";

// Load holdings, then a live quote per symbol. Market value, unrealized P&L and
// P&L% are computed client-side from the live price (the backend's stored
// market_value is the last-trade value, not live).
async function loadPositions() {
  const { positions } = await getPortfolio();
  const quotes = await Promise.all(positions.map((p) => getPrice(p.symbol)));
  return positions.map((p, i) => {
    const price = quotes[i].price;
    const marketValue = price * p.shares;
    const unrealized = (price - p.avg_cost) * p.shares;
    const pnlPct = price / p.avg_cost - 1;
    return { ...p, price, marketValue, unrealized, pnlPct };
  });
}

export default function Positions() {
  const { data, loading, error } = useAsync(loadPositions);

  if (loading) return <Loading label="Loading positions & live prices…" />;
  if (error) return <ErrorState error={error} />;
  if (!data.length) return <Empty label="No open positions." />;

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
          {data.map((r) => (
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
        </tbody>
      </table>
    </div>
  );
}
