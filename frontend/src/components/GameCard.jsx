import React, { useState } from "react";
import { FlipIcon, PaperIcon, LayerIcon, ExternalLinkIcon, DownloadIcon, PinIcon, PinFilledIcon, SearchIcon } from "./Icons";

function GameCardComponent({
  idea,
  isShortlisted = false,
  onToggleShortlist,
  onFindSimilar,
  userSkills = ""
}) {
  const [isFlipped, setIsFlipped] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

  const toggleFlip = () => {
    setIsFlipped((prev) => !prev);
  };

  const handleExport = async (e) => {
    e.stopPropagation();
    setIsExporting(true);
    try {
      const targetId = idea.paper_id || idea.id;
      const res = await fetch(`http://localhost:8055/api/export/${targetId}`);
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const safeTitle = (idea.title || "Proposal").replace(/[^a-zA-Z0-9_-]/g, "_");
      a.download = `${safeTitle}_Proposal.docx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error("Export failed:", err);
      alert("Failed to export proposal document. Ensure the API server is active.");
    } finally {
      setIsExporting(false);
    }
  };

  const domains = Array.isArray(idea.domains) && idea.domains.length > 0
    ? idea.domains
    : [idea.domain || "Full-Stack"];
  const primaryDomain = domains[0];
  const viability = idea.viability_score || 90;
  const feasibilityTimeline = idea.feasibility_timeline || "120 Hours / 4 Sprints";
  const architecture = idea.architecture || {};
  const milestones = Array.isArray(idea.milestones) ? idea.milestones : [];
  const techStack = Array.isArray(idea.tech_stack) ? idea.tech_stack : [];

  // Scannable 4-point blueprint extraction with high-fidelity fallbacks
  const coreConcept = idea.core_concept || (idea.summary ? idea.summary.split(".")[0] + "." : "High-performance systems architecture implementation.");
  const targetService = idea.target_service || `${primaryDomain} Production Daemon / Runtime`;
  const novelty = idea.novelty || idea.core_mechanism || "Algorithmic and architectural optimization derived from recent literature.";
  const sellingPoint = idea.selling_point || "High-impact portfolio showcase for systems engineering and latency-critical design.";

  // Skill Gap Analyzer calculation against user's skills
  const userSkillsTokens = (userSkills || "")
    .toLowerCase()
    .split(/[\s,+/]+/)
    .map((s) => s.trim())
    .filter((s) => s.length > 1);

  const skillsYouHave = [];
  const skillsToLearn = [];

  if (userSkillsTokens.length > 0) {
    techStack.forEach((tech) => {
      const techLower = tech.toLowerCase();
      const hasMatch = userSkillsTokens.some(
        (token) => techLower.includes(token) || token.includes(techLower)
      );
      if (hasMatch) {
        skillsYouHave.push(tech);
      } else {
        skillsToLearn.push(tech);
      }
    });
  }

  return (
    <article className={`game-card-wrapper ${isShortlisted ? "card-shortlisted" : ""}`}>
      <div className={`game-card-inner ${isFlipped ? "is-flipped" : ""}`}>
        {/* FRONT FACE: Highly Scannable 4-Point Blueprint with Multi-Tagging */}
        <div className="game-card-face game-card-front apple-enterprise-card">
          <div className="card-header-row">
            <div className="card-domains-row">
              {domains.map((dom, idx) => (
                <span
                  key={idx}
                  className={`domain-badge domain-${dom.toLowerCase().replace(/[^a-z0-9]/g, '-')}`}
                >
                  {dom}
                </span>
              ))}
              {feasibilityTimeline && (
                <span className="feasibility-pill" title="Estimated Student Effort Timeline">
                  ⏱ {feasibilityTimeline}
                </span>
              )}
            </div>

            <div className="card-header-controls">
              <button
                type="button"
                className={`btn-pin-shortlist ${isShortlisted ? "active-pin" : ""}`}
                onClick={(e) => {
                  e.stopPropagation();
                  onToggleShortlist && onToggleShortlist(idea.id);
                }}
                title={isShortlisted ? "Remove from Shortlist" : "Bookmark / Shortlist Idea"}
                aria-label={isShortlisted ? "Remove from Shortlist" : "Bookmark / Shortlist Idea"}
                aria-pressed={isShortlisted}
              >
                {isShortlisted ? <PinFilledIcon /> : <PinIcon />}
              </button>

              <div className="viability-score-pill" title={`Viability Index: ${viability}/100`}>
                <span className="score-dot"></span>
                <span>{viability}</span>
                <span style={{ color: "var(--text-muted)", fontSize: "0.68rem" }}>INDEX</span>
              </div>
            </div>
          </div>

          <h2 className="project-title">{idea.title}</h2>

          {/* 4-Point Scannable List */}
          <div className="scannable-points-grid">
            <div className="point-row">
              <span className="point-badge">CORE CONCEPT</span>
              <p className="point-content">{coreConcept}</p>
            </div>

            <div className="point-row">
              <span className="point-badge">TARGET SERVICE</span>
              <p className="point-content">{targetService}</p>
            </div>

            <div className="point-row">
              <span className="point-badge">NOVELTY</span>
              <p className="point-content">{novelty}</p>
            </div>

            <div className="point-row">
              <span className="point-badge">SELLING POINT</span>
              <p className="point-content">{sellingPoint}</p>
            </div>
          </div>

          <div style={{ marginTop: "auto", paddingTop: "1.25rem" }}>
            <button
              type="button"
              className="btn-flip-trigger"
              onClick={toggleFlip}
              aria-label={`Inspect blueprint, architecture tiers, and paper citation for ${idea.title}`}
            >
              <FlipIcon />
              <span>Inspect Architecture & Paper</span>
            </button>
          </div>
        </div>
        {/* BACK FACE: Deep Academic Citations, Methodological Architecture & Skill Gap Analyzer */}
        <div className="game-card-face game-card-back apple-enterprise-card">
          <div className="card-header-row">
            <span className="blueprint-section-title">
              <LayerIcon /> System Architecture
            </span>
            <span className="domain-badge domain-default" style={{ fontSize: "0.68rem" }}>
              {idea.difficulty || "Advanced"}
            </span>
          </div>

          {/* Source Research Paper (Strictly on Back) */}
          <div className="source-paper-box">
            <div className="source-paper-label">
              <PaperIcon /> Grounded Research Paper
            </div>
            <div className="source-paper-title">{idea.paper_title || "Peer-Reviewed Academic Literature"}</div>
            {idea.paper_authors && (
              <div className="source-paper-authors">{idea.paper_authors}</div>
            )}
            <div className="source-paper-meta">
              <span>{idea.publication_year || 2023}</span>
              <span>•</span>
              <span>{idea.cited_by_count || 15} citations</span>
              {idea.doi && (
                <>
                  <span>•</span>
                  <a
                    href={idea.doi}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: "var(--swiss-accent)", textDecoration: "none", display: "inline-flex", alignItems: "center", gap: "2px" }}
                    aria-label={`Open DOI link for ${idea.paper_title}`}
                  >
                    DOI <ExternalLinkIcon />
                  </a>
                </>
              )}
            </div>
          </div>

          {/* Core Mechanism */}
          <div className="blueprint-block">
            <div className="blueprint-section-title">Core Mechanism</div>
            <p className="core-mech-text">{idea.core_mechanism}</p>
          </div>

          {/* Component Tiers / Deep Methodological Architecture */}
          {architecture && Object.keys(architecture).length > 0 && (
            <div className="blueprint-block">
              <div className="blueprint-section-title">Component Tiers</div>
              <div className="arch-grid">
                {Object.entries(architecture).map(([tier, desc]) => (
                  <div key={tier} className="arch-tier">
                    <div className="arch-tier-name">{tier.replace(/_/g, " ")}</div>
                    <div className="arch-tier-desc">{desc}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Implementation Milestones */}
          {milestones.length > 0 && (
            <div className="blueprint-block">
              <div className="blueprint-section-title">Implementation Roadmap</div>
              <div className="milestones-list">
                {milestones.map((m, idx) => (
                  <div key={idx} className="milestone-item">
                    <span className="milestone-phase">{m.phase}: </span>
                    <span>{m.goal}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Skill Gap Analyzer vs Production Tech Stack */}
          {userSkillsTokens.length > 0 ? (
            <div className="blueprint-block skill-gap-analyzer">
              <div className="blueprint-section-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span>Skill Gap Analyzer</span>
                <span className="skill-match-ratio" style={{ fontSize: "0.66rem", color: "var(--text-muted)" }}>
                  {skillsYouHave.length}/{techStack.length} Match
                </span>
              </div>
              <div className="skill-delta-group">
                {skillsYouHave.length > 0 && (
                  <div className="skill-delta-subgroup">
                    <div className="skill-delta-label text-success">✓ Skills You Have ({skillsYouHave.length})</div>
                    <div className="tech-chips-row">
                      {skillsYouHave.map((tech, idx) => (
                        <span key={idx} className="tech-chip chip-have">✓ {tech}</span>
                      ))}
                    </div>
                  </div>
                )}
                {skillsToLearn.length > 0 && (
                  <div className="skill-delta-subgroup" style={{ marginTop: skillsYouHave.length > 0 ? "0.35rem" : 0 }}>
                    <div className="skill-delta-label text-warning">▲ Skills to Learn ({skillsToLearn.length})</div>
                    <div className="tech-chips-row">
                      {skillsToLearn.map((tech, idx) => (
                        <span key={idx} className="tech-chip chip-learn">▲ {tech}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            techStack.length > 0 && (
              <div className="blueprint-block">
                <div className="blueprint-section-title">Production Tech Stack</div>
                <div className="tech-chips-row">
                  {techStack.map((tech, idx) => (
                    <span key={idx} className="tech-chip">{tech}</span>
                  ))}
                </div>
              </div>
            )
          )}

          <div className="card-actions-back" style={{ marginTop: "auto", paddingTop: "1rem", display: "flex", gap: "0.5rem" }}>
            <button
              type="button"
              className="btn-flip-trigger"
              style={{ flex: "1" }}
              onClick={toggleFlip}
              aria-label={`Flip back to overview for ${idea.title}`}
            >
              <FlipIcon />
              <span>Return</span>
            </button>
            <button
              type="button"
              className="btn-find-similar"
              style={{ flex: "1" }}
              onClick={(e) => {
                e.stopPropagation();
                onFindSimilar && onFindSimilar(idea);
              }}
              title="Find similar project blueprints matching domain(s) or tech stack"
              aria-label={`Find similar projects for ${idea.title}`}
            >
              <SearchIcon />
              <span>Find Similar</span>
            </button>
            <button
              type="button"
              className="btn-export-proposal"
              style={{ flex: "1.1" }}
              onClick={handleExport}
              disabled={isExporting}
              aria-label={`Export proposal document for ${idea.title}`}
            >
              <DownloadIcon />
              <span>{isExporting ? "Compiling..." : "Export"}</span>
            </button>
          </div>
        </div>
      </div>
    </article>
  );
}

function areEqual(prevProps, nextProps) {
  // Only re-render if key state or props changed
  if (prevProps.isShortlisted !== nextProps.isShortlisted) return false;
  if (prevProps.userSkills !== nextProps.userSkills) return false;
  if (prevProps.idea?.id !== nextProps.idea?.id) return false;
  if (prevProps.idea?.viability_score !== nextProps.idea?.viability_score) return false;
  if (prevProps.idea?.title !== nextProps.idea?.title) return false;
  if (prevProps.idea?.feasibility_timeline !== nextProps.idea?.feasibility_timeline) return false;
  if (prevProps.onToggleShortlist !== nextProps.onToggleShortlist) return false;
  if (prevProps.onFindSimilar !== nextProps.onFindSimilar) return false;
  return true;
}

export const GameCard = React.memo(GameCardComponent, areEqual);
export default GameCard;
