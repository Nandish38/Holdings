import { Card } from "@/components/Card";
import { Kpi } from "@/components/Kpi";
import { api } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function MarketsPage() {
  const universes = await api.universes();
  const total = universes.reduce((acc, item) => acc + item.symbols.length, 0);

  return (
    <>
      <div className="hero">
        <p className="muted">Markets</p>
        <h1>Market universes</h1>
      </div>
      <div className="kpiGrid">
        <Kpi label="Universes" value={String(universes.length)} />
        <Kpi label="Tracked symbols" value={String(total)} />
      </div>
      <div className="grid">
        {universes.map((universe) => (
          <Card key={universe.key} title={universe.label} subtitle={`${universe.symbols.length} symbols`}>
            <p>{universe.symbols.slice(0, 24).join(", ") || "Curated list is loaded by the backend watch table."}</p>
          </Card>
        ))}
      </div>
    </>
  );
}
