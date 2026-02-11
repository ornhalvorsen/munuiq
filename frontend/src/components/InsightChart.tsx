import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { ChartSpec } from "../types";

interface Props {
  chart: ChartSpec;
  columns: string[];
  data: (string | number | null)[][];
}

export default function InsightChart({ chart, columns, data }: Props) {
  if (chart.chart_type === "none" || !chart.x_key || !chart.y_key) return null;

  const xIdx = columns.indexOf(chart.x_key);
  const yIdx = columns.indexOf(chart.y_key);
  if (xIdx === -1 || yIdx === -1) return null;

  const chartData = data.slice(0, 30).map((row) => ({
    [chart.x_key]: row[xIdx],
    [chart.y_key]: Number(row[yIdx]) || 0,
  }));

  const common = (
    <>
      <CartesianGrid strokeDasharray="3 3" />
      <XAxis dataKey={chart.x_key} tick={{ fontSize: 11 }} />
      <YAxis tick={{ fontSize: 11 }} />
      <Tooltip />
    </>
  );

  return (
    <div style={{ marginTop: 12 }}>
      {chart.title && (
        <p style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>{chart.title}</p>
      )}
      <ResponsiveContainer width="100%" height={240}>
        {chart.chart_type === "line" ? (
          <LineChart data={chartData}>
            {common}
            <Line type="monotone" dataKey={chart.y_key} stroke="#4f46e5" strokeWidth={2} />
          </LineChart>
        ) : (
          <BarChart data={chartData}>
            {common}
            <Bar dataKey={chart.y_key} fill="#4f46e5" radius={[4, 4, 0, 0]} />
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
