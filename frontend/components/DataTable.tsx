import { asText } from "@/lib/api";

type DataTableProps = {
  rows: Array<Record<string, unknown>>;
  columns: string[];
};

export function DataTable({ rows, columns }: DataTableProps) {
  if (!rows.length) {
    return <p className="empty">No rows yet.</p>;
  }

  return (
    <div className="tableWrap">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 80).map((row, idx) => (
            <tr key={idx}>
              {columns.map((column) => (
                <td key={column}>{asText(row[column])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
