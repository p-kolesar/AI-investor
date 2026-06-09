import { getTrades } from "../api.js";
import { useAsync } from "../components/useAsync.js";
import { Loading, ErrorState, Empty } from "../components/States.jsx";
import { usd, num } from "../components/format.js";

export default function Blotter() {
  const { data, loading, error } = useAsync(getTrades);

  if (loading) return <Loading label="Loading trade history…" />;
  if (error) return <ErrorState error={error} />;
  if (!data.length) return <Empty label="No trades recorded yet." />;

  const sorted = [...data].reverse();

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
          </tr>
        </thead>
        <tbody>
          {sorted.map((t, i) => (
            <tr key={i}>
              <td>{t.date}</td>
              <td>{t.symbol}</td>
              <td className={t.side === "BUY" ? "pos" : "neg"}>{t.side}</td>
              <td className="mono">{num(t.shares)}</td>
              <td className="mono">{usd(t.price)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
