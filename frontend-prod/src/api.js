// Single seam between the UI and the backend. Every view calls these functions
// and nothing else. Each returns the exact shape the Function App serves
// (see backend/function_app.py). When VITE_API_BASE is unset the app runs on
// stub/demo data so it works with no backend. In production the deploy workflow
// builds with VITE_API_BASE=https://<func-host>/api (cross-origin; the Function
// App's CORS allows the Static Web App origin) to hit the real API.

const API_BASE = import.meta.env.VITE_API_BASE ?? "";
const USE_STUBS = !API_BASE;

async function get(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`${path} -> ${res.status} ${res.statusText}`);
  return res.json();
}

// ---- Portfolio: { positions:[{symbol,shares,avg_cost,market_value}], cash, total_value }
export async function getPortfolio() {
  return USE_STUBS ? stub.portfolio() : get("/portfolio");
}

// ---- Trades: [{date,symbol,shares,price,side}]
export async function getTrades() {
  return USE_STUBS ? stub.trades() : get("/trades");
}

// ---- Agent log: { runs:[{run_date,..tokens,total_tokens,estimated_cost_usd,memo}], total_runs, cumulative_cost_usd }
export async function getAgentLog(limit = 30) {
  return USE_STUBS ? stub.agentLog(limit) : get(`/agent/log?limit=${limit}`);
}

// ---- Watchlist: { watchlist:[...], count }
export async function getWatchlist() {
  return USE_STUBS ? stub.watchlist() : get("/watchlist");
}

// ---- Daily snapshots: [{timestamp, positions:[{symbol,shares}], market_value, cash, total}]
// Most recent first. One row per agent run; market_value is live-marked at run time.
export async function getSnapshots(limit = 60) {
  return USE_STUBS ? stub.snapshots() : get(`/snapshots?limit=${limit}`);
}

// ---- Live quote: { symbol, price, open, high, low, cached }
export async function getPrice(symbol) {
  return USE_STUBS ? stub.price(symbol) : get(`/prices/${symbol}`);
}

// ---- Daily time-series for the charts. NOT served by the backend yet
// (benchmark.parquet is a stub, no /history endpoint). Phase 6 adds
// GET /api/history -> [{date, portfolio_value, spy_close}]. Until then this
// returns mock data and isStub:true so the UI can label the charts.
export async function getHistory() {
  if (USE_STUBS) return { series: stub.history(), isStub: true };
  // Real endpoint does not exist yet — fall back to mock, flagged as stub.
  return { series: stub.history(), isStub: true };
}

export const usingStubs = USE_STUBS;

// ---------------------------------------------------------------------------
// Stub / demo data. Shapes match the real endpoints 1:1 so swapping to live
// data (Phase 6) requires no view changes.
// ---------------------------------------------------------------------------

const STUB_QUOTES = {
  AAPL: 214.3, MSFT: 449.8, NVDA: 131.2, LLY: 812.5, JPM: 205.1, XOM: 112.4,
};

const stub = {
  portfolio: () => ({
    positions: [
      { symbol: "AAPL", shares: 60, avg_cost: 198.4, market_value: 12504.0 },
      { symbol: "MSFT", shares: 25, avg_cost: 421.1, market_value: 11245.0 },
      { symbol: "NVDA", shares: 90, avg_cost: 119.7, market_value: 11808.0 },
      { symbol: "LLY", shares: 12, avg_cost: 789.0, market_value: 9750.0 },
      { symbol: "JPM", shares: 50, avg_cost: 210.6, market_value: 10255.0 },
    ],
    cash: 44688.0,
    total_value: 100250.0,
  }),

  trades: () => [
    { date: "2026-05-19", symbol: "AAPL", shares: 60, price: 198.4, side: "BUY" },
    { date: "2026-05-19", symbol: "MSFT", shares: 25, price: 421.1, side: "BUY" },
    { date: "2026-05-20", symbol: "NVDA", shares: 90, price: 119.7, side: "BUY" },
    { date: "2026-05-22", symbol: "LLY", shares: 12, price: 789.0, side: "BUY" },
    { date: "2026-05-23", symbol: "JPM", shares: 50, price: 210.6, side: "BUY" },
    { date: "2026-05-28", symbol: "XOM", shares: 40, price: 118.2, side: "BUY" },
    { date: "2026-05-29", symbol: "XOM", shares: 40, price: 113.9, side: "SELL" },
  ],

  agentLog: (limit) => {
    const runs = [
      {
        run_date: "2026-05-29",
        level1_input_tokens: 2100, level1_output_tokens: 480,
        level2_input_tokens: 4300, level2_output_tokens: 1620,
        total_tokens: 8500, estimated_cost_usd: 0.043,
        memo: "Reduced XOM ahead of energy-sector softness; rotated nothing new. SPY flat. Holding AAPL/MSFT/NVDA core; LLY thesis intact pre-earnings.",
      },
      {
        run_date: "2026-05-28",
        level1_input_tokens: 1980, level1_output_tokens: 510,
        level2_input_tokens: 4100, level2_output_tokens: 1700,
        total_tokens: 8290, estimated_cost_usd: 0.041,
        memo: "Opened XOM on oversold RSI + analyst upgrade. Considered CAT but rejected on stretched valuation.",
      },
      {
        run_date: "2026-05-27",
        level1_input_tokens: 2040, level1_output_tokens: 460,
        level2_input_tokens: 0, level2_output_tokens: 0,
        total_tokens: 2500, estimated_cost_usd: 0.013,
        memo: "No deep dive — watchlist scan showed no setups meeting the entry criteria. Held all positions.",
      },
    ];
    return {
      runs: runs.slice(0, limit),
      total_runs: runs.length,
      cumulative_cost_usd: 0.097,
    };
  },

  watchlist: () => ({
    watchlist: ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "JPM", "BRK.B", "UNH", "LLY", "XOM", "CAT", "PG", "SPY", "QQQ"],
    count: 14,
  }),

  // Daily snapshots, most recent first (matches GET /snapshots).
  snapshots: () => [
    {
      timestamp: "2026-05-29 07:55:06",
      positions: [
        { symbol: "AAPL", shares: 60 }, { symbol: "MSFT", shares: 25 },
        { symbol: "NVDA", shares: 90 }, { symbol: "LLY", shares: 12 }, { symbol: "JPM", shares: 50 },
      ],
      market_value: 55562.0, cash: 44688.0, total: 100250.0,
    },
    {
      timestamp: "2026-05-28 07:55:11",
      positions: [
        { symbol: "AAPL", shares: 60 }, { symbol: "MSFT", shares: 25 },
        { symbol: "NVDA", shares: 90 }, { symbol: "LLY", shares: 12 },
        { symbol: "JPM", shares: 50 }, { symbol: "XOM", shares: 40 },
      ],
      market_value: 56114.0, cash: 39960.0, total: 96074.0,
    },
    {
      timestamp: "2026-05-27 07:55:09",
      positions: [
        { symbol: "AAPL", shares: 60 }, { symbol: "MSFT", shares: 25 },
        { symbol: "NVDA", shares: 90 }, { symbol: "LLY", shares: 12 }, { symbol: "JPM", shares: 50 },
      ],
      market_value: 51230.0, cash: 49020.0, total: 100250.0,
    },
  ],

  price: (symbol) => {
    const price = STUB_QUOTES[symbol] ?? 100 + Math.random() * 50;
    return {
      symbol,
      price: Number(price.toFixed(2)),
      open: Number((price * 0.995).toFixed(2)),
      high: Number((price * 1.012).toFixed(2)),
      low: Number((price * 0.988).toFixed(2)),
      cached: false,
    };
  },

  // 14 trading days of portfolio value vs SPY (indexed off the same $100k start).
  history: () => {
    const start = 100000;
    let pv = start;
    let spy = start;
    const out = [];
    for (let i = 0; i < 14; i++) {
      pv *= 1 + (Math.sin(i / 2) * 0.004 + 0.0009);
      spy *= 1 + (Math.sin(i / 2.3) * 0.0035 + 0.0006);
      const d = new Date(2026, 4, 16 + i); // May 2026
      out.push({
        date: d.toISOString().slice(0, 10),
        portfolio_value: Number(pv.toFixed(0)),
        spy_close: Number(spy.toFixed(0)),
      });
    }
    return out;
  },
};
