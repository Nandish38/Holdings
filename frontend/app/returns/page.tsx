import { BarList } from "@/components/BarList";
import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { Kpi } from "@/components/Kpi";
import { api, formatCad } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ReturnsPage() {
  const returns = await api.returns();

  return (
    <>
      <div className="hero">
        <p className="muted">Returns</p>
        <h1>Contribution-adjusted performance</h1>
      </div>
      <div className="kpiGrid">
        <Kpi label="Raw change" value={formatCad(returns.summary.raw_change_cad)} />
        <Kpi label="Net contributions" value={formatCad(returns.summary.net_contributions_cad)} />
        <Kpi label="Adjusted gain" value={formatCad(returns.summary.contribution_adjusted_gain_cad)} />
      </div>
      <div className="grid">
        <Card title="Latest Account Values">
          <BarList rows={returns.account_history.slice(-12)} labelKey="label" />
        </Card>
        <Card title="Latest Symbol Values">
          <BarList rows={returns.symbol_history.slice(-12)} labelKey="label" />
        </Card>
      </div>
      <Card title="History">
        <DataTable
          rows={returns.rows}
          columns={["date", "total_market_value_cad", "net_flow_cad", "cumulative_net_contributions", "contribution_adjusted_gain_cad", "source"]}
        />
      </Card>
    </>
  );
}
