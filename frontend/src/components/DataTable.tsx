interface Props {
  columns: string[];
  data: (string | number | null)[][];
}

export default function DataTable({ columns, data }: Props) {
  if (!columns.length) return null;

  return (
    <div style={{ overflowX: "auto", marginTop: 8 }}>
      <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 13 }}>
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col}
                style={{
                  textAlign: "left",
                  padding: "6px 10px",
                  borderBottom: "2px solid #ddd",
                  whiteSpace: "nowrap",
                }}
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i} style={{ background: i % 2 === 0 ? "#fafafa" : "#fff" }}>
              {row.map((cell, j) => (
                <td
                  key={j}
                  style={{
                    padding: "4px 10px",
                    borderBottom: "1px solid #eee",
                    whiteSpace: "nowrap",
                  }}
                >
                  {cell === null ? "—" : String(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {data.length === 0 && (
        <p style={{ color: "#888", textAlign: "center", padding: 16 }}>No data</p>
      )}
    </div>
  );
}
