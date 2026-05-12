import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { Kpi } from "@/components/Kpi";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function JournalPage() {
  const rows = await api.journal();
  const symbols = new Set(rows.map((row) => String(row.symbol ?? "")).filter(Boolean));

  return (
    <>
      <div className="hero">
        <p className="muted">Journal</p>
        <h1>Thesis, exit notes, and lessons</h1>
      </div>
      <div className="kpiGrid">
        <Kpi label="Entries" value={String(rows.length)} />
        <Kpi label="Linked symbols" value={String(symbols.size)} />
      </div>
      <Card title="Journal Entries" subtitle="Write support is available through the FastAPI endpoint.">
        <DataTable rows={rows} columns={["when", "category", "symbol", "title", "body"]} />
      </Card>
    </>
  );
}
