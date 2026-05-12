import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { Kpi } from "@/components/Kpi";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ActivityPage() {
  const rows = await api.activity();
  const kinds = new Set(rows.map((row) => String(row.kind ?? "note")));

  return (
    <>
      <div className="hero">
        <p className="muted">Activity</p>
        <h1>Buys, sells, deposits, and notes</h1>
      </div>
      <div className="kpiGrid">
        <Kpi label="Rows" value={String(rows.length)} />
        <Kpi label="Types" value={String(kinds.size)} />
      </div>
      <Card title="Activity Log" subtitle="Write support is available through the FastAPI endpoint.">
        <DataTable rows={rows} columns={["when", "kind", "symbol", "qty", "price", "ccy", "text"]} />
      </Card>
    </>
  );
}
