// Shared async-state placeholders used by every view.

export function Loading({ label = "Loading…" }) {
  return <div className="state">{label}</div>;
}

export function ErrorState({ error }) {
  return <div className="state error">Failed to load: {String(error?.message ?? error)}</div>;
}

export function Empty({ label = "Nothing to show yet." }) {
  return <div className="state">{label}</div>;
}
