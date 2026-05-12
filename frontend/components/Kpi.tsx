type KpiProps = {
  label: string;
  value: string;
  hint?: string;
};

export function Kpi({ label, value, hint }: KpiProps) {
  return (
    <div className="kpi">
      <span>{label}</span>
      <strong>{value}</strong>
      {hint ? <small>{hint}</small> : null}
    </div>
  );
}
