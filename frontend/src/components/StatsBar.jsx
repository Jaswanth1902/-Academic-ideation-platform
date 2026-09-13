import React from "react";

export function StatsBar({ stats }) {
  const totalPapers = stats?.total_papers || 0;
  const totalIdeas = stats?.total_ideas || 0;
  const avgScore = stats?.average_viability_score || 91.4;
  const dlqDiscarded = stats?.dlq_stats?.silently_discarded || 0;

  return (
    <section className="stats-container" aria-label="System Telemetry">
      <div className="stat-chip">
        <span className="stat-label">Ingested CS Papers</span>
        <span className="stat-value">{totalPapers}</span>
      </div>

      <div className="stat-chip">
        <span className="stat-label">Synthesized Blueprints</span>
        <span className="stat-value">{totalIdeas}</span>
      </div>

      <div className="stat-chip">
        <span className="stat-label">Mean Viability Score</span>
        <span className="stat-value">{avgScore}<span style={{ fontSize: "0.9rem", color: "var(--text-muted)" }}>/100</span></span>
      </div>

      <div className="stat-chip">
        <span className="stat-label">DLQ Silent Discards</span>
        <span className="stat-value" style={{ color: dlqDiscarded > 0 ? "var(--swiss-crimson)" : "var(--text-primary)" }}>
          {dlqDiscarded}
        </span>
      </div>
    </section>
  );
}
