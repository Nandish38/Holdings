import { Card } from "@/components/Card";
import { Kpi } from "@/components/Kpi";
import { api, asText, formatCad } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function GoalsPage() {
  const goals = await api.goals();
  const accountTargets = (goals.account_targets_cad ?? {}) as Record<string, number>;

  return (
    <>
      <div className="hero">
        <p className="muted">Goals</p>
        <h1>Targets and guardrails</h1>
      </div>
      <div className="kpiGrid">
        <Kpi label="Portfolio target" value={formatCad(goals.target_portfolio_value_cad)} />
        <Kpi label="Months" value={asText(goals.months_to_goal)} />
        <Kpi label="Model return" value={`${asText(goals.target_annual_return_pct)}%`} />
      </div>
      <div className="grid">
        <Card title="Risk Limits">
          <p>Max position: {asText(goals.max_single_position_pct)}%</p>
          <p>Max non-index equity: {asText(goals.max_equity_non_index_pct)}%</p>
        </Card>
        <Card title="Account Targets">
          {Object.entries(accountTargets).length ? (
            Object.entries(accountTargets).map(([label, value]) => <p key={label}>{label}: {formatCad(value)}</p>)
          ) : (
            <p className="empty">No account targets set.</p>
          )}
        </Card>
        <Card title="Notes">
          <p>{asText(goals.notes)}</p>
        </Card>
      </div>
    </>
  );
}
