"""
Memory Pipeline — Orchestrates Gate → Extract → Store

PATTERN: Pipeline Pattern (Chain of Responsibility)
=====================================================

The Pipeline Pattern connects processing stages in a linear flow:
  Input → Stage 1 → Stage 2 → Stage 3 → Output

Each stage:
  - Receives input from the previous stage
  - Processes it independently
  - Passes output to the next stage

This is identical to:
  - Middleware in Express.js (request → auth → validate → route → response)
  - Image processing in Photoshop (raw → filter → crop → export)
  - ML data pipelines (raw → clean → transform → feature → train)

WHY PIPELINE?
  - Each stage is testable in isolation (unit test the gate without extraction)
  - Each stage is swappable (swap Nemotron for GPT-4o-mini without changing store)
  - Easy to add stages (add "deduplicate" between extract and store)
  - Failure in one stage doesn't crash others (graceful degradation)
"""

import logging
from pathlib import Path
from typing import Optional
from rememberance_mcp.config import Settings
from rememberance_mcp.gate import GateDecision
from rememberance_mcp.gate_backends import (
    DilBERTBackend, HeuristicBackend, OpenAIBackend,
    GateFallbackChain, GateMetrics,
)
from rememberance_mcp.extract import OllamaExtractor, StubExtractor, BaseExtractor
from rememberance_mcp.store import MemoryStore

logger = logging.getLogger(__name__)


class MemoryPipeline:
    """
    Orchestrates the full memory pipeline: Gate → Extract → Store.

    The gate uses a fallback chain: DilBERT → OpenAI → Heuristic
    This means it works on EVERY machine, from day one, no config needed.

    Usage:
        pipeline = MemoryPipeline()           # uses default settings
        result = pipeline.capture("text")     # returns dict
        memories = pipeline.search("query")    # returns list of dicts
        pipeline.consolidate()                 # runs decay/promotion
        metrics = pipeline.metrics_summary()   # effectiveness report
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()

        # ── Layer 1: Gate (fallback chain) ──────────────────────
        # Build the fallback chain based on what's available.
        # HeuristicBackend is ALWAYS included as the last resort.
        backends = []

        # Try DilBERT first (local, fast, free)
        try:
            dilbert = DilBERTBackend(
                model_path=self.settings.GATE_MODEL_PATH,
                skip_threshold=self.settings.SKIP_THRESHOLD,
            )
            backends.append(dilbert)
            logger.info("Gate backend: DilBERT available")
        except Exception:
            logger.info("Gate backend: DilBERT not available")

        # Try OpenAI second (cloud, fast, cheap)
        import os
        openai_key = os.environ.get("OPENAI_API_KEY", "")
        if openai_key:
            try:
                openai = OpenAIBackend(api_key=openai_key)
                backends.append(openai)
                logger.info("Gate backend: OpenAI available")
            except Exception:
                logger.info("Gate backend: OpenAI not available")

        # Heuristic is ALWAYS available (zero dependencies)
        backends.append(HeuristicBackend())
        logger.info("Gate backend: Heuristic (always available)")

        # Metrics for effectiveness monitoring
        metrics_db = self.settings.DB_PATH.parent / "metrics.db"
        self.metrics = GateMetrics(db_path=metrics_db)

        # The fallback chain
        self.gate_chain = GateFallbackChain(
            backends=backends,
            metrics=self.metrics,
        )

        # ── Layer 2: Extract (structured extraction) ───────────
        try:
            self.extractor: BaseExtractor = OllamaExtractor(
                model=self.settings.EXTRACT_MODEL,
                base_url=self.settings.OLLAMA_BASE_URL,
            )
        except Exception:
            logger.warning("Ollama extractor unavailable, using stub")
            self.extractor = StubExtractor()

        # ── Layer 3: Store (database) ───────────────────────────
        self.store = MemoryStore(
            db_path=self.settings.DB_PATH,
            cold_ttl=self.settings.COLD_TTL,
            active_ttl=self.settings.ACTIVE_TTL,
            persist_ttl=self.settings.PERSIST_TTL,
        )

    def capture(self, text: str, source: str = "cli",
                category: Optional[str] = None, tier: Optional[str] = None) -> dict:
        """
        Run the full pipeline on a piece of text.

        PIPELINE FLOW:
          1. Gate classifies (with fallback chain): SKIP → stop, COLD/ACTIVE/PERSIST → continue
          2. Extract summarizes and categorizes
          3. Store persists to SQLite with tier-based TTL
        """
        # Stage 1: Gate (with fallback chain and metrics)
        gate_result, backend_used, fallback_used = self.gate_chain.classify(text)

        if gate_result.decision == GateDecision.SKIP:
            logger.debug(f"Gate: SKIP (confidence: {gate_result.confidence:.3f}, backend: {backend_used})")
            return {
                "id": None,
                "decision": "SKIP",
                "confidence": gate_result.confidence,
                "backend": backend_used,
                "fallback_used": fallback_used,
                "category": None,
                "tier": None,
                "summary": None,
                "topics": None,
            }

        # Stage 2: Extract
        extraction = self.extractor.extract(
            text, source=source, gate_decision=gate_result.decision.value
        )

        # Override with explicit values if provided
        final_category = category or extraction.category
        final_tier = tier or extraction.tier

        # Stage 3: Store
        mem_id = self.store.store(
            content=text,
            summary=extraction.summary,
            category=final_category,
            tier=final_tier,
            key_topics=extraction.key_topics,
            source=source,
        )

        return {
            "id": mem_id,
            "decision": gate_result.decision.value,
            "confidence": gate_result.confidence,
            "backend": backend_used,
            "fallback_used": fallback_used,
            "category": final_category,
            "tier": final_tier,
            "summary": extraction.summary,
            "topics": extraction.key_topics,
        }

    def search(self, query: str, category: Optional[str] = None,
               tier: Optional[str] = None, limit: int = 10) -> list[dict]:
        """Search stored memories by text and metadata filters."""
        return self.store.search(query, category=category, tier=tier, limit=limit)

    def get(self, mem_id: str) -> Optional[dict]:
        """Get a specific memory by ID."""
        return self.store.get(mem_id)

    def consolidate(self) -> dict:
        """Run the decay/promotion cycle on stored memories."""
        return self.store.consolidate()

    def delete(self, mem_id: str) -> bool:
        """Delete a specific memory."""
        return self.store.delete(mem_id)

    def metrics_summary(self, hours: int = 24) -> dict:
        """
        Get effectiveness metrics for the gate.

        Use this to answer:
          - Is DilBERT better than heuristics? (compare by_backend)
          - What % of messages get SKIPPED? (skip_rate)
          - Is the fallback working? (fallback_rate)
          - How confident is the gate overall? (avg_confidence)
        """
        return self.metrics.summary(hours=hours)