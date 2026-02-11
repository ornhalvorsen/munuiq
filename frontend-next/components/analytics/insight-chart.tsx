"use client";

import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";

interface ChartSpec {
  chart_type: string;
  x_key: string;
  y_key: string;
  title: string;
}

interface InsightChartProps {
  chart: ChartSpec;
  columns: string[];
  data: (string | number | null)[][];
}

export function InsightChart({ chart, columns, data }: InsightChartProps) {
  if (!chart || chart.chart_type === "none" || !chart.x_key || !chart.y_key) {
    return null;
  }

  const xIdx = columns.indexOf(chart.x_key);
  const yIdx = columns.indexOf(chart.y_key);
  if (xIdx === -1 || yIdx === -1) return null;

  const chartData = data.slice(0, 30).map((row) => ({
    [chart.x_key]: row[xIdx],
    [chart.y_key]: Number(row[yIdx]) || 0,
  }));

  if (chartData.length === 0) return null;

  const ChartComponent = chart.chart_type === "line" ? LineChart : BarChart;

  return (
    <div className="mt-4">
      {chart.title && (
        <h4 className="mb-2 text-sm font-medium">{chart.title}</h4>
      )}
      <ResponsiveContainer width="100%" height={250}>
        <ChartComponent data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey={chart.x_key}
            tick={{ fontSize: 11 }}
            interval="preserveStartEnd"
          />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          {chart.chart_type === "line" ? (
            <Line
              type="monotone"
              dataKey={chart.y_key}
              stroke="hsl(var(--primary))"
              strokeWidth={2}
            />
          ) : (
            <Bar dataKey={chart.y_key} fill="hsl(var(--primary))" />
          )}
        </ChartComponent>
      </ResponsiveContainer>
    </div>
  );
}
