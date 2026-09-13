import React, { useState, useRef, useEffect } from "react";
import { SlidersIcon, CheckIcon } from "./Icons";

export const EXPANDED_DOMAINS = [
  { id: "Database Management", label: "Database Management" },
  { id: "AI/ML", label: "AI & Machine Learning" },
  { id: "Theory of Computation", label: "Theory of Computation" },
  { id: "Computer Vision", label: "Computer Vision" },
  { id: "Operations Research", label: "Operations Research" },
  { id: "Web Frameworks", label: "Web Frameworks" },
  { id: "GenAI", label: "Generative AI & LLMs" },
  { id: "Big Data Systems", label: "Big Data Systems" },
  { id: "Cryptography", label: "Cryptography" },
  { id: "Network Security", label: "Network Security" },
  { id: "Full-Stack", label: "Full-Stack Systems" },
  { id: "DSA", label: "Data Structures & Algos" },
  { id: "CN", label: "Computer Networks" },
  { id: "DBMS", label: "DBMS & Storage Engines" },
];

export function FilterBar({
  selectedDomains = [],
  onToggleDomain,
  onClearDomains,
  domainCounts = {},
  minViability = 80,
  onViabilityChange,
  difficultyFilter = "ALL",
  onDifficultyChange,
  sortBy = "created_at",
  onSelectSort,
  totalMatching = 0,
  // Backward compatibility props:
  activeFilter,
  onSelectFilter
}) {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Determine effective selected domains
  const activeDomains = Array.isArray(selectedDomains) && selectedDomains.length > 0
    ? selectedDomains
    : (activeFilter && activeFilter !== "ALL" ? [activeFilter] : []);

  const isAllDomains = activeDomains.length === 0;

  const handleDomainClick = (domainId) => {
    if (onToggleDomain) {
      onToggleDomain(domainId);
    } else if (onSelectFilter) {
      onSelectFilter(domainId);
    }
  };

  const handleAllClick = () => {
    if (onClearDomains) {
      onClearDomains();
    } else if (onSelectFilter) {
      onSelectFilter("ALL");
    }
    setIsDropdownOpen(false);
  };

  const difficulties = ["ALL", "Beginner", "Intermediate", "Advanced", "Hardcore"];

  return (
    <div className="filter-wrapper">
      <div className="filter-controls-row">
        {/* 1. 14-Domain Multi-Select Dropdown */}
        <div className="multi-select-container" ref={dropdownRef}>
          <button
            type="button"
            className={`multi-select-trigger ${!isAllDomains ? "active-filter-highlight" : ""}`}
            onClick={() => setIsDropdownOpen((prev) => !prev)}
            aria-haspopup="listbox"
            aria-expanded={isDropdownOpen}
            aria-label="Filter by academic disciplines"
          >
            <span className="dropdown-label">DISCIPLINE:</span>
            <span className="dropdown-selection">
              {isAllDomains
                ? "All Disciplines (14)"
                : `${activeDomains.length} Domain${activeDomains.length > 1 ? "s" : ""} Selected`}
            </span>
            <span className="dropdown-arrow">{isDropdownOpen ? "▲" : "▼"}</span>
          </button>

          {isDropdownOpen && (
            <div className="multi-select-dropdown" role="listbox" aria-label="Available Software Domains">
              <div className="dropdown-header-bar">
                <span>14-DOMAIN TAXONOMY</span>
                {!isAllDomains && (
                  <button type="button" className="btn-clear-filters" onClick={handleAllClick}>
                    Reset to All
                  </button>
                )}
              </div>

              <div
                className={`dropdown-option ${isAllDomains ? "selected" : ""}`}
                onClick={handleAllClick}
                role="option"
                aria-selected={isAllDomains}
              >
                <div className="option-checkbox">
                  {isAllDomains && <CheckIcon />}
                </div>
                <span className="option-name">All Disciplines</span>
                <span className="option-count">
                  ({Object.values(domainCounts).reduce((a, b) => a + b, 0)})
                </span>
              </div>

              <div className="dropdown-divider"></div>

              <div className="dropdown-options-scroll">
                {EXPANDED_DOMAINS.map((dom) => {
                  const isChecked = activeDomains.includes(dom.id);
                  const count = domainCounts[dom.id] || 0;

                  return (
                    <div
                      key={dom.id}
                      className={`dropdown-option ${isChecked ? "selected" : ""}`}
                      onClick={() => handleDomainClick(dom.id)}
                      role="option"
                      aria-selected={isChecked}
                    >
                      <div className="option-checkbox">
                        {isChecked && <CheckIcon />}
                      </div>
                      <span className="option-name">{dom.label}</span>
                      {count > 0 && <span className="option-count">({count})</span>}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* 2. Viability Score Range Slider */}
        <div className="slider-control-group" aria-label="Viability Score Filter">
          <div className="slider-label-row">
            <span className="control-legend">
              <SlidersIcon /> VIABILITY SCORE:
            </span>
            <span className="slider-value-badge">≥ {minViability}</span>
          </div>
          <input
            type="range"
            min="80"
            max="98"
            step="1"
            value={minViability}
            onChange={(e) => onViabilityChange && onViabilityChange(Number(e.target.value))}
            className="swiss-range-slider"
            aria-label={`Minimum Viability Score (Current: ${minViability})`}
          />
        </div>

        {/* 3. Segmented Difficulty Toggle */}
        <div className="difficulty-segmented-group" role="group" aria-label="Implementation Difficulty">
          <span className="control-legend">DIFFICULTY:</span>
          <div className="segmented-chips">
            {difficulties.map((diff) => {
              const isActive = difficultyFilter === diff;
              return (
                <button
                  key={diff}
                  type="button"
                  className={`segmented-chip ${isActive ? "active" : ""}`}
                  onClick={() => onDifficultyChange && onDifficultyChange(diff)}
                  aria-pressed={isActive}
                >
                  {diff}
                </button>
              );
            })}
          </div>
        </div>

        {/* 4. Ordering & Match Counter */}
        {onSelectSort && (
          <div className="sort-control" aria-label="Card Ordering">
            <span className="sort-label">ORDER:</span>
            <button
              type="button"
              className={`sort-chip ${sortBy === "created_at" ? "active" : ""}`}
              onClick={() => onSelectSort("created_at")}
              title="Sort by latest ingested first"
            >
              Latest First
            </button>
            <button
              type="button"
              className={`sort-chip ${sortBy === "viability" ? "active" : ""}`}
              onClick={() => onSelectSort("viability")}
              title="Sort by highest viability score"
            >
              Highest Viability
            </button>
          </div>
        )}
      </div>

      {/* Active filters pill tray if specific domains selected */}
      {!isAllDomains && (
        <div className="active-filter-pills-row">
          <span className="pills-label">Active Disciplines:</span>
          {activeDomains.map((dom) => (
            <span key={dom} className="active-filter-pill">
              {dom}
              <button
                type="button"
                className="pill-remove-btn"
                onClick={() => handleDomainClick(dom)}
                aria-label={`Remove ${dom} filter`}
              >
                ×
              </button>
            </span>
          ))}
          <button type="button" className="clear-all-text-btn" onClick={handleAllClick}>
            Clear All
          </button>
        </div>
      )}
    </div>
  );
}
