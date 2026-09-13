import React from "react";
import { RefreshIcon, DownloadIcon, TableIcon, CompareIcon, SearchIcon, PinIcon, PinFilledIcon } from "./Icons";

export function Header({
  onTriggerPipeline,
  isRunning,
  onBulkExport,
  isExportingBulk = false,
  onExportCsv,
  isExportingCsv = false,
  allowIot,
  onToggleIot,
  runtimeStatus = "Idle",
  serverPort = "8055",
  dbStatus = "SQLite Connected",
  // Skills Matcher & Compare Modal additions:
  skillsQuery = "",
  onSkillsQueryChange,
  shortlistedCount = 0,
  totalIdeasCount = 0,
  activeView = "explore",
  onSelectView,
  onOpenCompare
}) {
  return (
    <header className="masthead-container">
      {/* Live Runtime Telemetry Banner & Dynamic Toggle */}
      <div className="telemetry-banner-row">
        <div className="telemetry-stream">
          <span className="telemetry-badge">
            <span className={`status-pulse ${isRunning ? "pulse-active" : "pulse-idle"}`}></span>
            STATUS: {isRunning ? "INGESTING..." : runtimeStatus.toUpperCase()}
          </span>
          <span className="telemetry-sep">/</span>
          <span className="telemetry-meta">PORT: {serverPort}</span>
          <span className="telemetry-sep">/</span>
          <span className="telemetry-meta">DB: {dbStatus.toUpperCase()}</span>
          <span className="telemetry-sep">/</span>
          <span className="telemetry-meta">FEED: OPENALEX + ARXIV CS (14 DOMAINS)</span>
        </div>

        {/* Dynamic Two-State Toggle: Software-Only vs Include IoT */}
        <div className="iot-toggle-container" role="region" aria-label="Ingestion Domain Filter Mode">
          <span className="toggle-legend">DOMAIN FILTER:</span>
          <div className="swiss-toggle-group" role="group">
            <button
              type="button"
              className={`swiss-toggle-btn ${!allowIot ? "active" : ""}`}
              onClick={() => onToggleIot(false)}
              aria-pressed={!allowIot}
              title="Software-Only: Strictly exclude IoT, embedded sensors, and hardware"
            >
              Software-Only
            </button>
            <button
              type="button"
              className={`swiss-toggle-btn ${allowIot ? "active" : ""}`}
              onClick={() => onToggleIot(true)}
              aria-pressed={allowIot}
              title="Include IoT: Permit edge computing and distributed IoT protocol architectures"
            >
              Include IoT
            </button>
          </div>
        </div>
      </div>

      {/* Primary View Switcher Navigation Tabs */}
      {onSelectView && (
        <nav className="view-nav-tabs" aria-label="Catalog and Bookmarks Navigation">
          <button
            type="button"
            className={`view-tab-btn ${activeView === "explore" ? "view-tab-active" : ""}`}
            onClick={() => onSelectView("explore")}
            aria-pressed={activeView === "explore"}
          >
            Explore Catalog ({totalIdeasCount})
          </button>
          <button
            type="button"
            className={`view-tab-btn ${activeView === "bookmarks" ? "view-tab-active" : ""}`}
            onClick={() => onSelectView("bookmarks")}
            aria-pressed={activeView === "bookmarks"}
          >
            <PinFilledIcon />
            <span>My Bookmarked Ideas</span>
            <span className={`tab-counter-badge ${shortlistedCount > 0 ? "tab-counter-highlight" : ""}`}>
              {shortlistedCount}
            </span>
          </button>
        </nav>
      )}

      <div className="masthead-title-row">
        <div>
          <h1 className="editorial-headline">
            Academic Project <span>Ideation</span>
          </h1>
          <p className="editorial-subhead">
            Autonomous synthesis pipeline translating peer-reviewed Computer Science literature into
            rigorous software architectures, data structures, and milestone roadmaps.
          </p>
        </div>

        <div className="masthead-actions-group">
          {/* Quick-Jump to Bookmarks */}
          {onSelectView && (
            <button
              type="button"
              onClick={() => onSelectView("bookmarks")}
              className={`btn-swiss-secondary ${activeView === "bookmarks" ? "active-view-btn" : (shortlistedCount > 0 ? "btn-bookmark-badge" : "")}`}
              aria-label={`View ${shortlistedCount} bookmarked ideas`}
              title="View your saved collection of bookmarked blueprints"
            >
              {shortlistedCount > 0 ? <PinFilledIcon /> : <PinIcon />}
              <span>Bookmarks ({shortlistedCount})</span>
            </button>
          )}

          {/* Compare Modal Trigger */}
          <button
            type="button"
            onClick={onOpenCompare}
            disabled={shortlistedCount === 0}
            className={`btn-swiss-secondary ${shortlistedCount > 0 ? "btn-compare-highlight" : ""}`}
            aria-label={`Open side-by-side comparison for ${shortlistedCount} shortlisted ideas`}
            title={shortlistedCount === 0 ? "Shortlist ideas by pinning them to compare" : "Open side-by-side comparison matrix"}
          >
            <CompareIcon />
            <span>Compare Matrix ({shortlistedCount})</span>
          </button>

          <button
            type="button"
            onClick={onExportCsv}
            disabled={isExportingCsv || isRunning}
            className="btn-swiss-secondary"
            aria-label="Export All Project Blueprints as Lightweight CSV"
            title="Export all project blueprints as a lightweight, lightning-fast CSV spreadsheet"
          >
            <TableIcon className={isExportingCsv ? "animate-bounce" : ""} />
            <span>{isExportingCsv ? "Exporting CSV..." : "Export CSV"}</span>
          </button>

          <button
            type="button"
            onClick={onBulkExport}
            disabled={isExportingBulk || isRunning}
            className="btn-swiss-secondary"
            aria-label="Bulk Export All Project Blueprints to Word DOCX"
            title="Download comprehensive master DOCX archive with methodology preface, trademark signature, and all project blueprints"
          >
            <DownloadIcon className={isExportingBulk ? "animate-bounce" : ""} />
            <span>{isExportingBulk ? "Compiling Archive..." : "Bulk Export All (.docx)"}</span>
          </button>

          <button
            type="button"
            onClick={onTriggerPipeline}
            disabled={isRunning}
            className="btn-swiss-action"
            aria-label="Trigger OpenAlex Research Ingestion Pipeline"
          >
            <RefreshIcon className={isRunning ? "animate-spin" : ""} />
            <span>{isRunning ? "Ingesting Literature..." : "Trigger Ingest Cycle"}</span>
          </button>
        </div>
      </div>

      {/* Skills Matcher & Gap Analyzer Input Bar */}
      {onSkillsQueryChange && (
        <div className="skills-matcher-container">
          <div className="skills-matcher-input-wrap">
            <span className="skills-matcher-icon"><SearchIcon /></span>
            <input
              type="text"
              className="skills-matcher-input"
              value={skillsQuery}
              onChange={(e) => onSkillsQueryChange(e.target.value)}
              placeholder="My Skills (e.g. React, Python, SQL, Rust, Docker) — analyzes skill gaps & prioritizes matching blueprints..."
              aria-label="My skills input for skill gap analysis and ranking"
            />
            {skillsQuery && (
              <button
                type="button"
                className="skills-clear-btn"
                onClick={() => onSkillsQueryChange("")}
                aria-label="Clear skills filter"
              >
                ×
              </button>
            )}
          </div>
          {skillsQuery && (
            <div className="skills-active-indicator">
              <span>My Skills Active: "<strong>{skillsQuery}</strong>" (Skill Gap Analysis & Priority Sorting Active)</span>
            </div>
          )}
        </div>
      )}
    </header>
  );
}
