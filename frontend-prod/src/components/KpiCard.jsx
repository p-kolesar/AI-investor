// One KPI tile: label + big value. `tone` colors the value (pos/neg/dim).
export function KpiCard({ label, value, tone = "" }) {
  return (
    <div className="kpi-card">
      <div className="label">{label}</div>
      <div className={`value ${tone}`}>{value}</div>
    </div>
  );
}
