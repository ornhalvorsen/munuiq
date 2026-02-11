import { useEffect, useState } from "react";
import { getDashboard } from "../api/client";
import type { DashboardCard as DashboardCardType, ModelId } from "../types";
import DataTable from "./DataTable";
import InsightChart from "./InsightChart";

export default function Dashboard({ model }: { model: ModelId }) {
  const [cards, setCards] = useState<DashboardCardType[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [cached, setCached] = useState(false);
  const [loadedModel, setLoadedModel] = useState<string>("");

  useEffect(() => {
    // Only fetch if model changed or no data yet
    if (loadedModel === model && cards.length > 0) return;

    setLoading(true);
    setError("");
    getDashboard(model)
      .then((res) => {
        setCards(res.cards);
        setCached(res.cached);
        setLoadedModel(model);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load dashboard"))
      .finally(() => setLoading(false));
  }, [model]);

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: 40, color: "#6b7280" }}>
        Generating dashboard insights... (this may take a moment)
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ color: "#dc2626", background: "#fef2f2", padding: 16, borderRadius: 8 }}>
        {error}
      </div>
    );
  }

  return (
    <div>
      {cached && (
        <p style={{ fontSize: 12, color: "#9ca3af", marginBottom: 12 }}>
          Showing cached results (10 min TTL)
        </p>
      )}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(400px, 1fr))",
          gap: 16,
        }}
      >
        {cards.map((card, i) => (
          <div
            key={i}
            style={{
              border: "1px solid #e5e7eb",
              borderRadius: 8,
              padding: 16,
            }}
          >
            <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>{card.title}</h3>
            <p style={{ color: "#374151", fontSize: 13, marginBottom: 8 }}>{card.insight}</p>
            <InsightChart chart={card.chart} columns={card.columns} data={card.data} />
            <DataTable columns={card.columns} data={card.data} />
          </div>
        ))}
      </div>
    </div>
  );
}
