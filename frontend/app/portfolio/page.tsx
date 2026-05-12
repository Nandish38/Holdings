import { BarList } from "@/components/BarList";
import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { Kpi } from "@/components/Kpi";
import { api, formatCad } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function PortfolioPage() {
  const [summary, allocation, holdings] = await Promise.all([api.summary(), api.allocation(), api.holdings()]);
  const rows = holdings.map((row) => row.data);

  return (
    <>
      <div className="hero">
        <p className="muted">Portfolio</p>
        <h1>Holdings and allocation</h1>
      </div>
      <div className="kpiGrid">
        <Kpi label="Portfolio value" value={formatCad(summary.total_cad)} />
        <Kpi label="Positions" value={String(summary.positions)} />
        <Kpi label="Unrealized" value={formatCad(summary.unrealized)} />
      </div>
      <div className="grid">
        <Card title="Security Type">
          <BarList rows={allocation.security_type} labelKey="Security Type" />
        </Card>
        <Card title="Currency">
          <BarList rows={allocation.currency} labelKey="mv_ccy" />
        </Card>
        <Card title="Accounts">
          <BarList rows={allocation.accounts} labelKey="label" />
        </Card>
        <Card title="Top Symbols">
          <BarList rows={allocation.symbols} labelKey="Symbol" />
        </Card>
      </div>
      <Card title="Holdings" subtitle="First 80 rows from the current CSV export.">
        <DataTable rows={rows} columns={["Account Name", "Symbol", "Name", "Security Type", "mv_ccy", "Market Value", "market_value_cad"]} />
      </Card>
    </>
  );
}
