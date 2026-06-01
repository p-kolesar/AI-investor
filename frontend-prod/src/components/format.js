// Display formatters. Kept in one place so prod and beta format identically.

export const usd = (n) =>
  n == null
    ? "—"
    : n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });

export const pct = (n) => (n == null ? "—" : `${(n * 100).toFixed(2)}%`);

export const num = (n) => (n == null ? "—" : n.toLocaleString("en-US"));

export const signClass = (n) => (n == null ? "" : n > 0 ? "pos" : n < 0 ? "neg" : "");
