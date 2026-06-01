import { useState } from "react";
import { getAgentLog } from "../api.js";
import { useAsync } from "../components/useAsync.js";
import { KpiCard } from "../components/KpiCard.jsx";
import { Loading, ErrorState, Empty } from "../components/States.jsx";
import { usd, num } from "../components/format.js";

// Master/detail: a timeline of daily runs (the backend returns them
// newest-first) and the selected run's investment memo + token breakdown.
export default function AgentLog() {
  const { data, loading, error } = useAsync(() => getAgentLog(30));
  const [selected, setSelected] = useState(0);

  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;
  if (!data.runs.length) return <Empty label="No agent runs yet." />;

  const runs = data.runs; // newest-first as served by the backend
  const run = runs[selected] ?? runs[0];

  return (
    <>
      <div className="kpi-row">
        <KpiCard label="Total Runs" value={num(data.total_runs)} />
        <KpiCard label="Cumulative Cost" value={usd(data.cumulative_cost_usd)} />
        <KpiCard label="Latest Run" value={runs[0].run_date} />
        <KpiCard label="Latest Tokens" value={num(runs[0].total_tokens)} />
      </div>

      <div className="grid-2">
        <div className="panel">
          <h2>Run Timeline</h2>
          <div className="timeline">
            {runs.map((r, i) => (
              <button
                key={r.run_date}
                className={`timeline-item ${i === selected ? "active" : ""}`}
                onClick={() => setSelected(i)}
              >
                <div className="row1">
                  <span>{r.run_date}</span>
                  <span className="mono">{usd(r.estimated_cost_usd)}</span>
                </div>
                <div className="row2">{num(r.total_tokens)} tokens</div>
                <div className="excerpt">{r.memo}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="panel">
          <h2>Investment Memo — {run.run_date}</h2>
          <div className="memo-meta">
            <span>Screening: <b>{num(run.level1_input_tokens + run.level1_output_tokens)}</b> tok</span>
            <span>Deep dive: <b>{num(run.level2_input_tokens + run.level2_output_tokens)}</b> tok</span>
            <span>Total: <b>{num(run.total_tokens)}</b> tok</span>
            <span>Cost: <b>{usd(run.estimated_cost_usd)}</b></span>
          </div>
          <div className="memo">{run.memo}</div>
        </div>
      </div>
    </>
  );
}
