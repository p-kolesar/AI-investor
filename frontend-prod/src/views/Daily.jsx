import { getSnapshots } from "../api.js";
import { useAsync } from "../components/useAsync.js";
import { Loading, ErrorState, Empty } from "../components/States.jsx";
import { usd } from "../components/format.js";

// One row per portfolio snapshot (most recent first). The backend takes a
// live-marked snapshot at the end of every agent run, so market_value here is
// the value at run time — no client-side re-quoting needed (unlike Positions).
function splitTimestamp(ts) {
  const [date, time = ""] = String(ts).split(/[ T]/);
  return { date, time: time.slice(0, 5) }; // HH:MM
}

const holdings = (positions) =>
  positions?.length ? positions.map((p) => `${p.symbol} ×${p.shares}`).join(", ") : "—";

export default function Daily() {
  const { data, loading, error } = useAsync(getSnapshots);

  if (loading) return <Loading label="Loading daily snapshots…" />;
  if (error) return <ErrorState error={error} />;
  if (!data.length) return <Empty label="No snapshots yet." />;

  return (
    <div className="panel">
      <h2>Daily</h2>
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Time</th>
            <th>Portfolio</th>
            <th>Market Value</th>
            <th>Cashflow</th>
            <th>Total</th>
          </tr>
        </thead>
        <tbody>
          {data.map((r) => {
            const { date, time } = splitTimestamp(r.timestamp);
            return (
              <tr key={r.timestamp}>
                <td className="mono">{date}</td>
                <td className="mono">{time}</td>
                <td>{holdings(r.positions)}</td>
                <td className="mono">{usd(r.market_value)}</td>
                <td className="mono">{usd(r.cash)}</td>
                <td className="mono">{usd(r.total)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
