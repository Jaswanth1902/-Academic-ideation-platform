---
title: "Academic Ideation Platform Specs"
source: "01_Projects/Academic_Ideation_Platform"
tags:
  - resource
  - architecture
  - specifications
summary: "Technical specifications for the local-first Academic Project Ideation Platform covering OpenAlex ingestion, LLM synthesis, SQLite DLQ storage, and Swiss Editorial React frontend."
---

# Academic Ideation Platform Specs

Parent Project: [[Academic_Ideation_Platform]]

## Key Takeaways
- OpenAlex CS filter: `publication_year >= 2023`, `cited_by_count: 5..50`, software-exclusive concepts.
- Strict rejection of IoT, microcontrollers, embedded circuits, sensors, and robotics.
- 4 primary software project domains: Full-Stack, DSA, Computer Networks (CN), and DBMS.
- SQLite persistent storage with a 2-retry Dead-Letter Queue (DLQ); silent discard upon exhaustion.
- Swiss Editorial + Soft Claymorphism UI design with 3D flipping Game Cards.

## Detailed Notes

### Background & Context
Computer science students and engineers frequently struggle to find novel, grounded project ideas that demonstrate deep systems engineering principles. Standard portfolio projects (to-do apps, basic clones) fail to impress technical interviewers. This platform continuously harvests emerging peer-reviewed software engineering research from OpenAlex, extracts the foundational algorithms and system concepts, and synthesizes them into modular, high-impact student engineering projects.

### Ingestion & Filtering Rules
- **API Endpoint**: `https://api.openalex.org/works`
- **Filter**: `from_publication_date:2023-01-01`, `cited_by_count:5-50`, `concepts.id` for Computer Science.
- **Exclusion Heuristic**: Any paper with title, abstract, or keywords referencing Arduino, Raspberry Pi, LoRa, sensor node, FPGA, MEMS, embedded firmware, or hardware circuits is immediately filtered out.

### Synthesis Schema
- Project Title & High-concept Pitch
- Viability Domain: `Full-Stack`, `DSA`, `CN`, `DBMS`
- Architectural Components & Data Flow Diagram (Mermaid / structured spec)
- Core Algorithm / Mechanism extracted from the paper
- Phased Implementation Roadmap (Milestones 1 to 4)
- Resume & Technical Interview Pitch

### Dead-Letter Queue (DLQ)
- Each item tracked in `dead_letter_queue` has `retry_count`.
- Max retries: 2.
- Upon 2nd failure, marked `discarded` and silently dropped from active retry cycle.
