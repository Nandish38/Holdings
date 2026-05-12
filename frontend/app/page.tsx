import { Card } from "@/components/Card";
import { Kpi } from "@/components/Kpi";
import { api, formatCad } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const [summary, alerts] = await Promise.all([api.summary(), api.alerts()]);

  return (
    <>
      <div className="hero">
        <p className="muted">Portfolio intelligence</p>
        <h1>One place for allocation, returns, notes, and risk.</h1>
      </div>
      <div className="kpiGrid">
        <Kpi label="Portfolio value" value={formatCad(summary.total_cad)} hint="Approx CAD" />
        <Kpi label="Positions" value={String(summary.positions)} hint="Current holdings file" />
        <Kpi label="Top position" value={summary.top_position ?? "—"} hint="By market value" />
        <Kpi label="Open alerts" value={String(alerts.length)} hint="Rules and portfolio checks" />
      </div>
      <div className="grid">
        <Card title="Current Snapshot" subtitle="FastAPI reads the same Python logic as Streamlit.">
          <p>As of: {summary.as_of ?? "unknown"}</p>
          <p>Unrealized: {formatCad(summary.unrealized)}</p>
        </Card>
        <Card title="Migration Status" subtitle="Streamlit remains available while this frontend reaches parity.">
          <p>Backend: FastAPI on port 8000</p>
          <p>Frontend: Next.js on port 3000</p>
        </Card>
      </div>
    </>
  );
}
