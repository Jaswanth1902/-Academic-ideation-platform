"""
LLM Synthesis Engine for Academic Project Viability.
Evaluates papers for Full-Stack, DSA, CN, and DBMS project viability with zero IoT/Hardware tolerance.
Generates actionable engineering blueprints, component diagrams, and 4-phase implementation roadmaps.
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, Tuple
from config import VALID_DOMAINS, VLLM_API_URL, VLLM_MODEL, OLLAMA_API_URL, OLLAMA_MODEL
from openalex_client import is_hardware_or_iot


def _safe_stderr_write(msg: str) -> None:
    """Safely writes diagnostic messages to stderr without crashing on closed streams."""
    try:
        if sys.stderr and not getattr(sys.stderr, "closed", False):
            sys.stderr.write(msg)
            sys.stderr.flush()
    except Exception:
        try:
            if hasattr(sys, "__stderr__") and sys.__stderr__ and not getattr(sys.__stderr__, "closed", False):
                sys.__stderr__.write(msg)
                sys.__stderr__.flush()
        except Exception:
            pass


def _repair_and_parse_json(raw_text: str) -> Dict[str, Any]:
    """
    Parses JSON from LLM output with pure-Python self-healing repairs for truncation.
    Adheres strictly to the Karpathy Invariant (zero external dependencies).
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("Empty response text")

    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    # Fast path: direct valid JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find the start of the JSON object
    start_idx = text.find("{")
    if start_idx == -1:
        raise ValueError("No JSON object '{' found in response")
    text = text[start_idx:]

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Aggressive rollback to last clean key-value / bracket boundary
    for cut_pos in range(len(text) - 1, 0, -1):
        if text[cut_pos] in (',', '}', ']', '\n'):
            candidate = text[:cut_pos].rstrip().rstrip(',')
            stk = []
            is_s = False
            es = False
            for c in candidate:
                if is_s:
                    if es:
                        es = False
                    elif c == '\\':
                        es = True
                    elif c == '"':
                        is_s = False
                else:
                    if c == '"':
                        is_s = True
                    elif c in ('{', '['):
                        stk.append(c)
                    elif c == '}' and stk and stk[-1] == '{':
                        stk.pop()
                    elif c == ']' and stk and stk[-1] == '[':
                        stk.pop()
            if not is_s:
                for op in reversed(stk):
                    candidate += '}' if op == '{' else ']'
                try:
                    res = json.loads(candidate)
                    if isinstance(res, dict) and len(res) >= 2:
                        return res
                except Exception:
                    pass

    # Direct string close and bracket balance
    repaired = text
    in_str = False
    esc = False
    stk = []
    for c in repaired:
        if in_str:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c in ('{', '['):
                stk.append(c)
            elif c == '}' and stk and stk[-1] == '{':
                stk.pop()
            elif c == ']' and stk and stk[-1] == '[':
                stk.pop()

    if in_str:
        repaired += '"'
    repaired = re.sub(r',\s*$', '', repaired)
    for op in reversed(stk):
        repaired += '}' if op == '{' else ']'

    return json.loads(repaired)


class OllamaLocalWorker:
    """
    Local Ollama Inference Worker calling http://localhost:11434/api/generate.
    Zero external dependencies (pure Python urllib.request & json).
    Supports models: llama3, phi3, hermes3:8b, llama3.2:3b, etc.
    """

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (base_url or os.getenv("OLLAMA_API_URL", OLLAMA_API_URL or "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", OLLAMA_MODEL or "triage_model")

    # Coordinator semantic aliases — must be sent verbatim to port 11434.
    # Calling _resolve_model() on these would fail the /api/tags match and fall
    # back to qwen2.5-coder:7b. The coordinator intercepts and resolves them.
    COORDINATOR_ALIASES = {
        "agentic_worker_model", "agentic_worker",
        "code_worker_model",    "code_worker",
        "triage_model",         "triage",
        "hermes",
        "qwen2.5:7b",           "qwen2.5-coder:7b",
    }

    def _resolve_model(self, candidate: Optional[str] = None) -> str:
        """Checks available models on local Ollama instance and resolves compatible model.
        Skipped when candidate is a coordinator alias — those are passed verbatim."""
        target = candidate or self.model
        # Pass coordinator aliases through without resolution
        if target in self.COORDINATOR_ALIASES:
            return target
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    available = [m.get("name", "") for m in data.get("models", [])]
                    for name in available:
                        if name == target or name.startswith(f"{target}:"):
                            return name
                    for name in available:
                        if target in name:
                            return name
                    for pref in [target, "triage_model", "llama3.2:3b", "qwen2.5-coder:7b", "hermes3:8b", "llama3", "phi3"]:
                        for name in available:
                            if pref in name:
                                return name
                    if available:
                        return available[0]
        except Exception:
            pass
        return target

    def generate(self, prompt: str, system: Optional[str] = None, timeout: float = 360.0, model_override: Optional[str] = None, num_predict: int = 1024) -> Dict[str, Any]:
        """
        Calls Ollama /api/generate with JSON formatting option.
        Returns parsed JSON dict with self-healing truncation repairs.
        """
        resolved_model = self._resolve_model(model_override)
        payload = {
            "model": resolved_model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.2,
                "num_thread": 8,
                "num_predict": num_predict,
                "num_ctx": 4096
            }
        }
        if system:
            payload["system"] = system

        url = f"{self.base_url}/api/generate"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                raw_body = resp.read().decode("utf-8")
                res_obj = json.loads(raw_body)
                content = res_obj.get("response", "")
                return _repair_and_parse_json(content)
            raise RuntimeError(f"Ollama returned HTTP status {resp.status}")


class SynthesisEngine:
    """Evaluates academic papers and synthesizes senior-level software engineering project blueprints with Hybrid LLM routing."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        vllm_url: Optional[str] = None,
        vllm_model: Optional[str] = None,
        ollama_url: Optional[str] = None,
        ollama_model: Optional[str] = None
    ):
        self.gemini_api_key = api_key or os.getenv("GEMINI_API_KEY")
        if self.gemini_api_key in ("your_key_here", ""):
            self.gemini_api_key = None
        self.ollama_worker = OllamaLocalWorker(base_url=ollama_url, model=ollama_model)
        self.vllm_url = (vllm_url or os.getenv("VLLM_API_URL", VLLM_API_URL or "http://localhost:8000/v1")).rstrip("/")
        self.vllm_model = vllm_model or os.getenv("VLLM_MODEL", VLLM_MODEL or "meta-llama/Llama-3-8B-Instruct")
        self._gemini_disabled_this_session = False
        self._ollama_disabled_this_session = False
        self._vllm_disabled_this_session = False

    def evaluate_paper(self, paper: Dict[str, Any], allow_iot: bool = False, fast_mode: bool = False) -> Optional[Dict[str, Any]]:
        """
        Evaluates a paper for software project viability.
        Returns None if paper contains hardware/IoT elements and allow_iot is False.
        Routes generative synthesis through Gemini -> local vLLM_Engine (failover) -> deterministic compiler.
        """
        composite_text = f"{paper.get('title', '')} {paper.get('abstract', '')} {paper.get('concepts', '')}"
        is_hw, matched_kw = is_hardware_or_iot(composite_text)
        if is_hw and not allow_iot:
            # Strictly reject hardware/IoT papers when allow_iot is False
            return None

        # Determine 1 to 3 matching domains among the 14 software domains
        domains = self._classify_multi_domain(composite_text, max_domains=3)
        primary_domain = domains[0]

        # Route through Antigravity ModelRouter (Gemini -> vLLM failover -> deterministic)
        return self._route_synthesis(paper, primary_domain, domains=domains, allow_iot=allow_iot, fast_mode=fast_mode)

    def _route_synthesis(self, paper: Dict[str, Any], domain: str, domains: Optional[list] = None, allow_iot: bool = False, fast_mode: bool = False) -> Optional[Dict[str, Any]]:
        """
        Hybrid ModelRouter:
        1. Attempts cloud Gemini.
        2. If Gemini throws a quota error (HTTP 429 / quota limit exceeded / resource exhausted),
           immediately routes the paper to the local Ollama worker (http://localhost:11434/api/generate).
        3. If Gemini key is absent or disabled, routes directly to local Ollama worker.
        4. If local Ollama fails or is unavailable, fails over to local vLLM if configured.
        5. Returns None upon total LLM failure (strictly zero deterministic fallback).
        """
        if domains is None:
            domains = [domain]
        blueprint = None

        def _call_gemini():
            try:
                return self._synthesize_with_gemini(paper, domain, domains=domains, allow_iot=allow_iot, fast_mode=fast_mode)
            except TypeError:
                return self._synthesize_with_gemini(paper, domain, allow_iot=allow_iot)

        def _call_ollama():
            try:
                return self._synthesize_with_ollama(paper, domain, domains=domains, allow_iot=allow_iot, fast_mode=fast_mode)
            except TypeError:
                return self._synthesize_with_ollama(paper, domain, allow_iot=allow_iot)

        def _call_vllm():
            try:
                return self._synthesize_with_vllm(paper, domain, domains=domains, allow_iot=allow_iot, fast_mode=fast_mode)
            except TypeError:
                return self._synthesize_with_vllm(paper, domain, allow_iot=allow_iot)

        if self.gemini_api_key and not self._gemini_disabled_this_session:
            try:
                blueprint = _call_gemini()
            except urllib.error.HTTPError as err:
                if err.code in (400, 401, 403, 404):
                    _safe_stderr_write(f"[ModelRouter] Gemini API authentication/model issue ({err.code}). Failing over to local Ollama worker...\n")
                    self._gemini_disabled_this_session = True
                elif err.code == 429 or "quota" in str(err).lower():
                    _safe_stderr_write(f"[ModelRouter] Gemini quota exhausted (HTTP 429). Immediately routing paper to local Ollama worker at {self.ollama_worker.base_url}...\n")
                    self._gemini_disabled_this_session = True
                else:
                    _safe_stderr_write(f"[ModelRouter] Gemini API error ({err.code}): {err}. Attempting local Ollama failover...\n")

                if not self._ollama_disabled_this_session:
                    blueprint = _call_ollama()
            except Exception as exc:
                err_str = str(exc).lower()
                if "429" in err_str or "quota" in err_str or "resourceexhausted" in err_str:
                    _safe_stderr_write(f"[ModelRouter] Gemini quota limit triggered ({exc}). Immediately routing paper to local Ollama worker...\n")
                    self._gemini_disabled_this_session = True
                else:
                    _safe_stderr_write(f"[ModelRouter] Gemini synthesis exception: {exc}. Attempting local Ollama failover...\n")

                if not self._ollama_disabled_this_session:
                    blueprint = _call_ollama()
        else:
            # Direct routing to local Ollama worker when Gemini key is not configured
            if not self._ollama_disabled_this_session:
                blueprint = _call_ollama()

        # If Ollama did not produce a blueprint, attempt vLLM if configured
        if not blueprint and self.vllm_url and not self._vllm_disabled_this_session:
            blueprint = _call_vllm()

        return blueprint

    def _classify_multi_domain(self, text: str, max_domains: int = 3) -> list:
        """Classifies text and concepts dynamically into 1 to 3 software domains."""
        text_lower = text.lower()

        scores = {
            "Database Management": 0,
            "AI/ML": 0,
            "Theory of Computation": 0,
            "Computer Vision": 0,
            "Operations Research": 0,
            "Web Frameworks": 0,
            "GenAI": 0,
            "Big Data Systems": 0,
            "Cryptography": 0,
            "Network Security": 0,
            "Full-Stack": 0,
            "DSA": 0,
            "CN": 0,
            "DBMS": 0
        }

        # Concept-level strong weights (Weight: +6)
        if re.search(r"\b(generative ai|large language model|llms?|rag|retrieval-augmented|prompt (?:tuning|engineering)|diffusion models?|transformer models?|hallucination|chatgpt|gpt-[0-9]|text generation)\b", text_lower):
            scores["GenAI"] += 6
        if re.search(r"\b(computer vision|object detection|image segmentation|semantic segmentation|optical flow|point cloud|visual recognition|yolo|convolutional neural|cnn|vision transformer|neural rendering)\b", text_lower):
            scores["Computer Vision"] += 6
        if re.search(r"\b(cryptography|zero-knowledge|zk-snarks?|homomorphic encryption|lattice-based|post-quantum|digital signature|ciphers?|decryption|elliptic curve|merkle tree|verifiable computation)\b", text_lower):
            scores["Cryptography"] += 6
        if re.search(r"\b(network security|intrusion detection|firewalls?|packet filtering|ddos|malware|botnet|vulnerability analysis|cyber ?attack|zero trust|penetration testing|adversarial attacks?)\b", text_lower):
            scores["Network Security"] += 6
        if re.search(r"\b(big data|distributed stream|apache (?:spark|kafka|flink)|mapreduce|lakehouse|data warehouse|stream processing|delta lake|columnar format|parquet)\b", text_lower):
            scores["Big Data Systems"] += 6
        if re.search(r"\b(operations research|combinatorial optimization|integer programming|linear programming|simplex|vehicle routing|queueing theory|job shop scheduling|facility location)\b", text_lower):
            scores["Operations Research"] += 6
        if re.search(r"\b(theory of computation|automata|formal verification|computational complexity|np-hard|np-complete|turing machine|decidability|formal methods|model checking)\b", text_lower):
            scores["Theory of Computation"] += 6
        if re.search(r"\b(web frameworks?|micro-?frontends?|server-side rendering|ssr|api gateway|reactive ui|react|vue|next\.js|webassembly|graphql)\b", text_lower):
            scores["Web Frameworks"] += 6
        if re.search(r"\b(machine learning|deep learning|neural networks?|reinforcement learning|model training|supervised learning|unsupervised learning|loss function|gradient descent|inference optimization)\b", text_lower):
            scores["AI/ML"] += 5
        if re.search(r"\b(relational database|sql|acid|transaction processing|storage engine|query optimizer|wal|write-ahead|lsm-tree|b-tree|mvcc)\b", text_lower):
            scores["Database Management"] += 5
            scores["DBMS"] += 4
        if re.search(r"\b(computer network|transport layer|congestion control|p2p|peer-to-peer|tcp|quic|packet routing|bbr|udp)\b", text_lower):
            scores["CN"] += 5
        if re.search(r"\b(data structures?|algorithms?|skip list|hnsw|nearest neighbor|lock-free|non-blocking|trie|graph algorithm)\b", text_lower):
            scores["DSA"] += 5
        if re.search(r"\b(full-stack|web application|microservices?|crdt|reactive programming|collaborative workspace)\b", text_lower):
            scores["Full-Stack"] += 5

        # Secondary domain keyword boosts (Weight: +2)
        patterns = {
            "GenAI": [r"\bprompt\b", r"\brag\b", r"\bembeddings?\b", r"\bllm\b", r"\bgenerative\b", r"\bhallucination\b"],
            "Computer Vision": [r"\bpixels?\b", r"\bimages?\b", r"\bsegmentation\b", r"\bvisual\b", r"\bopencv\b", r"\byolo\b"],
            "Cryptography": [r"\bcrypto\w*\b", r"\bencryption\b", r"\bdecryption\b", r"\bcipher\b", r"\bhash\b", r"\bzkp\b"],
            "Network Security": [r"\bsecurity\b", r"\bfirewall\b", r"\bids\b", r"\bmalware\b", r"\battack\b", r"\bauth\w*\b"],
            "Big Data Systems": [r"\bspark\b", r"\bkafka\b", r"\bflink\b", r"\bstreaming\b", r"\blakehouse\b"],
            "Operations Research": [r"\boptimization\b", r"\bscheduling\b", r"\bqueue\b", r"\bheuristic\b", r"\bsimplex\b"],
            "Theory of Computation": [r"\bautomata\b", r"\bcomplexity\b", r"\bformal\b", r"\bverification\b", r"\bturing\b"],
            "Web Frameworks": [r"\bfrontend\b", r"\bbackend\b", r"\brest\b", r"\bgraphql\b", r"\bwebsocket\b"],
            "AI/ML": [r"\bclassifier\b", r"\bprediction\b", r"\btraining\b", r"\baccuracy\b", r"\bepoch\b"],
            "Database Management": [r"\bdatabase\b", r"\bquery\b", r"\bindex\b", r"\btransactions?\b", r"\bsql\b"],
            "DBMS": [r"\blsm\b", r"\bsstable\b", r"\bwal\b", r"\bcompaction\b", r"\brocksdb\b"],
            "CN": [r"\bquic\b", r"\btcp\b", r"\bpacing\b", r"\bpacket\b", r"\bbufferbloat\b"],
            "DSA": [r"\bskiplist\b", r"\block-free\b", r"\bconcurrent\b", r"\bheap\b", r"\btree\b"],
            "Full-Stack": [r"\bcrdt\b", r"\bcollaborative\b", r"\bevent-driven\b", r"\bui\b"]
        }
        for domain_name, pat_list in patterns.items():
            for p in pat_list:
                if re.search(p, text_lower):
                    scores[domain_name] += 2

        # Sort by score descending
        sorted_pairs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_positive = [dom for dom, score in sorted_pairs if score > 0]
        if not top_positive:
            return ["Full-Stack"]
        return top_positive[:max(1, max_domains)]

    def _classify_domain(self, text: str) -> str:
        """Classifies text and concepts dynamically into the single primary domain."""
        return self._classify_multi_domain(text, max_domains=1)[0]

    def _extract_keywords(self, title: str, abstract: str, top_k: int = 5) -> list:
        """Extracts salient technical keywords from title and abstract, filtering out stopwords."""
        stopwords = {
            "a", "an", "the", "in", "on", "for", "with", "and", "or", "of", "to", "at", "by", "from",
            "as", "is", "are", "was", "were", "be", "been", "using", "based", "study", "approach",
            "method", "system", "systems", "via", "towards", "paper", "review", "comprehensive",
            "advancements", "perspective", "utilizing", "model", "models", "analysis", "detection",
            "classification", "research", "supported", "real-time", "high-performance", "efficient",
            "novel", "new", "an", "application", "applications", "comparative", "experimental",
            "investigation", "improving", "performance", "framework", "architecture", "evaluation",
            "deep", "learning", "machine", "artificial", "intelligence", "neural", "network", "networks",
            "impact", "modern", "society", "recent", "years", "wide", "state", "art", "open", "role",
            "overview", "survey", "quantitative", "advancing", "general", "future", "challenges",
            "has", "have", "had", "emerged", "emerging", "due", "also", "well", "may", "can", "could", "should", "would", "must"
        }
        # Clean text
        raw_words = re.findall(r"\b[A-Za-z]{3,}\b", f"{title} {abstract}")
        filtered = [w for w in raw_words if w.lower() not in stopwords]
        
        # Preserve word order with deduplication
        seen = set()
        unique_kws = []
        for w in filtered:
            wl = w.lower()
            if wl not in seen:
                seen.add(wl)
                unique_kws.append(w.capitalize())
        
        if not unique_kws:
            unique_kws = ["Core", "Stream", "Distributed", "Dynamic", "Adaptive"]
        return unique_kws[:top_k]

    def _build_fast_prompt(self, paper: Dict[str, Any], domain: str) -> str:
        """Constructs ultra-compact prompt (~120 tokens JSON output) for high-speed synthesis."""
        abstract_text = (paper.get('abstract') or '')[:350]
        return f"""You are a Principal Software Architect.
Synthesize a software engineering student project based on this paper:
Title: {paper.get('title')}
Domain: {domain}
Abstract: {abstract_text}

Return ONLY a valid JSON object matching this schema:
{{
  "title": "Distinctive Project Codename: Subtitle",
  "core_concept": "1-sentence plain-English hook explaining what this software does",
  "core_mechanism": "Specific algorithm, mathematical technique, or data structure",
  "tech_stack": ["Tech1", "Tech2", "Tech3"],
  "difficulty": "Intermediate",
  "viability_score": 92
}}"""

    def _build_prompt(self, paper: Dict[str, Any], domain: str, domains: Optional[list] = None, allow_iot: bool = False) -> str:
        """Constructs standardized systems engineering prompt for LLM synthesis."""
        iot_clause = "IoT and Edge Computing software architectures are permitted." if allow_iot else "STRICTLY NO HARDWARE, NO IOT, NO SENSORS, NO EMBEDDED CIRCUITS. Must be 100% software."
        domains_hint = json.dumps(domains or [domain])
        abstract_text = (paper.get('abstract') or '')[:500]
        return f"""
You are a Principal Software Architect evaluating academic CS research papers for computer science student projects.
Evaluate the following paper strictly for viability in the domain '{domain}'.
Paper Title: {paper.get('title')}
Authors: {paper.get('authors')}
Abstract: {abstract_text}

Requirements:
1. {iot_clause}
2. Generate a completely unique, innovative project codename and subtitle based strictly on the paper's specific methodology and findings. NEVER use boilerplate or generic names like 'FluxSync', 'VectorSkip', 'FlashKV', or 'HyperPacer'.
3. Assign 1 to 3 relevant domain tags from: Database Management, AI/ML, Theory of Computation, Computer Vision, Operations Research, Web Frameworks, GenAI, Big Data Systems, Cryptography, Network Security, Full-Stack, DSA, CN, DBMS.
4. Keep descriptions high-signal and concise (under 20 words each). Each milestone goal must be a single concise sentence.
5. Estimate student implementation feasibility timeline (e.g., '120 Hours / 4 Sprints', '80 Hours / 3 Sprints', '160 Hours / 5 Sprints').
6. Return ONLY a valid JSON object matching this exact schema:
{{
  "domain": "{domain}",
  "domains": {domains_hint},
  "feasibility_timeline": "120 Hours / 4 Sprints",
  "title": "Compelling Project Name & Subtitle",
  "core_concept": "1-sentence plain-English hook explaining what this software does",
  "target_service": "Concrete daemon, service, or library built and run",
  "novelty": "Specific architectural or algorithmic differentiator from the paper",
  "selling_point": "Resume impact and high-value capstone talking point",
  "summary": "2-3 sentences explaining the project and why it is a standout resume piece",
  "architecture": {{
    "client_or_ingestion": "...",
    "processing_core": "...",
    "storage_or_state": "...",
    "monitoring": "..."
  }},
  "core_mechanism": "Specific algorithm, mathematical technique, or data structure adapted from the paper",
  "milestones": [
    {{"phase": "1. ...", "goal": "..."}},
    {{"phase": "2. ...", "goal": "..."}},
    {{"phase": "3. ...", "goal": "..."}},
    {{"phase": "4. ...", "goal": "..."}}
  ],
  "tech_stack": ["Tech1", "Tech2", "Tech3"],
  "difficulty": "Intermediate" or "Advanced" or "Hardcore",
  "viability_score": integer between 83 and 96
}}
"""

    def _normalize_llm_response(self, parsed: Dict[str, Any], domain: str, paper: Dict[str, Any], domains: Optional[list] = None) -> Dict[str, Any]:
        """Normalizes parsed JSON output from Gemini, Ollama, or vLLM into strict blueprint schema."""
        parsed_domains = parsed.get("domains")
        if isinstance(parsed_domains, list) and len(parsed_domains) > 0:
            assigned_domains = [str(d).strip() for d in parsed_domains if str(d).strip()][:3]
        else:
            assigned_domains = domains or [domain]

        diff = parsed.get("difficulty", "Advanced")
        if diff not in ("Beginner", "Intermediate", "Advanced", "Hardcore"):
            diff = "Advanced"

        feasibility = parsed.get("feasibility_timeline")
        if not feasibility or not str(feasibility).strip():
            if diff == "Hardcore":
                feasibility = "160 Hours / 5 Sprints"
            elif diff == "Advanced":
                feasibility = "120 Hours / 4 Sprints"
            elif diff == "Beginner":
                feasibility = "60 Hours / 2 Sprints"
            else:
                feasibility = "80 Hours / 3 Sprints"

        parsed_domain = parsed.get("domain")
        chosen_domain = parsed_domain if parsed_domain and str(parsed_domain).strip() else domain

        parsed_arch = parsed.get("architecture")
        if not isinstance(parsed_arch, dict) or not parsed_arch:
            parsed_arch = {
                "client_or_ingestion": "CLI & REST Ingestion Pipeline",
                "processing_core": parsed.get("core_mechanism") or f"{chosen_domain} Processing Core",
                "storage_or_state": "SQLite / Local State Storage",
                "monitoring": "Telemetry & Metrics Logger"
            }

        parsed_milestones = parsed.get("milestones")
        if not isinstance(parsed_milestones, list) or not parsed_milestones:
            parsed_milestones = [
                {"phase": "1. Foundation", "goal": "Core algorithmic prototype & data structures"},
                {"phase": "2. Engine", "goal": "State machine, storage, & processing loop"},
                {"phase": "3. API & CLI", "goal": "Expose client endpoints & testing harness"},
                {"phase": "4. Hardening", "goal": "Benchmarking, telemetry, & documentation"}
            ]

        core_concept = parsed.get("core_concept") or (parsed.get("summary", "").split(".")[0] + ".")

        return {
            "domain": chosen_domain,
            "domains": assigned_domains,
            "feasibility_timeline": str(feasibility),
            "title": parsed.get("title", f"Project: {paper.get('title')}"),
            "core_concept": core_concept,
            "target_service": parsed.get("target_service", f"{chosen_domain} Service Daemon"),
            "novelty": parsed.get("novelty", parsed.get("core_mechanism", "")),
            "selling_point": parsed.get("selling_point", "High-impact portfolio demonstration of systems engineering."),
            "summary": parsed.get("summary", core_concept),
            "architecture": json.dumps(parsed_arch),
            "core_mechanism": parsed.get("core_mechanism", ""),
            "milestones": json.dumps(parsed_milestones),
            "tech_stack": json.dumps(parsed.get("tech_stack", ["Python", "FastAPI", "SQLite"])),
            "difficulty": diff,
            "viability_score": int(parsed.get("viability_score", 90))
        }

    def _synthesize_with_gemini(self, paper: Dict[str, Any], domain: str, domains: Optional[list] = None, allow_iot: bool = False, fast_mode: bool = False) -> Optional[Dict[str, Any]]:
        """Invokes Google Gemini LLM API endpoint. Re-raises HTTP errors for ModelRouter failover."""
        prompt = self._build_fast_prompt(paper, domain) if fast_mode else self._build_prompt(paper, domain, domains=domains, allow_iot=allow_iot)
        candidate_models = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-2.5-pro"]
        last_err = None

        for model in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.gemini_api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}
            }

            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            try:
                with urllib.request.urlopen(req, timeout=15.0) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        text_resp = data["candidates"][0]["content"]["parts"][0]["text"]
                        parsed = json.loads(text_resp)
                        return self._normalize_llm_response(parsed, domain, paper, domains=domains)
            except urllib.error.HTTPError as err:
                last_err = err
                if err.code in (404, 503):
                    continue
                raise err
            except Exception as exc:
                last_err = exc
                continue

        if last_err:
            raise last_err
        return None

    def _synthesize_with_ollama(self, paper: Dict[str, Any], domain: str, domains: Optional[list] = None, allow_iot: bool = False, fast_mode: bool = False) -> Optional[Dict[str, Any]]:
        """
        Invokes local Ollama worker (http://localhost:11434/api/generate or http://localhost:11435/api/generate) for true local synthesis.
        Executes on local hardware with primary model and fast fallback without disabling the worker session.
        """
        prompt = self._build_fast_prompt(paper, domain) if fast_mode else self._build_prompt(paper, domain, domains=domains, allow_iot=allow_iot)
        predict_tokens = 350 if fast_mode else 1024
        system_prefix = (
            "You are a Principal Software Architect evaluating academic CS research papers. "
            "Return ONLY a valid JSON object matching the requested schema with zero markdown formatting."
        )

        # 1. Primary: rapid synthesis via coordinator using 'triage_model' -> qwen2.5:7b
        #    High-signal technical synthesis, fully conforms to JSON schema.
        try:
            parsed = self.ollama_worker.generate(
                prompt=prompt,
                system=system_prefix,
                timeout=120.0 if fast_mode else 360.0,
                model_override="triage_model",
                num_predict=predict_tokens
            )
            if parsed and isinstance(parsed, dict):
                _safe_stderr_write(f"[ModelRouter] Rapid coordinator synthesis completed (triage_model: qwen2.5:7b) for '{paper.get('title')}'\n")
                return self._normalize_llm_response(parsed, domain, paper, domains=domains)
        except Exception as exc:
            _safe_stderr_write(f"[ModelRouter] Primary triage_model failed ({exc}). Attempting agentic_worker_model fallback...\n")
            time.sleep(1.0)
            # 2. Fallback: 'agentic_worker_model' -> hermes3:8b via coordinator
            try:
                parsed = self.ollama_worker.generate(
                    prompt=prompt,
                    system=system_prefix,
                    timeout=240.0 if fast_mode else 480.0,
                    model_override="agentic_worker_model",
                    num_predict=predict_tokens
                )
                if parsed and isinstance(parsed, dict):
                    _safe_stderr_write(f"[ModelRouter] Coordinator fallback (agentic_worker_model) completed for '{paper.get('title')}'\n")
                    return self._normalize_llm_response(parsed, domain, paper, domains=domains)
            except Exception as e2:
                _safe_stderr_write(f"[ModelRouter] Coordinator fallback also failed ({e2}).\n")

        # Do NOT set self._ollama_disabled_this_session = True so future papers can still be processed!
        return None

    def _synthesize_with_vllm(self, paper: Dict[str, Any], domain: str, domains: Optional[list] = None, allow_iot: bool = False, fast_mode: bool = False) -> Optional[Dict[str, Any]]:
        """
        Invokes local vLLM inference engine (http://localhost:8000/v1) with RadixAttention prefix caching.
        Functions as high-velocity failover when Gemini cloud quotas are exhausted.
        """
        prompt = self._build_fast_prompt(paper, domain) if fast_mode else self._build_prompt(paper, domain, domains=domains, allow_iot=allow_iot)
        system_prefix = (
            "You are a Principal Software Architect evaluating academic CS research papers. "
            "Return ONLY a valid JSON object matching the requested schema with zero markdown formatting."
        )

        payload = {
            "model": self.vllm_model,
            "messages": [
                {"role": "system", "content": system_prefix},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "extra_body": {
                "radix_attention": True,
                "prefix_cache": True
            }
        }

        url = f"{self.vllm_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "X-Radix-Prefix-Cache": "true"
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers
            )
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    content = data["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    _safe_stderr_write(f"[ModelRouter] vLLM local synthesis completed successfully for '{paper.get('title')}'\n")
                    return self._normalize_llm_response(parsed, domain, paper, domains=domains)
        except Exception as exc:
            _safe_stderr_write(f"[ModelRouter] Local vLLM failover attempt failed ({exc}).\n")
            self._vllm_disabled_this_session = True
            return None
        return None
