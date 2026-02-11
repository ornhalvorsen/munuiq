import { useEffect, useState } from "react";
import Chat from "./components/Chat";
import Dashboard from "./components/Dashboard";
import { MODELS } from "./types";
import type { ModelId } from "./types";
import { getHealth } from "./api/client";

const tabs = ["Chat", "Dashboard"] as const;
type Tab = (typeof tabs)[number];

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("Chat");
  const [model, setModel] = useState<ModelId>("claude-haiku-4-5-20251001");
  const [ollamaAvailable, setOllamaAvailable] = useState(false);

  useEffect(() => {
    getHealth()
      .then((h) => setOllamaAvailable(h.ollama_available))
      .catch(() => setOllamaAvailable(false));
  }, []);

  const isDisabled = (m: (typeof MODELS)[number]) =>
    m.provider === "ollama" && !ollamaAvailable;

  return (
    <div style={{ maxWidth: 960, margin: "0 auto", padding: "20px 16px" }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>MUNUIQ</h1>
      <p style={{ color: "#6b7280", fontSize: 13, marginBottom: 16 }}>
        Restaurant AI Analytics
      </p>

      {/* Model selector */}
      <div
        style={{
          display: "flex",
          gap: 8,
          marginBottom: 16,
          alignItems: "center",
          flexWrap: "wrap",
        }}
      >
        <span style={{ fontSize: 13, color: "#6b7280", marginRight: 4 }}>Model:</span>
        {MODELS.map((m) => {
          const disabled = isDisabled(m);
          const selected = model === m.id;
          return (
            <button
              key={m.id}
              onClick={() => !disabled && setModel(m.id)}
              disabled={disabled}
              title={disabled ? "Ollama not running" : m.id}
              style={{
                padding: "5px 14px",
                fontSize: 13,
                fontWeight: selected ? 600 : 400,
                color: disabled ? "#9ca3af" : selected ? "#fff" : m.color,
                background: disabled
                  ? "#f3f4f6"
                  : selected
                    ? m.color
                    : "transparent",
                border: `1.5px solid ${disabled ? "#d1d5db" : m.color}`,
                borderRadius: 20,
                cursor: disabled ? "not-allowed" : "pointer",
                transition: "all 0.15s",
                opacity: disabled ? 0.6 : 1,
              }}
            >
              {m.label}
            </button>
          );
        })}
        {!ollamaAvailable && (
          <span style={{ fontSize: 11, color: "#9ca3af", marginLeft: 4 }}>
            Ollama offline
          </span>
        )}
      </div>

      {/* Tab bar */}
      <div
        style={{
          display: "flex",
          gap: 0,
          marginBottom: 20,
          borderBottom: "2px solid #e5e7eb",
        }}
      >
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: "8px 20px",
              fontSize: 14,
              fontWeight: activeTab === tab ? 600 : 400,
              color: activeTab === tab ? "#4f46e5" : "#6b7280",
              background: "none",
              border: "none",
              borderBottom:
                activeTab === tab ? "2px solid #4f46e5" : "2px solid transparent",
              cursor: "pointer",
              marginBottom: -2,
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      {activeTab === "Chat" && <Chat model={model} />}
      {activeTab === "Dashboard" && <Dashboard model={model} />}
    </div>
  );
}
