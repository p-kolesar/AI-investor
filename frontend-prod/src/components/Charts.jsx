import {
  ResponsiveContainer,
  LineChart, Line,
  BarChart, Bar, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from "recharts";

// Palette mirrors theme.css (Recharts needs explicit colors, not CSS vars).
const C = {
  accent: "#58a6ff",
  spy: "#8b949e",
  pos: "#3fb950",
  neg: "#f85149",
  grid: "#2a3038",
  text: "#8b949e",
};

const compactUsd = (n) =>
  n == null ? "" : `$${(n / 1000).toLocaleString("en-US", { maximumFractionDigits: 1 })}k`;

const tooltipStyle = {
  background: "#161b22",
  border: "1px solid #2a3038",
  borderRadius: 8,
  color: "#e6edf3",
  fontSize: 12,
};

const axis = { stroke: C.text, fontSize: 11 };

// Portfolio value vs SPY (both indexed off the same $100k start).
export function PortfolioVsSpyChart({ series }) {
  return (
    <div className="chart-wrap">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={series} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
          <CartesianGrid stroke={C.grid} strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="date" tick={axis} tickLine={false} axisLine={{ stroke: C.grid }} minTickGap={24} />
          <YAxis tick={axis} tickLine={false} axisLine={false} tickFormatter={compactUsd} domain={["auto", "auto"]} width={48} />
          <Tooltip contentStyle={tooltipStyle} formatter={(v) => compactUsd(v)} />
          <Legend wrapperStyle={{ fontSize: 12, color: C.text }} />
          <Line type="monotone" dataKey="portfolio_value" name="Portfolio" stroke={C.accent} strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="spy_close" name="SPY" stroke={C.spy} strokeWidth={2} strokeDasharray="4 3" dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// Day-over-day change in portfolio value.
export function DailyPnlChart({ series }) {
  const bars = series
    .map((d, i) => (i === 0 ? null : { date: d.date, pnl: d.portfolio_value - series[i - 1].portfolio_value }))
    .filter(Boolean);

  return (
    <div className="chart-wrap">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={bars} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
          <CartesianGrid stroke={C.grid} strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="date" tick={axis} tickLine={false} axisLine={{ stroke: C.grid }} minTickGap={24} />
          <YAxis tick={axis} tickLine={false} axisLine={false} tickFormatter={compactUsd} width={48} />
          <Tooltip contentStyle={tooltipStyle} formatter={(v) => `$${Math.round(v).toLocaleString("en-US")}`} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
          <Bar dataKey="pnl" name="Daily P&L">
            {bars.map((b) => (
              <Cell key={b.date} fill={b.pnl >= 0 ? C.pos : C.neg} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
