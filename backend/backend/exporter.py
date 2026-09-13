"""
Proposal Document Exporter.
Compiles synthesized project blueprints, 4-point software architectures,
and OpenAlex research citations into executive-grade Microsoft Word (.docx) files.
Integrates with report-generator skill (99_Meta/Scripts/report_generator.py) with
deterministic OpenXML zip fallback for zero-dependency portability.
"""

import os
import sys
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, Any, Optional
import xml.sax.saxutils as saxutils


def generate_proposal_markdown(idea: Dict[str, Any]) -> str:
    """Generates structured GitHub-flavored Markdown for an executive project proposal."""
    title = idea.get("title", "Software Engineering Project Proposal")
    domain = idea.get("domain", "Full-Stack")
    viability = idea.get("viability_score", 90)
    difficulty = idea.get("difficulty", "Advanced")
    summary = idea.get("summary", "")

    core_concept = idea.get("core_concept") or (summary.split(".")[0] + "." if summary else "High-performance systems engineering architecture.")
    target_service = idea.get("target_service") or f"{domain} Production Daemon / Runtime"
    novelty = idea.get("novelty") or idea.get("core_mechanism") or "Algorithmic optimization derived from literature."
    selling_point = idea.get("selling_point") or "Demonstrates advanced systems programming and low-latency architecture."

    # Parse JSON fields if strings
    architecture = idea.get("architecture", {})
    if isinstance(architecture, str):
        try:
            architecture = json.loads(architecture)
        except Exception:
            architecture = {}

    milestones = idea.get("milestones", [])
    if isinstance(milestones, str):
        try:
            milestones = json.loads(milestones)
        except Exception:
            milestones = []

    tech_stack = idea.get("tech_stack", [])
    if isinstance(tech_stack, str):
        try:
            tech_stack = json.loads(tech_stack)
        except Exception:
            tech_stack = []

    md = []
    domains_str = ", ".join(idea.get("domains", [])) if idea.get("domains") else idea.get("domain", "Full-Stack")
    timeline = idea.get("feasibility_timeline", "120 Hours / 4 Sprints")
    md.append(f"# Executive Capstone Proposal: {title}\n")
    md.append(f"> **Domain(s)**: {domains_str}  |  **Viability Index**: {viability}/100  |  **Engineering Level**: {difficulty}  |  **Timeline**: {timeline}\n")
    md.append("## 1. Executive Summary\n")
    md.append(f"{summary}\n")

    md.append("## 2. Four-Point Software Architecture Blueprint\n")
    md.append(f"- **Core Concept**: {core_concept}")
    md.append(f"- **Target Service**: {target_service}")
    md.append(f"- **Technical Novelty**: {novelty}")
    md.append(f"- **Portfolio Selling Point**: {selling_point}\n")

    md.append("## 3. Core Mechanism & Algorithmic Principles\n")
    md.append(f"{idea.get('core_mechanism', 'Standard systems engineering implementation.')}\n")

    if architecture:
        md.append("## 4. Architectural Tiers & Component Layout\n")
        for tier, desc in architecture.items():
            tier_name = tier.replace("_", " ").title()
            md.append(f"### {tier_name}")
            md.append(f"{desc}\n")

    if milestones:
        md.append("## 5. Implementation Roadmap & Phases\n")
        for m in milestones:
            phase = m.get("phase", "Phase")
            goal = m.get("goal", "")
            md.append(f"- **{phase}**: {goal}")
        md.append("")

    if tech_stack:
        md.append("## 6. Production Technology Stack\n")
        md.append(f"**Verified Technologies**: {', '.join(tech_stack)}\n")

    # Research citation & grounding
    md.append("## 7. Academic Grounding & Peer-Reviewed Citation\n")
    md.append(f"- **Grounded Paper**: {idea.get('paper_title', 'Peer-Reviewed Research')}")
    if idea.get("paper_authors"):
        md.append(f"- **Authors**: {idea.get('paper_authors')}")
    md.append(f"- **Publication Year**: {idea.get('publication_year', 2024)}")
    md.append(f"- **Academic Citations**: {idea.get('cited_by_count', 0)}")
    if idea.get("doi"):
        md.append(f"- **DOI Identifier**: [{idea.get('doi')}]({idea.get('doi')})")

    md.append("\n---\n*Generated autonomously by Academic Project Ideation Platform.*")
    return "\n".join(md)


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


def _build_body_xml(markdown_text: str) -> str:
    """Parses markdown lines into OpenXML document body paragraphs."""
    lines = markdown_text.splitlines()
    body_xml_parts = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        escaped = saxutils.escape(stripped)

        if stripped.startswith("# Project "):
            h_text = saxutils.escape(stripped[2:])
            body_xml_parts.append(
                f'<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
                f'<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
                f'<w:r><w:rPr><w:b/><w:sz w:val="40"/><w:color w:val="0E1116"/></w:rPr>'
                f'<w:t>{h_text}</w:t></w:r></w:p>'
            )
        elif stripped.startswith("# "):
            h_text = saxutils.escape(stripped[2:])
            body_xml_parts.append(
                f'<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
                f'<w:r><w:rPr><w:b/><w:sz w:val="44"/><w:color w:val="0E1116"/></w:rPr>'
                f'<w:t>{h_text}</w:t></w:r></w:p>'
            )
        elif stripped.startswith("## "):
            h_text = saxutils.escape(stripped[3:])
            body_xml_parts.append(
                f'<w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr>'
                f'<w:r><w:rPr><w:b/><w:sz w:val="32"/><w:color w:val="E5534B"/></w:rPr>'
                f'<w:t>{h_text}</w:t></w:r></w:p>'
            )
        elif stripped.startswith("### "):
            h_text = saxutils.escape(stripped[4:])
            body_xml_parts.append(
                f'<w:p><w:pPr><w:pStyle w:val="Heading3"/></w:pPr>'
                f'<w:r><w:rPr><w:b/><w:sz w:val="26"/><w:color w:val="161B22"/></w:rPr>'
                f'<w:t>{h_text}</w:t></w:r></w:p>'
            )
        elif stripped.startswith("- ") or stripped.startswith("* "):
            bullet_text = saxutils.escape(stripped[2:])
            body_xml_parts.append(
                f'<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr>'
                f'<w:r><w:rPr><w:sz w:val="22"/><w:color w:val="30363D"/></w:rPr>'
                f'<w:t>• {bullet_text}</w:t></w:r></w:p>'
            )
        elif stripped.startswith("> "):
            quote_text = saxutils.escape(stripped[2:])
            body_xml_parts.append(
                f'<w:p><w:pPr><w:pBdr><w:left w:val="single" w:sz="24" w:space="15" w:color="E5534B"/></w:pBdr></w:pPr></w:p>'
                f'<w:r><w:rPr><w:i/><w:sz w:val="22"/><w:color w:val="666666"/></w:rPr>'
                f'<w:t>{quote_text}</w:t></w:r></w:p>'
            )
        elif stripped in ("---", "***"):
            body_xml_parts.append(
                f'<w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="12" w:space="8" w:color="D0D7DE"/></w:pBdr></w:pPr></w:p>'
            )
        else:
            body_xml_parts.append(
                f'<w:p><w:r><w:rPr><w:sz w:val="22"/><w:color w:val="161B22"/></w:rPr>'
                f'<w:t>{escaped}</w:t></w:r></w:p>'
            )

    return "".join(body_xml_parts)


def build_fallback_docx_bytes(markdown_text: str, title: str = "Proposal") -> bytes:
    """
    Constructs a valid, standard Office Open XML (.docx) binary package in-memory.
    Explicitly retrieves .getvalue() from io.BytesIO before buffer disposal,
    preventing any 'I/O operation on closed file' exceptions.
    """
    import io

    body_content = _build_body_xml(markdown_text)

    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
    <w:body>
        {body_content}
        <w:sectPr>
            <w:pgSz w:w="12240" w:h="15840"/>
            <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>
        </w:sectPr>
    </w:body>
</w:document>"""

    content_types_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
    <Default Extension="xml" ContentType="application/xml"/>
    <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

    rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

    bio = io.BytesIO()
    # Explicit zipfile handling: write archive parts, close zipfile to flush central directory,
    # then safely extract bytes from the still-open BytesIO buffer.
    zf = zipfile.ZipFile(bio, "w", compression=zipfile.ZIP_DEFLATED)
    try:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("word/document.xml", document_xml)
    finally:
        zf.close()

    raw_docx = bio.getvalue()
    bio.close()
    return raw_docx


def build_fallback_docx(markdown_text: str, output_path: Any, title: str = "Proposal") -> Any:
    """
    Constructs a valid, standard Office Open XML (.docx) binary package from markdown.
    Supports file paths, Path objects, and io.BytesIO/file-like targets without closure errors.
    """
    import io

    raw_bytes = build_fallback_docx_bytes(markdown_text, title=title)

    if isinstance(output_path, (str, Path)):
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(raw_bytes)
        return out_path
    elif isinstance(output_path, io.BytesIO) or hasattr(output_path, "write"):
        output_path.write(raw_bytes)
        return output_path
    else:
        out_path = Path(str(output_path))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(raw_bytes)
        return out_path


def export_idea_to_docx_bytes(idea: Dict[str, Any]) -> bytes:
    """Compiles an evaluated idea directly into raw .docx bytes in-memory."""
    md_content = generate_proposal_markdown(idea)
    return build_fallback_docx_bytes(md_content, title=idea.get("title", "Proposal"))


def export_idea_to_docx(idea: Dict[str, Any], output_path: Optional[Any] = None) -> Any:
    """
    Compiles an evaluated idea into an executive-grade .docx report.
    Attempts Pandoc compilation via report-generator first, falling back to clean OpenXML packager.
    Handles both Path targets and in-memory io.BytesIO streams safely.
    """
    import io

    md_content = generate_proposal_markdown(idea)
    title_slug = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in idea.get("title", "Proposal"))

    if isinstance(output_path, io.BytesIO) or (output_path is not None and hasattr(output_path, "write")):
        raw_bytes = build_fallback_docx_bytes(md_content, title=idea.get("title", "Proposal"))
        output_path.write(raw_bytes)
        return output_path

    if not output_path:
        reports_dir = Path(__file__).resolve().parent.parent / "03_Resources" / "Reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        output_path = reports_dir / f"{title_slug}.docx"
    else:
        output_path = Path(output_path)

    # Try Pandoc report_generator from 99_Meta
    try:
        workspace_root = Path(__file__).resolve().parent.parent.parent.parent
        report_gen_script = workspace_root / "99_Meta" / "Scripts" / "report_generator.py"
        if report_gen_script.exists():
            import importlib.util
            if "report_generator" in sys.modules:
                mod = sys.modules["report_generator"]
            else:
                spec = importlib.util.spec_from_file_location("report_generator", str(report_gen_script))
                mod = importlib.util.module_from_spec(spec)
                sys.modules["report_generator"] = mod
                spec.loader.exec_module(mod)

            tmp_dir = tempfile.mkdtemp()
            tmp_md_path = Path(tmp_dir) / "proposal.md"
            tmp_md_path.write_text(md_content, encoding="utf-8")

            try:
                res = mod.compile_report(
                    input_md=tmp_md_path,
                    template="executive",
                    output_filename=str(output_path),
                    silent=True
                )

                if res and res.exists() and res.stat().st_size > 0:
                    return res
            finally:
                try:
                    if tmp_md_path.exists():
                        tmp_md_path.unlink()
                    Path(tmp_dir).rmdir()
                except Exception:
                    pass
    except Exception as exc:
        _safe_stderr_write(f"[Exporter] Pandoc report-generator unavailable ({exc}). Using standard OpenXML engine.\n")

    # Robust fallback: standard Office Open XML package
    return build_fallback_docx(md_content, output_path, title=idea.get("title", "Proposal"))


def generate_bulk_proposal_markdown(ideas: list) -> str:
    """
    Generates a comprehensive master document containing:
    1. The Academic Ideation Platform methodology preface
    2. Trademarked signature authority ("Sai Jaswanth Reddy")
    3. Full systems engineering blueprints and citations for all ideas in SQLite.
    """
    md = []
    total_ideas = len(ideas)

    # Master Title & Signature
    md.append("# Academic Project Ideation Platform: Master Systems Engineering Archive\n")
    md.append(f"> **Platform Architect & Lead Systems Researcher**: Sai Jaswanth Reddy  \n"
              f"> **Document Scope**: Master Compilation of {total_ideas} Synthesized CS Project Blueprints  \n"
              f"> **Grounding**: OpenAlex Computer Science Scholarly Graph (≥2023, 5–50 Citations)  \n"
              f"> **Distribution Authority**: Academic Ideation Platform Enterprise Engine\n")

    # Methodology Preface
    md.append("## Methodology & Systems Architecture Preface\n")
    md.append("### 1. The Research-to-Architecture Paradigm")
    md.append("Traditional computer science education frequently suffers from a severe bifurcation: theoretical academic literature remains ungrounded in real-world software engineering, while student capstone projects often replicate commoditized tutorials without technical novelty.")
    md.append("The **Academic Project Ideation Platform** bridges this gap by continuously interrogating peer-reviewed research papers and compiling their mathematical and algorithmic insights into production-grade systems engineering blueprints.\n")

    md.append("### 2. Scholarly Graph Ingestion Criteria")
    md.append("Candidates are harvested via the OpenAlex API under deterministic constraints:")
    md.append("- **Publication Recency (≥2023)**: Ensures technical applicability to modern multi-core, non-volatile memory (NVMe/CXL), and asynchronous runtime environments.")
    md.append("- **Citation Calibration (5–50 Citations)**: Filters out unvalidated preprints while avoiding oversaturated, commoditized concepts.")
    md.append("- **Zero-Tolerance Hardware / IoT Heuristic**: Systematically identifies and excludes physical hardware prototypes, FPGA implementations, and microcontrollers unless explicitly toggled.\n")

    md.append("### 3. Four-Point Scannable Blueprint Standard")
    md.append("Each research breakthrough is synthesized into four core engineering criteria:")
    md.append("- **Core Concept**: Physical and algorithmic abstraction grounding the project.")
    md.append("- **Target Service**: Real-world daemon, microservice, or systems runtime to build.")
    md.append("- **Technical Novelty**: Differentiating algorithmic optimization derived from literature.")
    md.append("- **Portfolio Selling Point**: High-impact interview talking point for engineering career defense.\n")

    md.append("### 4. Trademark Certification & Signature")
    md.append("This document and its synthesized architectural blueprints have been engineered and certified under the trademark authority of **Sai Jaswanth Reddy**.")
    md.append("All blueprints are structured for deterministic replication and rigorous code review.\n")
    md.append("---\n")

    # Iterate over all project blueprints
    for idx, idea in enumerate(ideas, 1):
        title = idea.get("title", f"Project Blueprint {idx}")
        domain = idea.get("domain", "Full-Stack")
        viability = idea.get("viability_score", 90)
        difficulty = idea.get("difficulty", "Advanced")
        summary = idea.get("summary", "")

        core_concept = idea.get("core_concept") or (summary.split(".")[0] + "." if summary else "High-performance systems architecture implementation.")
        target_service = idea.get("target_service") or f"{domain} Production Daemon / Runtime"
        novelty = idea.get("novelty") or idea.get("core_mechanism") or "Algorithmic optimization derived from literature."
        selling_point = idea.get("selling_point") or "Demonstrates advanced systems programming and low-latency architecture."

        architecture = idea.get("architecture", {})
        if isinstance(architecture, str):
            try:
                architecture = json.loads(architecture)
            except Exception:
                architecture = {}

        milestones = idea.get("milestones", [])
        if isinstance(milestones, str):
            try:
                milestones = json.loads(milestones)
            except Exception:
                milestones = []

        tech_stack = idea.get("tech_stack", [])
        if isinstance(tech_stack, str):
            try:
                tech_stack = json.loads(tech_stack)
            except Exception:
                tech_stack = []

        md.append(f"# Project {idx}: {title}\n")
        md.append(f"> **Domain**: {domain}  |  **Viability Index**: {viability}/100  |  **Difficulty**: {difficulty}  |  **Architect**: Sai Jaswanth Reddy\n")

        md.append("## 1. Executive Summary\n")
        md.append(f"{summary}\n")

        md.append("## 2. Four-Point Software Architecture Blueprint\n")
        md.append(f"- **Core Concept**: {core_concept}")
        md.append(f"- **Target Service**: {target_service}")
        md.append(f"- **Technical Novelty**: {novelty}")
        md.append(f"- **Portfolio Selling Point**: {selling_point}\n")

        md.append("## 3. Core Mechanism & Algorithmic Principles\n")
        md.append(f"{idea.get('core_mechanism', 'Standard systems engineering implementation.')}\n")

        if architecture:
            md.append("## 4. Architectural Tiers & Component Layout\n")
            for tier, desc in architecture.items():
                tier_name = tier.replace("_", " ").title()
                md.append(f"### {tier_name}")
                md.append(f"{desc}\n")

        if milestones:
            md.append("## 5. Implementation Roadmap & Phases\n")
            for m in milestones:
                phase = m.get("phase", "Phase")
                goal = m.get("goal", "")
                md.append(f"- **{phase}**: {goal}")
            md.append("")

        if tech_stack:
            md.append("## 6. Production Technology Stack\n")
            md.append(f"**Verified Technologies**: {', '.join(tech_stack)}\n")

        md.append("## 7. Academic Grounding & Peer-Reviewed Citation\n")
        md.append(f"- **Grounded Paper**: {idea.get('paper_title', 'Peer-Reviewed Research')}")
        if idea.get("paper_authors"):
            md.append(f"- **Authors**: {idea.get('paper_authors')}")
        md.append(f"- **Publication Year**: {idea.get('publication_year', 2024)}")
        md.append(f"- **Academic Citations**: {idea.get('cited_by_count', 0)}")
        if idea.get("doi"):
            md.append(f"- **DOI Identifier**: [{idea.get('doi')}]({idea.get('doi')})")

        md.append(f"\n*Blueprint {idx} of {total_ideas} — Certified by Sai Jaswanth Reddy*\n")
        md.append("\n---\n")

    md.append("\n*End of Master Archive — Academic Project Ideation Platform by Sai Jaswanth Reddy.*")
    return "\n".join(md)


def export_all_ideas_to_docx_bytes(ideas: list) -> bytes:
    """Compiles all ideas into an in-memory master .docx archive bytes."""
    md_content = generate_bulk_proposal_markdown(ideas)
    return build_fallback_docx_bytes(md_content, title="Academic Ideation Master Archive")


def export_all_ideas_to_docx(ideas: list, output_path: Optional[Any] = None) -> Any:
    """
    Compiles all project blueprints into a master .docx archive.
    Attempts Pandoc compilation via report-generator first, falling back to clean OpenXML packager.
    Handles file paths, Path objects, and in-memory streams safely.
    """
    import io

    md_content = generate_bulk_proposal_markdown(ideas)

    if isinstance(output_path, io.BytesIO) or (output_path is not None and hasattr(output_path, "write")):
        raw_bytes = build_fallback_docx_bytes(md_content, title="Academic Ideation Master Archive")
        output_path.write(raw_bytes)
        return output_path

    if not output_path:
        reports_dir = Path(__file__).resolve().parent.parent / "03_Resources" / "Reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        output_path = reports_dir / "Academic_Ideation_Master_Archive.docx"
    else:
        output_path = Path(output_path)

    # Try Pandoc report_generator from 99_Meta
    try:
        workspace_root = Path(__file__).resolve().parent.parent.parent.parent
        report_gen_script = workspace_root / "99_Meta" / "Scripts" / "report_generator.py"
        if report_gen_script.exists():
            import importlib.util
            if "report_generator" in sys.modules:
                mod = sys.modules["report_generator"]
            else:
                spec = importlib.util.spec_from_file_location("report_generator", str(report_gen_script))
                mod = importlib.util.module_from_spec(spec)
                sys.modules["report_generator"] = mod
                spec.loader.exec_module(mod)

            tmp_dir = tempfile.mkdtemp()
            tmp_md_path = Path(tmp_dir) / "master_archive.md"
            tmp_md_path.write_text(md_content, encoding="utf-8")

            try:
                res = mod.compile_report(
                    input_md=tmp_md_path,
                    template="executive",
                    output_filename=str(output_path),
                    silent=True
                )

                if res and res.exists() and res.stat().st_size > 0:
                    return res
            finally:
                try:
                    if tmp_md_path.exists():
                        tmp_md_path.unlink()
                    Path(tmp_dir).rmdir()
                except Exception:
                    pass
    except Exception as exc:
        _safe_stderr_write(f"[Exporter] Pandoc report-generator unavailable for bulk export ({exc}). Using standard OpenXML engine.\n")

    # Robust fallback: standard Office Open XML package
    return build_fallback_docx(md_content, output_path, title="Academic Ideation Master Archive")


def generate_ideas_csv_string(ideas: list) -> str:
    """
    Serializes project blueprints into a clean, comprehensive CSV format.
    Includes all 4-point architecture specifications, grounded academic metadata,
    and trademark signature authority ("Sai Jaswanth Reddy").
    """
    import csv
    import io

    output = io.StringIO()
    # Write UTF-8 BOM for seamless double-click opening in Microsoft Excel
    output.write("\ufeff")

    fieldnames = [
        "id",
        "title",
        "domain",
        "domains",
        "feasibility_timeline",
        "viability_score",
        "difficulty",
        "core_concept",
        "target_service",
        "technical_novelty",
        "portfolio_selling_point",
        "summary",
        "core_mechanism",
        "tech_stack",
        "architectural_layout",
        "milestones",
        "paper_title",
        "paper_authors",
        "publication_year",
        "cited_by_count",
        "doi",
        "signature_authority",
        "created_at"
    ]

    writer = csv.DictWriter(output, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()

    for idx, idea in enumerate(ideas, 1):
        summary = idea.get("summary", "")
        core_concept = idea.get("core_concept") or (summary.split(".")[0] + "." if summary else "")
        target_service = idea.get("target_service") or f"{idea.get('domain', 'Full-Stack')} Production Daemon"
        novelty = idea.get("novelty") or idea.get("core_mechanism") or ""
        selling_point = idea.get("selling_point") or ""
        domains_str = ", ".join(idea.get("domains", [])) if idea.get("domains") else idea.get("domain", "")

        # Normalize tech stack into readable comma-separated string
        tech_stack = idea.get("tech_stack", [])
        if isinstance(tech_stack, str):
            try:
                tech_stack = json.loads(tech_stack)
            except Exception:
                pass
        tech_stack_str = ", ".join(tech_stack) if isinstance(tech_stack, list) else str(tech_stack)

        # Normalize architecture into compact JSON or string
        arch = idea.get("architecture", {})
        if isinstance(arch, str):
            arch_str = arch
        else:
            arch_str = json.dumps(arch) if arch else ""

        # Normalize milestones into compact string
        milestones = idea.get("milestones", [])
        if isinstance(milestones, str):
            try:
                milestones = json.loads(milestones)
            except Exception:
                pass
        if isinstance(milestones, list):
            milestones_str = " | ".join(f"{m.get('phase', 'Phase')}: {m.get('goal', '')}" for m in milestones if isinstance(m, dict))
        else:
            milestones_str = str(milestones)

        writer.writerow({
            "id": idea.get("id", idx),
            "title": idea.get("title", ""),
            "domain": idea.get("domain", ""),
            "domains": domains_str,
            "feasibility_timeline": idea.get("feasibility_timeline", "120 Hours / 4 Sprints"),
            "viability_score": idea.get("viability_score", 0),
            "difficulty": idea.get("difficulty", "Advanced"),
            "core_concept": core_concept,
            "target_service": target_service,
            "technical_novelty": novelty,
            "portfolio_selling_point": selling_point,
            "summary": summary,
            "core_mechanism": idea.get("core_mechanism", ""),
            "tech_stack": tech_stack_str,
            "architectural_layout": arch_str,
            "milestones": milestones_str,
            "paper_title": idea.get("paper_title", ""),
            "paper_authors": idea.get("paper_authors", ""),
            "publication_year": idea.get("publication_year", ""),
            "cited_by_count": idea.get("cited_by_count", 0),
            "doi": idea.get("doi", ""),
            "signature_authority": "Sai Jaswanth Reddy",
            "created_at": idea.get("created_at", "")
        })

    return output.getvalue()


def export_all_ideas_to_csv_bytes(ideas: list) -> bytes:
    """Compiles all ideas into UTF-8 encoded CSV bytes."""
    csv_str = generate_ideas_csv_string(ideas)
    return csv_str.encode("utf-8")

