import { getTrades } from "../api.js";
import { useAsync } from "../components/useAsync.js";
import { Loading, ErrorState, Empty } from "../components/States.jsx";
import { usd } from "../components/format.js";

export default function Blotter() {
  const { data, loading, error } = useAsync(getTrades);

  if (loading) return <Loading label="Loading trade history…" />;
  if (error) return <ErrorState error={error} />;
  if (!data.length) return <Empty label="No trades yet." />;

  const sorted = [...data].sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));

  return (
    <div className="panel">
      <h2>Blotter</h2>
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Symbol</th>
            <th>Side</th>
            <th>Shares</th>
            <th>Price</th>
            <th>Value</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((t, i) => (
            <tr key={i}>
              <td className="mono">{t.date}</td>
              <td>{t.symbol}</td>
              <td className={t.side === "BUY" ? "pos" : "neg"}>{t.side}</td>
              <td className="mono">{t.shares}</td>
              <td className="mono">{usd(t.price)}</td>
              <td className="mono">{usd(t.price * t.shares)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
