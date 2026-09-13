# 🎓 Academic Ideation Platform

[![Stack: React 18](https://img.shields.io/badge/Frontend-React%2018%20%7C%20Vite%20%7C%20Tailwind-61dafb?style=flat-square&logo=react)](https://github.com/Jaswanth1902/academic-ideation-platform)
[![Backend: FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%7C%20Python%203.11-009688?style=flat-square&logo=fastapi)](https://github.com/Jaswanth1902/academic-ideation-platform)
[![Inference: Ollama / vLLM](https://img.shields.io/badge/Inference-Ollama%20%7C%20vLLM%20Local-black?style=flat-square)](https://github.com/Jaswanth1902/academic-ideation-platform)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)

An end-to-end, self-hosted **Academic Research & Project Ideation Engine**. Combines a reactive TypeScript/Tailwind exploration workbench with an autonomous Python backend that cross-references research hypotheses against academic paper corpuses, computes multi-dimensional feasibility scores, and generates rigorous problem statements using local LLM inference.

```
┌────────────────────────┐      ┌─────────────────────────┐      ┌────────────────────────┐
│  React + Vite Frontend │ <--> │  FastAPI Backend Engine │ <--> │ Local Ollama / vLLM    │
│  (Interactive Matrix)  │ HTTP │  (Scoring & Synthesis)  │ HTTP │ (Llama 3 8B / Qwen 2.5)│
└────────────────────────┘      └─────────────────────────┘      └────────────────────────┘
                                             │
                                             ▼
                                ┌─────────────────────────┐
                                │   SQLite Academic DB    │
                                │   (Embeddings & Cache)  │
                                └─────────────────────────┘
```

---

## ⚡ Core Capabilities

- **Corpus-Grounded Idea Synthesis**: Ingests arXiv, IEEE, and custom academic paper datasets to ground student and lab proposals in verified literature.
- **Multi-Factor Feasibility Scoring**: Evaluates candidate projects across:
  - *Technical Complexity* (algorithmic depth, compute requirements)
  - *Novelty Index* (distance from published prior art)
  - *Implementation Feasibility* (dataset availability, hardware constraints)
  - *Academic Value* (impact potential and publication viability)
- **Zero-Cloud Air-Gapped Inference**: Runs natively against local **Ollama** or **vLLM** endpoints with automatic prompt formatting and JSON schema validation.
- **Interactive Matrix Explorer**: High-density React dashboard with category filtering, real-time search, and instant PDF/Markdown report export.

---

## 🏗️ Architecture

The repository is structured as an ergonomic full-stack application:

```text
academic-ideation-platform/
├── backend/
│   ├── app/                 # FastAPI routes, controllers, and schemas
│   ├── data/                # Seed academic corpuses and database migrations
│   ├── tests/               # Pytest integration and scoring unit tests
│   ├── academic_cli.py      # Standalone terminal CLI for batch idea generation
│   ├── launch.py            # Local orchestration supervisor
│   ├── requirements.txt     # Python dependencies
│   └── .env.example         # Configuration template
├── frontend/
│   ├── src/                 # React 18 components, hooks, and stores
│   ├── package.json         # UI dependencies
│   ├── vite.config.js       # Bundler configuration
│   └── index.html           # Single-page application entry
├── docs/
│   └── SPECIFICATIONS.md    # Formal engineering PRD & scoring formulas
├── docker-compose.yml       # Production container orchestration
└── README.md
```

---

## 🚀 Quickstart

### Prerequisites
- Python 3.10+
- Node.js 18+ and npm
- (Optional) [Ollama](https://ollama.ai/) for offline local LLM inference

---

### Option A: Local Development

#### 1. Start Backend
```bash
cd backend

# Create virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment configuration
cp .env.example .env

# Run FastAPI server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8055 --reload
```
API documentation available at `http://localhost:8055/docs`.

#### 2. Start Frontend
```bash
cd frontend

# Install packages
npm install

# Start Vite development server
npm run dev
```
UI dashboard opens at `http://localhost:5173`.

---

### Option B: Docker Compose
```bash
docker-compose up --build
```
The full-stack application will be live at `http://localhost:3000`.

---

### 💻 Academic CLI Mode

The platform includes a zero-UI terminal CLI for batch processing and automated idea evaluations:

```bash
cd backend
python academic_cli.py --generate --domain "Distributed Systems" --count 5
```

---

## 🧪 Testing

Run the backend test suite:
```bash
cd backend
pytest tests/ -v
```

---

## 📄 License

Distributed under the [MIT License](LICENSE). Copyright (c) 2026 Jaswanth Reddy.
