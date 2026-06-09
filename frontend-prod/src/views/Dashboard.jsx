import { getPortfolio, getHistory, getPrice } from "../api.js";
import { useAsync } from "../components/useAsync.js";
import { KpiCard } from "../components/KpiCard.jsx";
import { Loading, ErrorState } from "../components/States.jsx";
import { PortfolioVsSpyChart, DailyPnlChart } from "../components/Charts.jsx";
import { usd, pct, signClass } from "../components/format.js";

const INITIAL_CAPITAL = 100000;

// Total return over a series indexed off the same start value.
const totalReturn = (series, key) =>
  series.length < 2 ? null : series[series.length - 1][key] / series[0][key] - 1;

async function loadDashboard() {
  const [portfolio, history] = await Promise.all([getPortfolio(), getHistory()]);
  // Re-mark positions with live prices so Portfolio Value and P&L (Performance tab)
  // use the same price basis. The backend stores last-trade market_value, not live.
  const quotes = await Promise.all(portfolio.positions.map((p) => getPrice(p.symbol)));
  const livePositionsValue = quotes.reduce((sum, q, i) => sum + q.price * portfolio.positions[i].shares, 0);
  const total_value = livePositionsValue + portfolio.cash;
  return { portfolio: { ...portfolio, total_value }, history };
}

export default function Dashboard() {
  const { data, loading, error } = useAsync(loadDashboard);

  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} />;

  const { portfolio, history } = data;
  const ret = portfolio.total_value / INITIAL_CAPITAL - 1;

  // Outperformance = portfolio return − SPY return over the charted window.
  const pRet = totalReturn(history.series, "portfolio_value");
  const sRet = totalReturn(history.series, "spy_close");
  const vsSpy = pRet == null || sRet == null ? null : pRet - sRet;

  return (
    <>
      <div className="kpi-row">
        <KpiCard label="Portfolio Value" value={usd(portfolio.total_value)} />
        <KpiCard label="Cash" value={usd(portfolio.cash)} />
        <KpiCard label="Total Return" value={pct(ret)} tone={signClass(ret)} />
        <KpiCard
          label="vs SPY"
          value={vsSpy == null ? "—" : `${vsSpy >= 0 ? "+" : ""}${pct(vsSpy)}`}
          tone={signClass(vsSpy)}
        />
      </div>

      {history.isStub && (
        <div className="stub-banner">
          Charts use demo history — the backend has no daily time-series endpoint yet.
        </div>
      )}

      <div className="grid-2">
        <div className="panel">
          <h2>Portfolio vs SPY</h2>
          <PortfolioVsSpyChart series={history.series} />
        </div>
        <div className="panel">
          <h2>Daily P&amp;L</h2>
          <DailyPnlChart series={history.series} />
        </div>
      </div>
    </>
  );
}
