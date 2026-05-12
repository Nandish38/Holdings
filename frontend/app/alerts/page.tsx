import { Card } from "@/components/Card";
import { Kpi } from "@/components/Kpi";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function AlertsPage() {
  const alerts = await api.alerts();
  const alertCount = alerts.filter((flag) => flag.severity === "alert").length;
  const warnCount = alerts.filter((flag) => flag.severity === "warn").length;

  return (
    <>
      <div className="hero">
        <p className="muted">Alerts</p>
        <h1>Risk and data-quality checks</h1>
      </div>
      <div className="kpiGrid">
        <Kpi label="Total flags" value={String(alerts.length)} />
        <Kpi label="Alerts" value={String(alertCount)} />
        <Kpi label="Warnings" value={String(warnCount)} />
      </div>
      <Card title="Current Flags">
        {alerts.length ? (
          alerts.map((flag) => (
            <div className={`flag ${flag.severity}`} key={`${flag.title}-${flag.symbols.join("-")}`}>
              <strong>{flag.title}</strong>
              <p>{flag.detail}</p>
              {flag.symbols.length ? <small>{flag.symbols.join(", ")}</small> : null}
            </div>
          ))
        ) : (
          <p className="empty">No flags right now.</p>
        )}
      </Card>
    </>
  );
}
