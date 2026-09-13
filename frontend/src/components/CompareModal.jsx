import React, { useState, useEffect } from "react";
import { CloseIcon, LayerIcon, PinFilledIcon } from "./Icons";

export function CompareModal({ ideas = [], isOpen, onClose, onRemoveFromCompare }) {
  const [selectedIds, setSelectedIds] = useState([]);

  useEffect(() => {
    if (isOpen && ideas.length > 0) {
      // Default to the first 3 ideas
      setSelectedIds(ideas.slice(0, 3).map((i) => i.id));
    }
  }, [isOpen, ideas.length]);

  if (!isOpen) return null;

  const toggleSelectIdea = (id) => {
    setSelectedIds((prev) => {
      if (prev.includes(id)) {
        if (prev.length <= 1) return prev; // Keep at least one selected
        return prev.filter((item) => item !== id);
      } else {
        if (prev.length >= 3) {
          // Replace the last item to keep max 3
          return [prev[0], prev[1], id];
        }
        return [...prev, id];
      }
    });
  };

  const displayedIdeas = ideas.length <= 3
    ? ideas
    : ideas.filter((i) => selectedIds.includes(i.id));

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-label="Compare Project Blueprints">
      <div className="modal-content comparison-modal-container" onClick={(e) => e.stopPropagation()}>
        {/* Modal Header */}
        <div className="modal-header-row">
          <div className="modal-title-wrap">
            <span className="telemetry-badge" style={{ color: "var(--swiss-accent)" }}>
              <LayerIcon /> SIDE-BY-SIDE SELECTION MATRIX
            </span>
            <h2 className="modal-headline">
              Compare Project <span>Blueprints</span> ({displayedIdeas.length}/3)
            </h2>
          </div>
          <button
            type="button"
            className="modal-close-btn"
            onClick={onClose}
            aria-label="Close Comparison Modal"
          >
            <CloseIcon />
          </button>
        </div>

        {/* Multi-Bookmark Selector Strip (Only shown when user has > 3 bookmarks) */}
        {ideas.length > 3 && (
          <div className="compare-selector-bar">
            <span className="compare-selector-label">
              Comparing <strong>{displayedIdeas.length} of {ideas.length}</strong> bookmarked ideas (select up to 3):
            </span>
            <div className="compare-pills-row">
              {ideas.map((idea) => {
                const isSelected = selectedIds.includes(idea.id);
                return (
                  <button
                    key={idea.id}
                    type="button"
                    className={`compare-pill ${isSelected ? "compare-pill-active" : ""}`}
                    onClick={() => toggleSelectIdea(idea.id)}
                    aria-pressed={isSelected}
                  >
                    <span className="compare-pill-check">{isSelected ? "✓" : "+"}</span>
                    <span className="compare-pill-title">{idea.title}</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Modal Body: Comparison Table */}
        <div className="comparison-table-wrapper">
          {displayedIdeas.length === 0 ? (
            <div className="comparison-empty-state">
              <p>No project blueprints selected for comparison.</p>
              <span>Click the pin icon on any cards or select from your saved bookmarks.</span>
            </div>
          ) : (
            <table className="comparison-matrix-table">
              <thead>
                <tr>
                  <th className="matrix-metric-header">Attribute</th>
                  {displayedIdeas.map((idea) => (
                    <th key={idea.id || idea.title} className="matrix-idea-header">
                      <div className="matrix-header-card">
                        <div className="matrix-domain-row">
                          <span className={`domain-badge domain-${idea.domain || "Full-Stack"}`}>
                            {idea.domain || "Full-Stack"}
                          </span>
                          <button
                            type="button"
                            className="btn-remove-compare"
                            onClick={() => {
                              if (ideas.length > 3) {
                                toggleSelectIdea(idea.id);
                              } else {
                                onRemoveFromCompare(idea.id);
                              }
                            }}
                            title="Remove from comparison"
                            aria-label={`Remove ${idea.title} from comparison`}
                          >
                            ×
                          </button>
                        </div>
                        <h3 className="matrix-idea-title">{idea.title}</h3>
                        <div className="matrix-score-badge">
                          Viability: <strong>{idea.viability_score || 90}</strong> • {idea.difficulty || "Advanced"}
                        </div>
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="matrix-metric-label">Core Concept</td>
                  {displayedIdeas.map((idea) => (
                    <td key={idea.id} className="matrix-metric-val">
                      {idea.core_concept || idea.summary?.split(".")[0] || "—"}
                    </td>
                  ))}
                </tr>

                <tr>
                  <td className="matrix-metric-label">Data Structures & Core Mechanism</td>
                  {displayedIdeas.map((idea) => (
                    <td key={idea.id} className="matrix-metric-val">
                      <span className="code-text-highlight">
                        {idea.core_mechanism || "Algorithmic state synchronization"}
                      </span>
                    </td>
                  ))}
                </tr>

                <tr>
                  <td className="matrix-metric-label">Architectural Novelty</td>
                  {displayedIdeas.map((idea) => (
                    <td key={idea.id} className="matrix-metric-val">
                      {idea.novelty || idea.core_mechanism || "—"}
                    </td>
                  ))}
                </tr>

                <tr>
                  <td className="matrix-metric-label">Target Service</td>
                  {displayedIdeas.map((idea) => (
                    <td key={idea.id} className="matrix-metric-val">
                      <span className="service-tag">{idea.target_service || `${idea.domain} Runtime Daemon`}</span>
                    </td>
                  ))}
                </tr>

                <tr>
                  <td className="matrix-metric-label">Tech Stack</td>
                  {displayedIdeas.map((idea) => {
                    let stack = idea.tech_stack;
                    if (typeof stack === "string") {
                      try { stack = JSON.parse(stack); } catch(e) { stack = []; }
                    }
                    if (!Array.isArray(stack)) stack = [];
                    return (
                      <td key={idea.id} className="matrix-metric-val">
                        <div className="tech-chips-row">
                          {stack.map((t, idx) => (
                            <span key={idx} className="tech-chip">{t}</span>
                          ))}
                        </div>
                      </td>
                    );
                  })}
                </tr>

                <tr>
                  <td className="matrix-metric-label">Timeline & Sprints</td>
                  {displayedIdeas.map((idea) => (
                    <td key={idea.id} className="matrix-metric-val">
                      <span className="feasibility-pill" style={{ display: "inline-block" }}>
                        ⏱ {idea.feasibility_timeline || "120 Hours / 4 Sprints"}
                      </span>
                    </td>
                  ))}
                </tr>

                <tr>
                  <td className="matrix-metric-label">Grounded Paper</td>
                  {displayedIdeas.map((idea) => (
                    <td key={idea.id} className="matrix-metric-val paper-citation-cell">
                      <div className="paper-name">{idea.paper_title || "Literature Reference"}</div>
                      <div className="paper-submeta">
                        {idea.paper_authors} ({idea.publication_year || 2023}) • {idea.cited_by_count || 10} cites
                      </div>
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          )}
        </div>

        {/* Modal Footer */}
        <div className="modal-footer-row">
          <div className="modal-footer-tip">
            {ideas.length > 3
              ? `You have ${ideas.length} bookmarked ideas. Showing ${displayedIdeas.length} selected in side-by-side comparison.`
              : "Tip: Bookmark any project ideas to compare them side-by-side before thesis or capstone submission."}
          </div>
          <button type="button" className="btn-swiss-secondary" onClick={onClose}>
            Close Matrix
          </button>
        </div>
      </div>
    </div>
  );
}
