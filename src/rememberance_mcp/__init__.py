"""
Remembrance MCP — Universal memory for AI agents.

ARCHITECTURE PATTERN: Three-Layer Pipeline (Cascading Classifier)
================================================================

This server uses a pattern common in production AI systems:

  Layer 1 (GATE)    → Cheap, fast model decides IF we should save
  Layer 2 (EXTRACT) → Expensive, slow model decides WHAT to save
  Layer 3 (STORE)   → Database write with tier-based TTL

WHY THIS PATTERN?
- 80%+ of conversation messages are not worth storing ("ok", "thanks", "hmm")
- Running a big model on every message is expensive and slow
- The gate model is ~100x cheaper and ~20x faster than the extract model
- This "funnel" pattern is used by Google, Meta, etc. for content moderation,
  spam detection, and recommendation filtering

KEY CONCEPTS:
- MCP (Model Context Protocol): JSON-RPC protocol that lets AI agents call tools
- Cascading Classifier: Chain of models, cheap→expensive, early-exit on rejection
- TTL (Time To Live): Auto-expiry based on importance tier (like CPU cache L1/L2/L3)
- Consolidation: Periodic garbage collection that promotes/demotes memory tiers

DESIGN DECISIONS:
- SQLite for storage: Zero-config, single-file, fast enough for local use,
  and universally available. No server process needed.
- DilBERT for gate: DistilBERT is a "distilled" (compressed) version of BERT.
  It's ~40% smaller, ~60% faster, with 97% of the accuracy.
  Fine-tuned on our 4-class dataset for memory relevance.
- Nemotron for extraction: Small but capable model for structured extraction.
  Runs locally via Ollama, no API key needed.
"""

from rememberance_mcp.config import Settings
from rememberance_mcp.gate import MemoryGate, GateDecision, GateResult
from rememberance_mcp.extract import BaseExtractor, OllamaExtractor, StubExtractor, ExtractionResult
from rememberance_mcp.store import MemoryStore, Memory
from rememberance_mcp.pipeline import MemoryPipeline
from rememberance_mcp.server import create_server

__all__ = [
    "Settings",
    "MemoryGate",
    "GateDecision",
    "GateResult",
    "BaseExtractor",
    "OllamaExtractor",
    "StubExtractor",
    "ExtractionResult",
    "MemoryStore",
    "Memory",
    "MemoryPipeline",
    "create_server",
    "main",
]


def main():
    """Entry point for `memory-mcp` CLI command."""
    import asyncio
    server = create_server()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()