"""
Configuration — Environment Variables & Defaults

PATTERN: Environment-based Configuration (Twelve-Factor App)
=============================================================

This follows the "Twelve-Factor App" methodology:
  https://12factor.net/config

Key principle: Configuration should live in environment variables,
NOT in code. This makes the app:
  1. Portable — same code works on Mac, Linux, Docker, Cloud
  2. Testable — override config in tests without touching code
  3. Secure — secrets never checked into source control

We use pydantic-settings because it:
  - Validates types automatically (Path must exist, int must be positive)
  - Loads from .env files OR environment variables
  - Provides defaults for local development
  - Fails fast if required config is missing
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All configuration in one place. Override via env vars or .env file."""

    # ── Paths ──────────────────────────────────────────────
    # BASE_DIR: root directory for all memory data
    # Can be overridden for testing or multi-instance setups
    BASE_DIR: Path = Path(os.environ.get(
        "MEMORY_MCP_HOME",
        str(Path.home() / ".memory-mcp"),
    ))

    # Database location (SQLite single-file)
    DB_PATH: Path = Path("")  # computed from BASE_DIR below

    # Gate model directory (DilBERT fine-tuned)
    GATE_MODEL_PATH: Path = Path("")  # computed below

    # ── Gate Thresholds ────────────────────────────────────
    # These control how aggressive the gate is at filtering.
    # Higher = more selective (fewer memories saved).
    # These are the confidence thresholds for each class:
    #   If the gate is 80% confident something is SKIP → skip it
    #   If 70% confident it's PERSIST → save it permanently
    SKIP_THRESHOLD: float = 0.7
    COLD_THRESHOLD: float = 0.5
    ACTIVE_THRESHOLD: float = 0.5
    PERSIST_THRESHOLD: float = 0.7

    # ── Tier TTLs (seconds) ───────────────────────────────
    # TTL = Time To Live. How long before a memory auto-expires.
    # Inspired by CPU cache hierarchy:
    #   L1 (cold) = very short, L2 (active) = medium, L3 (persist) = forever
    COLD_TTL: int = 86400           # 1 day
    ACTIVE_TTL: int = 30 * 86400   # 30 days
    PERSIST_TTL: int = -1           # -1 = never expires

    # ── Extraction ─────────────────────────────────────────
    # Model for structured extraction (runs via Ollama locally)
    EXTRACT_MODEL: str = "nemotron-3-nano"
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # ── Search ─────────────────────────────────────────────
    # Model for generating search embeddings
    SEARCH_MODEL: str = "all-MiniLM-L6-v2"  # sentence-transformers default
    SEARCH_RESULTS_LIMIT: int = 10

    # ── Server ─────────────────────────────────────────────
    MCP_SERVER_NAME: str = "memory"
    MCP_SERVER_VERSION: str = "0.1.0"

    model_config = {
        "env_prefix": "MEMORY_MCP_",  # env vars: MEMORY_MCP_DB_PATH, etc.
        "env_file": ".env",
    }

    def model_post_init(self, __context):
        """Compute derived paths after loading config."""
        if not self.DB_PATH or self.DB_PATH == Path(""):
            self.DB_PATH = self.BASE_DIR / "memory.db"
        if not self.GATE_MODEL_PATH or self.GATE_MODEL_PATH == Path(""):
            self.GATE_MODEL_PATH = self.BASE_DIR / "models" / "distilbert-memory-gate"

        # Ensure directories exist
        self.BASE_DIR.mkdir(parents=True, exist_ok=True)
        (self.BASE_DIR / "models").mkdir(parents=True, exist_ok=True)