"""
Configuration module for Academic Project Ideation Platform.
Local-first settings, OpenAlex criteria, domain filters, and DLQ invariants.
"""

import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Auto-load .env file if present
def _load_env(env_path: Path) -> None:
    if env_path.exists():
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass

_load_env(BASE_DIR / ".env")

DB_PATH = os.getenv("ACADEMIC_DB_PATH", str(DATA_DIR / "academic_ideation.db"))

# LLM & Inference Engine Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "triage_model")
VLLM_API_URL = os.getenv("VLLM_API_URL", "http://localhost:8000/v1")
VLLM_MODEL = os.getenv("VLLM_MODEL", "meta-llama/Llama-3-8B-Instruct")

# OpenAlex Ingestion Rules
OPENALEX_API_URL = "https://api.openalex.org/works"
MIN_PUBLICATION_YEAR = 2023
MIN_CITATIONS = 5
MAX_CITATIONS = 50

# Computer Science Concept IDs in OpenAlex
# c41008148: Computer science
# c199360897: Programming language
# c77088390: Distributed computing
# c111919701: Operating system
# c252276716: Computer network
# c76155785: Database
CS_CONCEPT_IDS = [
    "c41008148",
    "c199360897",
    "c77088390",
    "c111919701",
    "c252276716",
    "c76155785",
]

# Strict Software Domains (Expanded 14-Domain Academic Taxonomy)
VALID_DOMAINS = [
    "Database Management",
    "AI/ML",
    "Theory of Computation",
    "Computer Vision",
    "Operations Research",
    "Web Frameworks",
    "GenAI",
    "Big Data Systems",
    "Cryptography",
    "Network Security",
    "Full-Stack",
    "DSA",
    "CN",
    "DBMS",
]

# Strict IoT / Hardware Exclusions (Zero Tolerance)
HARDWARE_EXCLUSIONS = [
    "iot",
    "internet of things",
    "sensor",
    "sensors",
    "sensing",
    "arduino",
    "raspberry pi",
    "microcontroller",
    "mems",
    "fpga",
    "vlsi",
    "circuit",
    "circuits",
    "actuator",
    "embedded hardware",
    "firmware",
    "wearable",
    "drone",
    "robotics",
    "robotic",
    "rfid",
    "zigbee",
    "lora",
    "lorawan",
    "ble beacon",
    "antenna",
    "photovoltaic",
    "battery",
    "analog",
    "asic",
]

# Dead-Letter Queue Policies
MAX_RETRIES = 2

# Server Configuration
SERVER_HOST = os.getenv("API_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("API_PORT", "8055"))
DEBUG_MODE = os.getenv("APP_DEBUG", "False").lower() in ("true", "1")
