// Realized P&L and win rate from the trade ledger, using a running average cost
// per symbol (mirrors backend/trading.py: avg cost on buys, unchanged on sells).
// Returns { bySymbol: {SYM: {realized, closed, wins}}, totalRealized, closed, wins }.
export function realizedFromTrades(trades) {
  const bySymbol = {};
  // Process chronologically so average cost is correct when sells happen.
  const ordered = [...trades].sort((a, b) => String(a.date).localeCompare(String(b.date)));

  for (const t of ordered) {
    const s = (bySymbol[t.symbol] ??= { shares: 0, avgCost: 0, realized: 0, closed: 0, wins: 0 });
    if (t.side === "BUY") {
      const cost = s.shares * s.avgCost + t.shares * t.price;
      s.shares += t.shares;
      s.avgCost = s.shares ? cost / s.shares : 0;
    } else {
      // SELL: realize gain/loss against the running average cost.
      const pnl = (t.price - s.avgCost) * t.shares;
      s.realized += pnl;
      s.closed += 1;
      if (pnl > 0) s.wins += 1;
      s.shares -= t.shares;
    }
  }

  let totalRealized = 0;
  let closed = 0;
  let wins = 0;
  for (const s of Object.values(bySymbol)) {
    totalRealized += s.realized;
    closed += s.closed;
    wins += s.wins;
  }
  return { bySymbol, totalRealized, closed, wins };
}
