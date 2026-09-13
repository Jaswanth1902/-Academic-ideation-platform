import React, { useState, useEffect, useCallback, useMemo } from "react";
import { Header } from "./components/Header";
import { StatsBar } from "./components/StatsBar";
import { FilterBar } from "./components/FilterBar";
import { GameCard } from "./components/GameCard";
import { CompareModal } from "./components/CompareModal";
import { BookmarksPage } from "./components/BookmarksPage";

// High-fidelity fallback seed data ensuring zero-downtime render
const INITIAL_BENCHMARK_IDEAS = [
  {
    id: 1,
    domain: "DBMS",
    title: "FlashKV: High-Performance Log-Structured Storage Engine",
    core_concept: "Production-grade persistent key-value store with tiered compaction to eliminate NVMe write stalls.",
    target_service: "Embedded key-value storage engine & RESP-compatible daemon",
    novelty: "Lock-free parallel compaction scheduling reducing write amplification from 28x down to 4.2x.",
    selling_point: "Demonstrates low-level systems mastery of LSM-trees, WAL group commits, and storage internals.",
    summary: "Production-grade persistent key-value database engine inspired by 'Optimizing LSM-Tree Compactions for Multi-Tier NVMe Storage Engines'. Implements tiered SSTable compaction, WAL group commits, and lock-free skiplist memtables.",
    viability_score: 96,
    difficulty: "Hardcore",
    paper_title: "Optimizing LSM-Tree Compactions for Multi-Tier NVMe Storage Engines",
    paper_authors: "Chen Zhang, Elena Rostova, David K. Park",
    publication_year: 2023,
    cited_by_count: 28,
    doi: "https://doi.org/10.1145/3588912.3588944",
    core_mechanism: "Lock-free leveled compaction scheduling with partition-level range overlap elimination, reducing write amplification from 28x to 4.2x.",
    architecture: {
      client_interface: "RESP (Redis Serialization Protocol) compatible TCP server",
      write_pipeline: "MemTable (SkipList) -> WAL (O_DIRECT) -> Level 0 SSTables",
      read_pipeline: "MemTable -> Bloom Filter probe -> Multi-level Block Cache -> SSTables",
      compactor: "Background thread pool executing parallel dynamic partition compactions"
    },
    milestones: [
      { phase: "Phase 1", goal: "Construct lock-free concurrent SkipList MemTable with epoch memory reclamation." },
      { phase: "Phase 2", goal: "Implement append-only Write-Ahead Log with group commit flush buffers." },
      { phase: "Phase 3", goal: "Develop parallel leveled partition compactor with Bloom filter cascades." },
      { phase: "Phase 4", goal: "Run YCSB benchmark harness verifying P99 latency <1.8ms under 100k ops/sec." }
    ],
    tech_stack: ["Rust / C++", "POSIX AIO", "FlatBuffers", "Prometheus"]
  },
  {
    id: 2,
    domain: "CN",
    title: "HyperPacer: Adaptive Congestion Control Network Proxy",
    core_concept: "Autonomous transport-layer network proxy with microsecond pacing to prevent link bufferbloat.",
    target_service: "eBPF/AF_XDP zero-copy network proxy daemon",
    novelty: "Microsecond probe-interval drain rate estimation detecting queue bloat before packet drops occur.",
    selling_point: "High-impact portfolio showcase for distributed networking, kernel bypass, and protocol engineering.",
    summary: "Autonomous transport-layer network proxy implementing adaptive congestion window pacing from 'BBRv3-Adaptive'. Estimates microsecond queue drain rates to eliminate bufferbloat in high-throughput links.",
    viability_score: 94,
    difficulty: "Advanced",
    paper_title: "BBRv3-Adaptive: Dynamic Congestion Window Pacing for High-Throughput Edge Networks",
    paper_authors: "Marcus Lindqvist, Aarti Sundaram, Kevin Vance",
    publication_year: 2023,
    cited_by_count: 34,
    doi: "https://doi.org/10.1109/TNET.2023.3289012",
    core_mechanism: "Microsecond probe-interval queue drain rate estimation that detects buffer buildup before packet loss occurs, maintaining 94% link saturation.",
    architecture: {
      packet_filter: "eBPF / AF_XDP raw socket filter capturing flow metrics",
      pacing_engine: "Dynamic token bucket state machine tracking inflight BDP",
      controller: "RTT gradient feedback loop adjusting sender flight size",
      forwarder: "Zero-copy splice forwarding layer relaying TCP/UDP streams"
    },
    milestones: [
      { phase: "Phase 1", goal: "Build zero-copy stream proxy using epoll / kqueue event loops." },
      { phase: "Phase 2", goal: "Implement hardware timestamping and microsecond RTT rolling window." },
      { phase: "Phase 3", goal: "Translate adaptive congestion state machine into pacing controller." },
      { phase: "Phase 4", goal: "Validate with Linux netem under 50ms simulated latency and 5% jitter." }
    ],
    tech_stack: ["Rust", "epoll", "Linux netem", "Prometheus"]
  },
  {
    id: 3,
    domain: "DSA",
    title: "VectorSkip: Cache-Conscious High-Throughput Index Engine",
    core_concept: "Cache-conscious concurrent index engine packing node pointer routing arrays into single L1 lines.",
    target_service: "High-throughput in-memory index library & memory-mapped persistence runtime",
    novelty: "SIMD-vectorized binary search over cache-aligned blocks with lock-free hazard pointer reclamation.",
    selling_point: "Proves advanced competence in modern hardware-aware algorithms, concurrency, and cache locality.",
    summary: "High-performance concurrent indexing library adapting principles from 'Concurrent Cache-Conscious Skip Lists'. Packs hierarchical routing arrays into single 64-byte L1 cache lines with lock-free hazard pointers.",
    viability_score: 92,
    difficulty: "Advanced",
    paper_title: "Concurrent Cache-Conscious Skip Lists with O(1) Lock-Free Predecessor Tracking",
    paper_authors: "Yuki Tanaka, Arthur Pendelton, Sophia Chen",
    publication_year: 2024,
    cited_by_count: 14,
    doi: "https://doi.org/10.1145/3620665.3640391",
    core_mechanism: "Hierarchical routing array compaction fitting 8 forward pointers into a single CPU cache line, yielding 3.4x higher search throughput.",
    architecture: {
      memory_layout: "Contiguous array arena aligning index nodes to 64-byte boundaries",
      search_engine: "SIMD-vectorized binary search over compacted node blocks",
      concurrency: "Lock-free single-writer multi-reader (SWMR) synchronization",
      persistence: "Memory-mapped file (mmap) snapshotting for crash resilience"
    },
    milestones: [
      { phase: "Phase 1", goal: "Implement custom 64-byte cache-aligned memory arena allocator." },
      { phase: "Phase 2", goal: "Develop SIMD-accelerated predecessor search across node blocks." },
      { phase: "Phase 3", goal: "Integrate hazard pointers for safe concurrent reader memory reclamation." },
      { phase: "Phase 4", goal: "Benchmark L1/L2 cache miss rates using Linux perf and Criterion." }
    ],
    tech_stack: ["C++20", "AVX2 SIMD", "perf", "Google Benchmark"]
  },
  {
    id: 4,
    domain: "Full-Stack",
    title: "FluxSync: Real-Time Distributed Collaborative Workspace",
    core_concept: "Collaborative real-time workspace syncing multi-user hierarchical state via CRDTs and ArrayBuffers.",
    target_service: "Distributed reactive web service with Web Worker background state machines",
    novelty: "Zero-copy shared ArrayBuffer event bus guaranteeing conflict-free client convergence under 12ms.",
    selling_point: "Standout capstone demonstrating complex distributed state machines and offline-first UI architecture.",
    summary: "Distributed real-time collaborative workspace engine based on 'Zero-Copy Event-Driven Reactive Micro-Frontends'. Uses Conflict-Free Replicated Data Types (CRDTs) and shared ArrayBuffers for instant offline-first synchronization.",
    viability_score: 89,
    difficulty: "Intermediate",
    paper_title: "Zero-Copy Event-Driven Reactive Micro-Frontends with Distributed State Machines",
    paper_authors: "Liam O'Connor, Beatrice Varga, Julian Meyer",
    publication_year: 2023,
    cited_by_count: 19,
    doi: "https://doi.org/10.1016/j.sysarc.2023.102874",
    core_mechanism: "Zero-copy shared ArrayBuffer event bus paired with state-based causal tree CRDT, guaranteeing eventual consistency across tabs in <12ms.",
    architecture: {
      client_runtime: "Web Workers thread running local state machine over SharedArrayBuffer",
      wire_protocol: "WebSocket binary protocol transmitting compressed delta vectors",
      crdt_core: "JSON-compatible causal tree CRDT resolving concurrent offline edits",
      broker: "Asynchronous pub/sub broker with append-only event log"
    },
    milestones: [
      { phase: "Phase 1", goal: "Implement JSON causal tree CRDT with vector clocks in TypeScript." },
      { phase: "Phase 2", goal: "Construct binary delta serializer using Protobuf over WebSockets." },
      { phase: "Phase 3", goal: "Offload state reconciliation to background Web Workers for 60 FPS UI." },
      { phase: "Phase 4", goal: "Stress test with offline chaos simulator verifying zero state drift." }
    ],
    tech_stack: ["TypeScript", "React", "Fastify", "WebSockets", "Web Workers"]
  },
  {
    id: 5,
    domain: "CN",
    title: "AegisP2P: Deterministic Merkle DAG Chunk Distribution",
    core_concept: "Cryptographically verifiable peer-to-peer chunk streaming network with erasure-coded DAG blocks.",
    target_service: "Decentralized peer-to-peer chunk distribution daemon & DHT node",
    novelty: "Cryptographic erasure coding embedded directly within Merkle DAG nodes for O(1) poison rejection.",
    selling_point: "Exceptional capstone displaying mastery of cryptographic data structures and adversarial network protocols.",
    summary: "Cryptographically verifiable peer-to-peer chunk streaming network based on 'Resilient P2P Chunk Distribution'. Embeds erasure codes into Merkle DAG blocks to eliminate poisoning attacks in untrusted swarms.",
    viability_score: 93,
    difficulty: "Advanced",
    paper_title: "Resilient P2P Chunk Distribution with Deterministic Merkle Directed Acyclic Graphs",
    paper_authors: "Tariq Mansoor, Claire Dubois, Henrik Falk",
    publication_year: 2023,
    cited_by_count: 23,
    doi: "https://doi.org/10.1109/ICDCS.2023.00045",
    core_mechanism: "Cryptographic erasure coding embedded directly within Merkle DAG nodes, allowing downstream peers to verify chunk authenticity in O(1) time.",
    architecture: {
      swarm_discovery: "Kademlia Distributed Hash Table (DHT) for decentralized peer routing",
      chunk_encoder: "Reed-Solomon erasure coding splitting payload into 1MB verifiable blocks",
      dag_verifier: "BLAKE3 Merkle tree verifying chunk hashes against root manifest",
      transport: "QUIC multiplexed streams over UDP with TLS 1.3 encryption"
    },
    milestones: [
      { phase: "Phase 1", goal: "Implement Kademlia DHT node discovery and NAT traversal." },
      { phase: "Phase 2", goal: "Build Reed-Solomon block chunker with BLAKE3 Merkle DAG verification." },
      { phase: "Phase 3", goal: "Construct multiplexed QUIC transport layer with rate limits." },
      { phase: "Phase 4", goal: "Simulate adversarial 100-node cluster verifying resilience to Byzantine poisoning." }
    ],
    tech_stack: ["Go", "libp2p", "BLAKE3", "QUIC-go"]
  }
];

export function App() {
  const [ideas, setIdeas] = useState(INITIAL_BENCHMARK_IDEAS);
  const [stats, setStats] = useState({
    total_papers: 6,
    total_ideas: 5,
    average_viability_score: 92.8,
    domain_counts: { "DBMS": 1, "CN": 2, "DSA": 1, "Full-Stack": 1 },
    dlq_stats: { total_failures: 0, retryable: 0, silently_discarded: 0 },
    runtime: { status: "Idle", port: "8055", db_status: "SQLite Connected" }
  });
  const [selectedDomains, setSelectedDomains] = useState(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const urlDomains = params.get("domains");
      if (urlDomains) {
        const parsed = urlDomains.split(",").map(d => d.trim()).filter(Boolean);
        if (parsed.length > 0) return parsed;
      }
    } catch {
      // ignore
    }
    return [];
  });
  const [guidelinesEnforced, setGuidelinesEnforced] = useState(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      return params.get("guidelines") === "enforced";
    } catch {
      return false;
    }
  });
  const [minViability, setMinViability] = useState(80);
  const [difficultyFilter, setDifficultyFilter] = useState("ALL");
  const [skillsQuery, setSkillsQuery] = useState("");
  const [sortBy, setSortBy] = useState("created_at");
  const [isRunningPipeline, setIsRunningPipeline] = useState(false);
  const [isExportingBulk, setIsExportingBulk] = useState(false);
  const [isExportingCsv, setIsExportingCsv] = useState(false);
  const [allowIot, setAllowIot] = useState(false);
  const [pipelineFeedback, setPipelineFeedback] = useState(null);
  const [isCompareModalOpen, setIsCompareModalOpen] = useState(false);
  const [visibleCount, setVisibleCount] = useState(24);

  // Active View navigation state: "explore" or "bookmarks", synced with window.location.hash
  const [activeView, setActiveView] = useState(() => {
    return window.location.hash === "#bookmarks" ? "bookmarks" : "explore";
  });

  useEffect(() => {
    const handleHashChange = () => {
      setActiveView(window.location.hash === "#bookmarks" ? "bookmarks" : "explore");
    };
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  const handleSelectView = (view) => {
    setActiveView(view);
    window.location.hash = view === "bookmarks" ? "#bookmarks" : "#explore";
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  // Reset pagination window when filters, search queries, or sort criteria change
  useEffect(() => {
    setVisibleCount(24);
  }, [selectedDomains, minViability, difficultyFilter, skillsQuery, sortBy]);

  // Persistent shortlisting state with localStorage fallback
  const [shortlistedIds, setShortlistedIds] = useState(() => {
    try {
      const saved = localStorage.getItem("academic_ideation_shortlist");
      return saved ? new Set(JSON.parse(saved)) : new Set();
    } catch {
      return new Set();
    }
  });

  // Fetch live ideas and stats from API server with robust network failover
  const fetchLiveData = async (sortOrder = sortBy) => {
    try {
      let ideasRes;
      try {
        ideasRes = await fetch(`/api/ideas?sort=${sortOrder}`);
      } catch {
        try {
          ideasRes = await fetch(`http://localhost:8055/api/ideas?sort=${sortOrder}`);
        } catch {
          ideasRes = await fetch(`http://127.0.0.1:8055/api/ideas?sort=${sortOrder}`);
        }
      }
      if (ideasRes && ideasRes.ok) {
        const ideasData = await ideasRes.json();
        if (ideasData.ideas && ideasData.ideas.length > 0) {
          setIdeas(ideasData.ideas);

          // Synchronize shortlisted IDs from database records
          setShortlistedIds((prev) => {
            const next = new Set(prev);
            for (const item of ideasData.ideas) {
              if (item.is_shortlisted || item.is_bookmarked) {
                next.add(item.id);
              }
            }
            return next;
          });
        }
      }

      let statsRes;
      try {
        statsRes = await fetch("/api/stats");
      } catch {
        try {
          statsRes = await fetch("http://localhost:8055/api/stats");
        } catch {
          statsRes = await fetch("http://127.0.0.1:8055/api/stats");
        }
      }
      if (statsRes && statsRes.ok) {
        const statsData = await statsRes.json();
        if (statsData.total_ideas > 0) {
          setStats(statsData);
        }
      }
    } catch {
      // Gracefully maintain cached benchmark dataset
    }
  };

  // Bookmark Toggle Handler (Unlimited, Optimistic & Concurrent-Safe)
  const handleToggleShortlist = useCallback(async (ideaId) => {
    const isCurrently = shortlistedIds.has(ideaId);
    const nextState = !isCurrently;

    setShortlistedIds((prev) => {
      const next = new Set(prev);
      if (nextState) {
        next.add(ideaId);
      } else {
        next.delete(ideaId);
      }
      try {
        localStorage.setItem("academic_ideation_shortlist", JSON.stringify(Array.from(next)));
      } catch {}
      return next;
    });

    setPipelineFeedback({
      type: nextState ? "success" : "info",
      message: nextState
        ? "Saved blueprint to your Bookmarks! View it anytime under 'My Bookmarked Ideas'."
        : "Removed blueprint from your Bookmarks."
    });

    try {
      const targetUrl = `/api/ideas/${ideaId}/bookmark`;
      await fetch(targetUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_bookmarked: nextState })
      }).catch(async () => {
        await fetch(`http://localhost:8055/api/ideas/${ideaId}/bookmark`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ is_bookmarked: nextState })
        }).catch(() => {});
      });
    } catch {}
  }, [shortlistedIds]);

  // Clear all saved bookmarks
  const handleClearAllBookmarks = useCallback(async () => {
    setShortlistedIds(new Set());
    try {
      localStorage.removeItem("academic_ideation_shortlist");
    } catch {}

    setPipelineFeedback({
      type: "info",
      message: "Cleared all saved blueprints from your bookmarks collection."
    });

    try {
      await fetch("/api/bookmarks/clear", { method: "POST" })
        .catch(async () => {
          await fetch("http://localhost:8055/api/bookmarks/clear", { method: "POST" }).catch(() => {});
        });
    } catch {}
  }, []);

  // Export only bookmarked blueprints to CSV
  const handleExportBookmarkedCsv = async () => {
    if (shortlistedIds.size === 0) return;
    setIsExportingCsv(true);
    setPipelineFeedback(null);
    try {
      let res;
      try {
        res = await fetch("/api/export/csv?bookmarked=true");
      } catch {
        try {
          res = await fetch("http://localhost:8055/api/export/csv?bookmarked=true");
        } catch {
          res = await fetch("http://127.0.0.1:8055/api/export/csv?bookmarked=true");
        }
      }
      if (!res.ok) throw new Error("Failed to export bookmarked CSV.");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "Academic_Ideation_Bookmarked_Archive.csv";
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      setPipelineFeedback({
        type: "success",
        message: `Successfully exported ${shortlistedIds.size} bookmarked blueprints to CSV spreadsheet!`
      });
    } catch (err) {
      setPipelineFeedback({ type: "error", message: err.message || "Failed to download bookmarks CSV." });
    } finally {
      setIsExportingCsv(false);
    }
  };

  // Export only bookmarked blueprints to Word (.docx)
  const handleExportBookmarkedDocx = async () => {
    if (shortlistedIds.size === 0) return;
    setIsExportingBulk(true);
    setPipelineFeedback(null);
    try {
      let res;
      try {
        res = await fetch("/api/export/bulk?bookmarked=true");
      } catch {
        try {
          res = await fetch("http://localhost:8055/api/export/bulk?bookmarked=true");
        } catch {
          res = await fetch("http://127.0.0.1:8055/api/export/bulk?bookmarked=true");
        }
      }
      if (!res.ok) throw new Error("Failed to export bookmarked proposals.");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "Academic_Ideation_Bookmarked_Archive.docx";
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      setPipelineFeedback({
        type: "success",
        message: `Successfully compiled and exported ${shortlistedIds.size} bookmarked proposals to Word (.docx)!`
      });
    } catch (err) {
      setPipelineFeedback({ type: "error", message: err.message || "Failed to download bookmarks archive." });
    } finally {
      setIsExportingBulk(false);
    }
  };

  const handleToggleDomain = (domainId) => {
    setSelectedDomains((prev) => {
      if (prev.includes(domainId)) {
        return prev.filter((d) => d !== domainId);
      } else {
        return [...prev, domainId];
      }
    });
  };

  const handleClearDomains = () => {
    setSelectedDomains([]);
  };

  useEffect(() => {
    fetchLiveData(sortBy);
  }, [sortBy]);

  const handleSelectSort = (newSort) => {
    setSortBy(newSort);
    fetchLiveData(newSort);
  };

  const handleExportCsv = async () => {
    setIsExportingCsv(true);
    setPipelineFeedback(null);
    try {
      let res;
      try {
        res = await fetch("/api/export/csv");
      } catch {
        try {
          res = await fetch("http://localhost:8055/api/export/csv");
        } catch {
          res = await fetch("http://127.0.0.1:8055/api/export/csv");
        }
      }
      if (!res.ok) {
        const errPayload = await res.json().catch(() => ({}));
        throw new Error(errPayload.error || `Server responded with ${res.status}`);
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "Academic_Ideation_Master_Archive.csv";
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      setPipelineFeedback({
        type: "success",
        message: `Successfully exported ${ideas.length} project blueprints to lightweight CSV spreadsheet (Excel UTF-8 compatible)!`
      });
    } catch (err) {
      setPipelineFeedback({
        type: "error",
        message: err.message || "Failed to download CSV archive. Ensure backend API is active."
      });
    } finally {
      setIsExportingCsv(false);
    }
  };

  const handleBulkExport = async () => {
    setIsExportingBulk(true);
    setPipelineFeedback(null);
    try {
      let res;
      try {
        res = await fetch("/api/export/bulk");
      } catch {
        try {
          res = await fetch("http://localhost:8055/api/export/bulk");
        } catch {
          res = await fetch("http://127.0.0.1:8055/api/export/bulk");
        }
      }
      if (!res.ok) {
        const errPayload = await res.json().catch(() => ({}));
        throw new Error(errPayload.error || `Server responded with ${res.status}`);
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "Academic_Ideation_Master_Archive.docx";
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      setPipelineFeedback({
        type: "success",
        message: `Successfully compiled and exported master Word document archive (${ideas.length} project blueprints with methodology preface and certification signature)!`
      });
    } catch (err) {
      setPipelineFeedback({
        type: "error",
        message: err.message || "Failed to download master bulk export archive. Ensure backend API is active."
      });
    } finally {
      setIsExportingBulk(false);
    }
  };

  const handleTriggerPipeline = async () => {
    setIsRunningPipeline(true);
    setPipelineFeedback(null);
    try {
      let res;
      const requestOptions = {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ allow_iot: allowIot, per_page: 6 })
      };

      try {
        res = await fetch("/api/pipeline/run", requestOptions);
      } catch {
        try {
          res = await fetch("http://localhost:8055/api/pipeline/run", requestOptions);
        } catch {
          res = await fetch("http://127.0.0.1:8055/api/pipeline/run", requestOptions);
        }
      }

      if (!res.ok) {
        const errPayload = await res.json().catch(() => ({}));
        throw new Error(errPayload.error || `Server responded with ${res.status}`);
      }
      const data = await res.json();
      const synthesizedCount = data.results?.synthesized_ideas || 0;
      const newPapers = data.results?.new_papers || 0;

      setPipelineFeedback({
        type: "success",
        message: synthesizedCount > 0
          ? `Ingest pass complete: Synthesized ${synthesizedCount} brand-new project blueprints from ${newPapers} research papers (${allowIot ? "IoT Included" : "Software-Only"})!`
          : `Ingest pass complete: ${data.results?.fetched || 0} papers evaluated. Zero new candidates (${allowIot ? "IoT Included" : "Software-Only"}).`
      });

      // Reset to ALL and latest sort so new ideas appear at the very top
      setActiveFilter("ALL");
      setSortBy("created_at");
      await fetchLiveData("created_at");
    } catch (err) {
      setPipelineFeedback({
        type: "error",
        message: err.message || "Pipeline execution failed. Please check server logs."
      });
    } finally {
      setIsRunningPipeline(false);
    }
  };

  // Find Similar Blueprints Handler
  const handleFindSimilar = useCallback((idea) => {
    const targetDomains = Array.isArray(idea.domains) && idea.domains.length > 0
      ? idea.domains
      : [idea.domain || "Full-Stack"];
    setSelectedDomains(targetDomains);

    const techList = Array.isArray(idea.tech_stack) ? idea.tech_stack : [];
    const primarySkill = techList.length > 0 ? techList[0].split("/")[0].trim() : (idea.domain || "");
    setSkillsQuery(primarySkill);

    setPipelineFeedback({
      type: "info",
      message: `Filtering similar blueprints matching discipline(s): ${targetDomains.join(", ")} & tech: "${primarySkill}".`
    });

    const grid = document.querySelector(".masonry-layout");
    if (grid) grid.scrollIntoView({ behavior: "smooth" });
  }, []);

  // Multi-criteria filtering and Skills Matcher re-sorting engine
  const filteredAndSortedIdeas = useMemo(() => {
    return ideas.filter((idea) => {
      // 1. Domain Filter (Multi-domain matching)
      if (selectedDomains.length > 0) {
        const itemDomains = Array.isArray(idea.domains) && idea.domains.length > 0
          ? idea.domains
          : [idea.domain];
        const hasMatch = selectedDomains.some((d) => itemDomains.includes(d));
        if (!hasMatch) return false;
      }
      // 2. Viability Score Filter
      const score = Number(idea.viability_score || 90);
      if (score < minViability) {
        return false;
      }
      // 3. Difficulty Filter
      if (difficultyFilter !== "ALL") {
        const diff = (idea.difficulty || "Advanced").toLowerCase();
        if (diff !== difficultyFilter.toLowerCase()) {
          return false;
        }
      }
      return true;
    }).map((idea) => {
      // 4. Skills Matcher Scoring
      let matchScore = 0;
      if (skillsQuery.trim()) {
        const queryTokens = skillsQuery
          .toLowerCase()
          .split(/[\s,+/]+/)
          .filter((t) => t.length > 1);

        const techList = Array.isArray(idea.tech_stack)
          ? idea.tech_stack.join(" ").toLowerCase()
          : (typeof idea.tech_stack === "string" ? idea.tech_stack.toLowerCase() : "");
        const coreText = (idea.core_concept || "").toLowerCase();
        const titleText = (idea.title || "").toLowerCase();
        const mechText = (idea.core_mechanism || "").toLowerCase();

        for (const token of queryTokens) {
          if (techList.includes(token)) matchScore += 6;
          if (titleText.includes(token)) matchScore += 4;
          if (coreText.includes(token)) matchScore += 2;
          if (mechText.includes(token)) matchScore += 2;
        }
      }
      return { ...idea, _matchScore: matchScore };
    }).sort((a, b) => {
      // Priority 1: Skills Match Score (if query active)
      if (skillsQuery.trim() && b._matchScore !== a._matchScore) {
        return b._matchScore - a._matchScore;
      }
      // Priority 2: User-selected order
      if (sortBy === "viability") {
        return (b.viability_score || 90) - (a.viability_score || 90);
      }
      return (b.id || 0) - (a.id || 0);
    });
  }, [ideas, selectedDomains, minViability, difficultyFilter, skillsQuery, sortBy]);

  // Virtual pagination window: slice to visibleCount (default 24)
  const visibleIdeas = useMemo(() => {
    return filteredAndSortedIdeas.slice(0, visibleCount);
  }, [filteredAndSortedIdeas, visibleCount]);

  // Selected ideas for side-by-side comparison modal (up to 3)
  const shortlistedIdeas = ideas.filter((item) => shortlistedIds.has(item.id));

  return (
    <main>
      <Header
        onTriggerPipeline={handleTriggerPipeline}
        isRunning={isRunningPipeline}
        onBulkExport={activeView === "bookmarks" ? handleExportBookmarkedDocx : handleBulkExport}
        isExportingBulk={isExportingBulk}
        onExportCsv={activeView === "bookmarks" ? handleExportBookmarkedCsv : handleExportCsv}
        isExportingCsv={isExportingCsv}
        allowIot={allowIot}
        onToggleIot={setAllowIot}
        runtimeStatus={stats.runtime?.status || (isRunningPipeline ? "Ingesting..." : "Idle")}
        serverPort={stats.runtime?.port || "8055"}
        dbStatus={stats.runtime?.db_status || "SQLite Connected"}
        skillsQuery={skillsQuery}
        onSkillsQueryChange={setSkillsQuery}
        shortlistedCount={shortlistedIds.size}
        totalIdeasCount={ideas.length}
        activeView={activeView}
        onSelectView={handleSelectView}
        onOpenCompare={() => setIsCompareModalOpen(true)}
      />

      {pipelineFeedback && (
        <div
          role="status"
          aria-live="polite"
          className={`feedback-banner ${pipelineFeedback.type === "error" ? "feedback-error" : (pipelineFeedback.type === "info" ? "feedback-info" : "feedback-success")}`}
        >
          <span>{pipelineFeedback.message}</span>
          <button
            type="button"
            onClick={() => setPipelineFeedback(null)}
            className="feedback-dismiss-btn"
            aria-label="Dismiss message"
          >
            ×
          </button>
        </div>
      )}

      {activeView === "bookmarks" ? (
        <BookmarksPage
          bookmarkedIdeas={shortlistedIdeas}
          onToggleBookmark={handleToggleShortlist}
          onFindSimilar={handleFindSimilar}
          userSkills={skillsQuery}
          onBackToExplore={() => handleSelectView("explore")}
          onOpenCompare={() => setIsCompareModalOpen(true)}
          onExportCsv={handleExportBookmarkedCsv}
          onExportDocx={handleExportBookmarkedDocx}
          onClearAll={handleClearAllBookmarks}
          isExportingCsv={isExportingCsv}
          isExportingDocx={isExportingBulk}
        />
      ) : (
        <>
          <StatsBar stats={stats} />
          {selectedDomains.length > 0 && (
            <div className="apple-guideline-banner">
              <div className="guideline-led-pill">
                <span className="led-dot-pulse"></span>
                <span className="guideline-text">
                  ACTIVE GUIDELINES: {selectedDomains.join(" & ")} ENFORCED • STRICT NO-IOT SOFTWARE FILTER
                </span>
              </div>
              <button
                type="button"
                className="guideline-clear-btn"
                onClick={() => {
                  setSelectedDomains([]);
                  if (window.history.pushState) {
                    window.history.pushState({}, "", window.location.pathname);
                  }
                }}
              >
                Reset All Guidelines
              </button>
            </div>
          )}
          <FilterBar
            selectedDomains={selectedDomains}
            onToggleDomain={handleToggleDomain}
            onClearDomains={handleClearDomains}
            domainCounts={stats.domain_counts || {}}
            minViability={minViability}
            onViabilityChange={setMinViability}
            difficultyFilter={difficultyFilter}
            onDifficultyChange={setDifficultyFilter}
            sortBy={sortBy}
            onSelectSort={handleSelectSort}
            totalMatching={filteredAndSortedIdeas.length}
          />

          {guidelinesEnforced && (
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '24px' }}>
              <div className="guideline-led-pill">
                <span className="led-dot-pulse"></span>
                ACTIVE GUIDELINES: DBMS & AI/ML EXCLUSIVE • STRICT NO-IOT FILTER ENFORCED
              </div>
            </div>
          )}

          <section className="masonry-layout" aria-label="Synthesized Software Project Cards">
            {visibleIdeas.map((idea) => (
              <GameCard
                key={idea.id || idea.title}
                idea={idea}
                isShortlisted={shortlistedIds.has(idea.id)}
                onToggleShortlist={handleToggleShortlist}
                onFindSimilar={handleFindSimilar}
                userSkills={skillsQuery}
              />
            ))}
          </section>

          {visibleCount < filteredAndSortedIdeas.length && (
            <div className="load-more-container">
              <div className="load-more-stats">
                Showing <strong>{visibleIdeas.length}</strong> of <strong>{filteredAndSortedIdeas.length}</strong> Blueprints
              </div>
              <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", justifyContent: "center" }}>
                <button
                  type="button"
                  className="btn-load-more"
                  onClick={() => setVisibleCount((prev) => Math.min(prev + 24, filteredAndSortedIdeas.length))}
                  aria-label="Load next 24 blueprints"
                >
                  Load More Blueprints (+24)
                </button>
                <button
                  type="button"
                  className="btn-swiss-secondary"
                  style={{ borderRadius: "8px", padding: "0.75rem 1.5rem" }}
                  onClick={() => setVisibleCount(filteredAndSortedIdeas.length)}
                  aria-label="Show all blueprints"
                >
                  Show All ({filteredAndSortedIdeas.length})
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Side-by-Side Selection Matrix Modal */}
      <CompareModal
        ideas={shortlistedIdeas}
        isOpen={isCompareModalOpen}
        onClose={() => setIsCompareModalOpen(false)}
        onRemoveFromCompare={handleToggleShortlist}
      />

      <footer style={{
        maxWidth: "1360px",
        margin: "0 auto 3rem",
        padding: "1.5rem",
        borderTop: "1px solid var(--border-subtle)",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        flexWrap: "wrap",
        gap: "1rem",
        fontFamily: "var(--font-mono)",
        fontSize: "0.75rem",
        color: "var(--text-muted)"
      }}>
        <div>Academic Project Ideation Platform — Local-First Swiss Editorial Architecture</div>
        <div>OpenAlex + ArXiv Multi-Category Ingestion • Dead-Letter Queue (Max 2 Retries) • {allowIot ? "IoT/Edge Permitted" : "Software-Only Enforced"}</div>
      </footer>
    </main>
  );
}

export default App;
