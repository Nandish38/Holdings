import { asText, formatCad } from "@/lib/api";

type BarListProps = {
  rows: Array<Record<string, unknown>>;
  labelKey: string;
  valueKey?: string;
};

export function BarList({ rows, labelKey, valueKey = "market_value_cad" }: BarListProps) {
  const max = Math.max(...rows.map((row) => Number(row[valueKey] ?? 0)), 1);

  if (!rows.length) {
    return <p className="empty">No rows yet.</p>;
  }

  return (
    <div className="barList">
      {rows.slice(0, 12).map((row, idx) => {
        const value = Number(row[valueKey] ?? 0);
        const width = `${Math.max(4, (value / max) * 100)}%`;
        return (
          <div className="barRow" key={`${asText(row[labelKey])}-${idx}`}>
            <div className="barMeta">
              <span>{asText(row[labelKey])}</span>
              <strong>{formatCad(value)}</strong>
            </div>
            <div className="barTrack">
              <div className="barFill" style={{ width }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
