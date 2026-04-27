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
from typing import Optional
from memory_mcp_server.config import Settings
from memory_mcp_server.gate import MemoryGate, GateResult
from memory_mcp_server.extract import OllamaExtractor, StubExtractor, BaseExtractor, ExtractionResult
from memory_mcp_server.store import MemoryStore

logger = logging.getLogger(__name__)


class MemoryPipeline:
    """
    Orchestrates the full memory pipeline: Gate → Extract → Store.

    Usage:
        pipeline = MemoryPipeline()           # uses default settings
        result = pipeline.capture("text")     # returns CaptureResult
        memories = pipeline.search("query")    # returns list of dicts
        pipeline.consolidate()                 # runs decay/promotion
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()

        # Layer 1: Gate (cheap classifier)
        self.gate = MemoryGate(
            model_path=self.settings.GATE_MODEL_PATH,
            skip_threshold=self.settings.SKIP_THRESHOLD,
        )

        # Layer 2: Extract (expensive structured extraction)
        # Try Ollama first, fall back to stub if unavailable
        try:
            self.extractor: BaseExtractor = OllamaExtractor(
                model=self.settings.EXTRACT_MODEL,
                base_url=self.settings.OLLAMA_BASE_URL,
            )
        except Exception:
            logger.warning("Ollama extractor unavailable, using stub")
            self.extractor = StubExtractor()

        # Layer 3: Store (database)
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

        Args:
            text: The raw text to process
            source: Where this came from (discord, cli, api, etc.)
            category: Override auto-detected category (optional)
            tier: Override auto-detected tier (optional)

        Returns:
            dict with keys: id, decision, confidence, category, tier, summary, topics

        PIPELINE FLOW:
          1. Gate classifies: SKIP → stop, COLD/ACTIVE/PERSIST → continue
          2. Extract summarizes and categorizes
          3. Store persists to SQLite with tier-based TTL
        """
        # Stage 1: Gate
        gate_result = self.gate.classify(text)

        if not gate_result.should_capture:
            logger.debug(f"Gate: SKIP (confidence: {gate_result.confidence:.3f})")
            return {
                "id": None,
                "decision": "SKIP",
                "confidence": gate_result.confidence,
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