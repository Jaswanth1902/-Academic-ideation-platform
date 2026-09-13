import React, { useState, useMemo } from "react";
import { GameCard } from "./GameCard";
import { PinFilledIcon, TableIcon, DownloadIcon, CompareIcon, SearchIcon, RefreshIcon } from "./Icons";

export function BookmarksPage({
  bookmarkedIdeas = [],
  onToggleBookmark,
  onFindSimilar,
  userSkills = "",
  onBackToExplore,
  onOpenCompare,
  onExportCsv,
  onExportDocx,
  onClearAll,
  isExportingCsv = false,
  isExportingDocx = false
}) {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedDomain, setSelectedDomain] = useState("ALL");

  // Dynamically compute all unique domains present in bookmarked items
  const availableDomains = useMemo(() => {
    const domainSet = new Set();
    bookmarkedIdeas.forEach((idea) => {
      const doms = Array.isArray(idea.domains) && idea.domains.length > 0
        ? idea.domains
        : [idea.domain || "Full-Stack"];
      doms.forEach((d) => domainSet.add(d));
    });
    return Array.from(domainSet).sort();
  }, [bookmarkedIdeas]);

  // Filter bookmarked ideas by search query and domain
  const filteredBookmarks = useMemo(() => {
    return bookmarkedIdeas.filter((idea) => {
      // Domain filter
      if (selectedDomain !== "ALL") {
        const itemDomains = Array.isArray(idea.domains) && idea.domains.length > 0
          ? idea.domains
          : [idea.domain];
        if (!itemDomains.includes(selectedDomain)) return false;
      }

      // Search query filter
      if (searchQuery.trim()) {
        const queryTokens = searchQuery.toLowerCase().split(/[\s,+/]+/).filter((t) => t.length > 1);
        const searchableText = [
          idea.title,
          idea.core_concept,
          idea.target_service,
          idea.novelty,
          idea.core_mechanism,
          Array.isArray(idea.tech_stack) ? idea.tech_stack.join(" ") : "",
          Array.isArray(idea.domains) ? idea.domains.join(" ") : idea.domain
        ].join(" ").toLowerCase();

        return queryTokens.every((token) => searchableText.includes(token));
      }

      return true;
    });
  }, [bookmarkedIdeas, selectedDomain, searchQuery]);

  const handleConfirmClear = () => {
    if (bookmarkedIdeas.length === 0) return;
    if (window.confirm(`Are you sure you want to remove all ${bookmarkedIdeas.length} bookmarked ideas?`)) {
      onClearAll && onClearAll();
    }
  };

  return (
    <div className="bookmarks-page-container">
      {/* Editorial Page Masthead */}
      <section className="bookmarks-masthead">
        <div className="bookmarks-nav-row">
          <button
            type="button"
            className="btn-back-explore"
            onClick={onBackToExplore}
            aria-label="Return to full catalog"
          >
            ← Return to Full Catalog
          </button>
          <div className="bookmarks-live-meta">
            <span className="telemetry-badge" style={{ color: "var(--swiss-accent)" }}>
              <PinFilledIcon /> PERSISTENT CURATION
            </span>
            <span className="telemetry-sep">/</span>
            <span>{bookmarkedIdeas.length} IDEAS KEPT IN MIND</span>
          </div>
        </div>

        <div className="bookmarks-title-row">
          <div>
            <h1 className="bookmarks-headline">
              My Bookmarked <span>Blueprints</span>
            </h1>
            <p className="bookmarks-subhead">
              Curated workspace containing all research-backed project blueprints you have saved to keep in mind.
              Filter, compare side-by-side, or export your selection directly to CSV and Word.
            </p>
          </div>

          <div className="bookmarks-actions-group">
            <button
              type="button"
              onClick={onOpenCompare}
              disabled={bookmarkedIdeas.length === 0}
              className={`btn-swiss-secondary ${bookmarkedIdeas.length > 0 ? "btn-compare-highlight" : ""}`}
              aria-label="Open Compare Matrix for bookmarked ideas"
              title={bookmarkedIdeas.length === 0 ? "Bookmark ideas to compare" : "Open side-by-side comparison matrix"}
            >
              <CompareIcon />
              <span>Compare Matrix ({bookmarkedIdeas.length})</span>
            </button>

            <button
              type="button"
              onClick={onExportCsv}
              disabled={isExportingCsv || bookmarkedIdeas.length === 0}
              className="btn-swiss-secondary"
              aria-label="Export Bookmarks as CSV"
              title="Export only your bookmarked ideas to an Excel-compatible CSV spreadsheet"
            >
              <TableIcon className={isExportingCsv ? "animate-bounce" : ""} />
              <span>{isExportingCsv ? "Exporting..." : "Export Bookmarks (.csv)"}</span>
            </button>

            <button
              type="button"
              onClick={onExportDocx}
              disabled={isExportingDocx || bookmarkedIdeas.length === 0}
              className="btn-swiss-secondary"
              aria-label="Export Bookmarks as Word DOCX"
              title="Compile all bookmarked blueprints into a single Word document proposal archive"
            >
              <DownloadIcon className={isExportingDocx ? "animate-bounce" : ""} />
              <span>{isExportingDocx ? "Compiling..." : "Export Bookmarks (.docx)"}</span>
            </button>

            {bookmarkedIdeas.length > 0 && (
              <button
                type="button"
                onClick={handleConfirmClear}
                className="btn-clear-bookmarks"
                aria-label="Clear all saved bookmarks"
                title="Remove all bookmarked blueprints"
              >
                Clear All
              </button>
            )}
          </div>
        </div>

        {/* Filter and In-Bookmark Search Bar */}
        {bookmarkedIdeas.length > 0 && (
          <div className="bookmarks-filter-toolbar">
            <div className="bookmarks-search-wrap">
              <span className="skills-matcher-icon"><SearchIcon /></span>
              <input
                type="text"
                className="bookmarks-search-input"
                placeholder="Search within your saved bookmarks..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                aria-label="Search within bookmarked ideas"
              />
              {searchQuery && (
                <button
                  type="button"
                  className="skills-clear-btn"
                  onClick={() => setSearchQuery("")}
                  aria-label="Clear search input"
                >
                  ×
                </button>
              )}
            </div>

            {availableDomains.length > 1 && (
              <div className="bookmarks-domain-pills">
                <button
                  type="button"
                  className={`domain-pill-btn ${selectedDomain === "ALL" ? "active" : ""}`}
                  onClick={() => setSelectedDomain("ALL")}
                >
                  All Domains ({bookmarkedIdeas.length})
                </button>
                {availableDomains.map((dom) => (
                  <button
                    key={dom}
                    type="button"
                    className={`domain-pill-btn ${selectedDomain === dom ? "active" : ""}`}
                    onClick={() => setSelectedDomain(dom)}
                  >
                    {dom}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </section>

      {/* Main Content Area */}
      {bookmarkedIdeas.length === 0 ? (
        <div className="bookmarks-empty-state">
          <div className="bookmarks-empty-icon-box">
            <PinFilledIcon />
          </div>
          <h2 className="bookmarks-empty-title">Your Bookmark Collection is Empty</h2>
          <p className="bookmarks-empty-desc">
            You haven't bookmarked any project ideas yet. Explore the research catalog and click the bookmark pin on any card to save it here for later review and side-by-side comparison.
          </p>
          <button
            type="button"
            className="btn-load-more"
            onClick={onBackToExplore}
            style={{ marginTop: "1rem" }}
          >
            Explore All Blueprints →
          </button>
        </div>
      ) : filteredBookmarks.length === 0 ? (
        <div className="bookmarks-empty-state" style={{ padding: "3rem 1.5rem" }}>
          <h2 className="bookmarks-empty-title">No Matching Bookmarks</h2>
          <p className="bookmarks-empty-desc">
            No saved ideas match your filter "{searchQuery}" {selectedDomain !== "ALL" ? `in ${selectedDomain}` : ""}.
          </p>
          <button
            type="button"
            className="btn-swiss-secondary"
            onClick={() => {
              setSearchQuery("");
              setSelectedDomain("ALL");
            }}
            style={{ marginTop: "1rem" }}
          >
            Reset Bookmark Filters
          </button>
        </div>
      ) : (
        <section className="masonry-layout" aria-label="Bookmarked Project Cards">
          {filteredBookmarks.map((idea) => (
            <GameCard
              key={idea.id || idea.title}
              idea={idea}
              isShortlisted={true}
              onToggleShortlist={onToggleBookmark}
              onFindSimilar={onFindSimilar}
              userSkills={userSkills}
            />
          ))}
        </section>
      )}
    </div>
  );
}
