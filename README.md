# Remembrance MCP

**Universal memory for AI agents.** Knowledge graph, compiled truth, dream cycle, hybrid search — zero-cost local, accessible from any platform.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green)](https://opensource.org/licenses/Apache-2.0)
[![Tests: 133 passing](https://img.shields.io/badge/tests-133%20passing-brightgreen)]()

> **Why "Remembrance"?** Because AI agents forget. Every conversation starts from scratch. Remembrance gives agents a persistent, evolving memory — entities, relationships, compiled truth, and automated maintenance — so they can *remember* what matters across sessions.

---

## Table of Contents

- [What It Does](#what-it-does)
- [Architecture](#architecture)
- [Core Packages](#core-packages)
- [Setup](#setup)
- [Usage](#usage)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Development](#development)
- [License](#license)

---

## What It Does

Remembrance solves **context loss** — the #1 problem with AI agents. Every session, agents start from zero. They forget decisions, people, project state, and hard-won insights. Remembrance fixes this with:

1. **Intelligent capture** — A gate classifier decides *whether* to store a memory and *how important* it is (SKIP → COLD → ACTIVE → PERSIST)
2. **Knowledge graph** — Entities and relationships auto-detected on every write. No manual tagging.
3. **Compiled truth** — The current synthesis of what's known, with append-only timeline evidence underneath
4. **Dream cycle** — Automated maintenance: prune orphans, rewrite truth, detect patterns, purge stale data
5. **Hybrid search** — FTS5 + vector + graph + RRF fusion. +31 P@5 over vector-only (gbrain benchmark)
6. **Universal access** — MCP, REST API, and CLI. Any agent, any platform, any language.

All LLM calls use **Ollama** (Nemotron-3-nano for extraction, nomic-embed-text for embeddings). **No API keys required.**

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Access Layer                                │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                  │
│  │  MCP      │    │  REST    │    │  CLI     │                  │
│  │  Server   │    │  API     │    │          │                  │
│  │ (stdio)   │    │ (:8788)  │    │          │                  │
│  └────┬──────┘    └────┬─────┘    └────┬─────┘                  │
│       │                │               │                        │
│       └────────────────┼───────────────┘                        │
│                        │                                        │
│                   ┌─────▼─────┐                                  │
│                   │ Pipeline  │  ← capture, search, stats,       │
│                   │           │    consolidate, context_build    │
│                   └─────┬─────┘                                  │
│                         │                                        │
│  ┌──────────────────────┼──────────────────────────┐            │
│  │              Processing Pipeline                 │            │
│  │                                                  │            │
│  │   ┌───────┐    ┌─────────┐    ┌───────┐         │            │
│  │   │ Gate  │───▶│ Extract │───▶│ Store │         │            │
│  │   │(class)│    │(struct) │    │(SQLite)│         │            │
│  │   └───────┘    └─────────┘    └───────┘         │            │
│  │       │              │            │               │            │
│  │       ▼              ▼            ▼               │            │
│  │  ┌─────────┐  ┌──────────┐  ┌──────────┐        │            │
│  │  │ Entity  │  │  Graph   │  │ Hybrid   │        │            │
│  │  │Detector │  │ Wiring   │  │ Search   │        │            │
│  │  └────┬────┘  └────┬─────┘  └────┬─────┘        │            │
│  │       │            │             │               │            │
│  └───────┼────────────┼─────────────┼───────────────┘            │
│          │            │             │                            │
│  ┌───────▼────────────▼─────────────▼───────────────┐            │
│  │              Storage Layer (SQLite)               │            │
│  │                                                   │            │
│  │  ┌──────────┐ ┌────────┐ ┌──────────┐ ┌───────┐  │            │
│  │  │ memories │ │entities│ │  edges   │ │ facts │  │            │
│  │  │ + FTS5   │ │+aliases│ │ typed    │ │temporal│  │            │
│  │  │ + vectors│ │        │ │          │ │version │  │            │
│  │  └──────────┘ └────────┘ └──────────┘ └───────┘  │            │
│  │                                                   │            │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐         │            │
│  │  │memory_   │ │dream_log │ │brain/    │         │            │
│  │  │entities │ │          │ │(markdown)│         │            │
│  │  └──────────┘ └──────────┘ └──────────┘         │            │
│  └───────────────────────────────────────────────────┘            │
│                                                                   │
│  ┌──────────────────────────────────────────────────┐             │
│  │              Dream Cycle (Maintenance)            │             │
│  │                                                   │             │
│  │  entity_sweep → backlink_audit → truth_rewrite → │             │
│  │  pattern_detect → orphan_detect → embed_stale →  │             │
│  │  purge                                           │             │
│  └──────────────────────────────────────────────────┘             │
└───────────────────────────────────────────────────────────────────┘
```

### Data Flow

**Capture** (write path):
```
Text → Gate (SKIP/COLD/ACTIVE/PERSIST?) → Extract (structured) → Store (SQLite)
                                                            ↓
                                                      Entity Detection → Graph Wiring
                                                            ↓
                                                      Compiled Truth Update
```

**Search** (read path):
```
Query → FTS5 (keyword) + Vector (semantic) + Graph (context) → RRF Fusion → Ranked Results
```

**Dream** (maintenance path):
```
Trigger (cron/event/manual) → entity_sweep → backlink_audit → truth_rewrite → 
pattern_detect → orphan_detect → embed_stale → purge
```

---

## Core Packages

### `gate/` — Intelligent Gate Classification

Decides *whether* to store a memory and *how important* it is.

| Gate Class | Meaning | TTL | Example |
|-----------|---------|-----|---------|
| SKIP | Don't store | — | "hello", "thanks", "ok" |
| COLD | Low value | 1 day | Casual mentions, passing references |
| ACTIVE | Current context | 30 days | Project state, active tasks |
| PERSIST | Important forever | None | Decisions, people, architecture choices |

**Backends** (pluggable via `register_gate_backend()`):

| Backend | Model | Speed | Quality |
|---------|-------|-------|---------|
| `dilbert` | Fine-tuned DistilBERT (0.929 confidence) | <100ms | Best |
| `ollama` | Nemotron-3-nano via Ollama | ~2s | Good |
| `heuristic` | Regex + keyword rules | <1ms | Fallback |

The `GateFallbackChain` tries backends in order — DilBERT first, then Ollama, then heuristic. If no model is available, heuristic always works.

```python
from rememberance_mcp.gate import MemoryGate
from rememberance_mcp.gate_backends import GateFallbackChain, HeuristicBackend

gate = MemoryGate(backend=GateFallbackChain([HeuristicBackend()]))
decision = gate.classify("Ema decided to use SQLite for storage")
# → GateDecision(decision="PERSIST", confidence=0.85, category="decision")
```

**Files:** `gate/gate.py` (classifier), `gate/ollama.py` (Ollama backend), `gate_backends.py` (registry + fallback chain)

---

### `extract/` — Structured Extraction

Takes raw text and extracts structured data: summary, category, tier, key topics, entities.

Uses Nemotron-3-nano via Ollama for LLM-based extraction. Falls back to heuristic extraction when Ollama is unavailable.

```python
from rememberance_mcp.extract import Extractor

extractor = Extractor()
result = extractor.extract("Ema decided Prism stays domain-agnostic for V2")
# → ExtractedMemory(summary="Ema decided Prism stays domain-agnostic", 
#                    category="decision", tier="persist", key_topics=["Prism", "domain-agnostic"])
```

**Files:** `extract/extract.py`

---

### `store/` — Persistent Storage

SQLite-based storage with FTS5 full-text search, vector embeddings, and tier-based TTL.

| Module | Table(s) | Purpose |
|--------|----------|---------|
| `store.py` | `memories` | Core memory storage with TTL, consolidation, embedding BLOB |
| `memory.py` | `memories_fts` (virtual), `dream_log` | V2 extensions: FTS5 search, compiled truth, timeline, dream log |
| `edges.py` | `entities`, `edges`, `memory_entities`, `entity_aliases` | Knowledge graph: entities, typed edges, O(1) alias lookup |
| `facts.py` | `facts` | Temporal fact store with versioning, contradiction detection, provenance |
| `markdown.py` | — | Brain repo sync: SQLite ↔ `~/.remembrance/brain/` markdown export/import |

**Key design decisions:**
- **WAL mode** enabled on all stores for concurrent read/write
- **O(1) alias resolution** via `entity_aliases` table (replaces O(n) JSON scan)
- **FTS5 rank scoring** uses `1/(1+abs(rank))` for proper 0-1 range
- **Parameterized queries** throughout — no SQL injection vectors
- **REST API defaults to 127.0.0.1** — no accidental 0.0.0.0 binding

```python
from rememberance_mcp.store.edges import EntityStore
from rememberance_mcp.store.facts import FactStore

entities = EntityStore(db_path)
entity = entities.create_entity("Prism", entity_type="project", aliases=["AI-Hedge-Prism"])
# → Entity(id="prism", name="Prism", type="project", ...)

facts = FactStore(db_path)
fact = facts.assert_fact("Prism uses event-driven architecture", source="design-doc", confidence=0.95)
# → Fact with temporal versioning and provenance
```

---

### `graph/` — Knowledge Graph

Auto-wires entities and relationships on every capture. Zero-LLM entity detection using regex patterns.

| Module | Purpose |
|--------|---------|
| `entity.py` | EntityDetector — regex-based extraction, known entity bootstrap, edge type inference |
| `edges.py` | GraphWiring — creates typed edges (mentions, decided_about, works_on, related_to, depends_on) |
| `traversal.py` | GraphTraversal — N-hop BFS, shortest path, context builder |

**Entity types:** person, project, concept, tool, decision, preference

**Edge types:** mentions, decided_about, works_on, related_to, depends_on

**Scale safety:** Graph wiring caps at `mention_limit=10` detected entities to prevent O(n²) edge explosion.

```python
from rememberance_mcp.graph.entity import EntityDetector
from rememberance_mcp.graph.edges import GraphWiring

detector = EntityDetector()
entities = detector.detect("Ema decided Prism stays domain-agnostic")
# → [DetectedEntity(text="Ema", type="person"), DetectedEntity(text="Prism", type="project")]

wiring = GraphWiring(entity_store=entities, edge_store=edges)
result = wiring.wire("Ema decided Prism stays domain-agnostic", entities)
# → Creates/updates entities + typed edges in the graph
```

---

### `search/` — Hybrid Search

Multi-strategy search with reciprocal rank fusion (RRF) for optimal relevance.

```
Query ──┬── FTS5 (keyword) ─────────┐
        ├── Vector (semantic) ───────┤
        └── Graph (context augment) ──┤
                                        ↓
                                   RRF Fusion
                                        ↓
                               Tier Boost (1.5x persist)
                                        ↓
                                   Ranked Results
```

| Strategy | Method | When |
|----------|--------|------|
| FTS5 | Full-text search with BM25 ranking | Always (fast, precise) |
| Vector | Cosine similarity with nomic-embed-text | When embeddings available |
| Graph | Context-augmented results from related entities | When entities exist |

**RRF formula:** `score = Σ(1 / (k + rank_i)) × tier_boost` where `k=60` and tier boosts are PERSIST=1.5, ACTIVE=1.0, COLD=0.5.

**Batch entity lookup:** Single `WHERE IN` query instead of N+1 for search results.

```python
from rememberance_mcp.search.hybrid import HybridSearch

search = HybridSearch(memory_store, entity_store, edge_store)
results = search.search("Prism architecture decisions", mode="balanced", limit=10)
# → Ranked results with entities, tier, and source attribution
```

---

### `dream/` — Dream Cycle

Automated memory maintenance. Runs in 7 phases:

| Phase | What | LLM Required? |
|-------|------|---------------|
| `entity_sweep` | Re-scan memories for missed entities | No |
| `backlink_audit` | Verify all edges point to valid entities | No |
| `truth_rewrite` | Recompile truth from timeline evidence | Yes (Nemotron) |
| `pattern_detect` | Find recurring patterns across memories | Yes (Nemotron) |
| `orphan_detect` | Find entities with no edges or memories | No |
| `embed_stale` | Re-embed memories with missing vectors | Yes (Ollama) |
| `purge` | Delete expired COLD/ACTIVE memories past TTL | No |

Phases that need LLM gracefully degrade when Ollama is unavailable. Non-LLM phases always work.

**Triggers:** Nightly cron, event-driven (freshness), or manual (`POST /dream`).

```python
from rememberance_mcp.dream.cycle import DreamCycle

dream = DreamCycle(memory_store, entity_store, edge_store, fact_store)
report = dream.run(phases=["orphan_detect", "entity_sweep"])
# → {"phases_run": 2, "orphans_found": 3, "entities_created": 5, ...}
```

---

### `api/` — REST API

10 endpoints on port 8788 (configurable), bound to 127.0.0.1 by default.

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/health` | Health check + version |
| `GET` | `/stats` | Memory, entity, edge counts |
| `POST` | `/capture` | Gate → Extract → Store pipeline |
| `GET` | `/search` | Hybrid search (keyword/balanced/semantic) |
| `GET` | `/entity/{name}` | Get entity with compiled truth |
| `GET` | `/entity/{name}/neighbors` | Get entity's graph neighbors |
| `POST` | `/entity` | Create entity manually |
| `GET` | `/context/build` | Build context for a task |
| `GET` | `/graph/query` | Graph traversal (N-hop, shortest path) |
| `POST` | `/dream` | Run dream cycle (optional phases) |

All endpoints return JSON. Capture requires `{"text": "...", "source": "..."}`. Search accepts `?q=query&mode=keyword&limit=10`.

---

### Pipeline — `pipeline.py`

Orchestrates the full capture/search/dream flow.

```python
from rememberance_mcp import MemoryPipeline

pipeline = MemoryPipeline()

# Capture (gate → extract → entity detect → graph wire → store)
result = pipeline.capture("Ema decided Prism stays domain-agnostic", source="design-doc")
# → {"id": "mem_abc123", "decision": "PERSIST", "category": "decision", ...}

# Search (FTS5 + vector + graph → RRF fusion)
results = pipeline.search("architecture decisions", mode="balanced")

# Build context for a task
context = pipeline.build_context(task="implement vector search", project="prism")

# Stats
stats = pipeline.stats()
# → {"memories": 42, "entities": 15, "edges": 38, "facts": 7}

# Dream cycle
report = pipeline.dream(phases=["orphan_detect", "entity_sweep"])
```

---

## Setup

### Prerequisites

- **Python 3.10+**
- **Ollama** running locally (for extraction + embeddings) — [ollama.com](https://ollama.com)
- **No API keys required** — all LLM calls use local Ollama

### Install

```bash
# Clone
git clone https://github.com/emaharmony/rememberance-mcp.git
cd rememberance-mcp

# Install (core only — no gate model dependency)
pip install -e .

# Or with uv (recommended)
uv pip install -e .

# Install with DilBERT gate model support
pip install -e ".[gate]"

# Install with development dependencies
pip install -e ".[dev]"
```

### Ollama Models

Pull the required models:

```bash
# Extraction model (structured data from text)
ollama pull nemotron-3-nano:4b

# Embedding model (vector search)
ollama pull nomic-embed-text

# Optional: Gate model (if using DilBERT backend)
# Place trained model at ~/.remembrance/models/distilbert-memory-gate/
```

Remembrance works without Ollama too — it falls back to heuristic gate classification and keyword-only search. No crashes, just less intelligence.

### Run Tests

```bash
# All tests (133 tests, ~2 min)
pytest

# Specific test file
pytest tests/test_hybrid_search.py -v

# Skip slow integration tests
pytest -m "not integration"
```

---

## Usage

### As MCP Server (stdio) — Claude Desktop, Cursor, etc.

Add to your MCP client configuration:

```json
{
  "mcpServers": {
    "remembrance": {
      "command": "python",
      "args": ["-m", "rememberance_mcp"],
      "env": {
        "REMEMBRANCE_HOME": "~/.remembrance"
      }
    }
  }
}
```

**MCP Tools Provided:**

| Tool | Description |
|------|-------------|
| `memory_capture` | Gate → Extract → Store a piece of text |
| `memory_search` | Search stored memories by keyword and filters |
| `memory_consolidate` | Run decay/promotion cycle |
| `memory_get` | Get a specific memory by ID |
| `memory_delete` | Delete a specific memory by ID |
| `memory_graph_query` | Query the knowledge graph (N-hop, shortest path) |
| `memory_entity_get` | Get entity with compiled truth |
| `memory_entity_search` | Search entities by name/type |
| `memory_dream` | Run dream cycle (requires approval) |
| `memory_context_build` | Build context for a task/project |
| `memory_stats` | Get memory statistics |

### As REST API

```bash
# Start server (default: 127.0.0.1:8788)
python -m rememberance_mcp.api

# Custom host/port
python -m rememberance_mcp.api --host 0.0.0.0 --port 9000
```

```bash
# Capture a memory
curl -X POST http://localhost:8788/capture \
  -H "Content-Type: application/json" \
  -d '{"text": "Ema decided to use SQLite for storage", "source": "design-doc"}'

# Search
curl "http://localhost:8788/search?q=storage+decisions&mode=balanced"

# Build context
curl "http://localhost:8788/context/build?task=implement+search&project=prism"

# Run dream cycle
curl -X POST http://localhost:8788/dream \
  -H "Content-Type: application/json" \
  -d '{"phases": ["orphan_detect", "entity_sweep"]}'
```

### As Python Library

```python
from rememberance_mcp import MemoryPipeline

pipeline = MemoryPipeline()

# Capture (runs gate → extract → entity detect → graph wire → store)
result = pipeline.capture("Ema finished the SelfQuest audit", source="discord")
# → {"id": "mem_abc123", "decision": "PERSIST", "category": "project", ...}

# Search (FTS5 + vector + graph → RRF fusion)
results = pipeline.search("SelfQuest PR status", limit=5)

# Build context for a task
context = pipeline.build_context(task="implement vector search", project="prism")

# Get stats
stats = pipeline.stats()
# → {"memories": 42, "entities": 15, "edges": 38, "facts": 7}
```

---

## Configuration

All configuration via environment variables or `Settings` dataclass:

| Variable | Default | Description |
|----------|---------|-------------|
| `REMEMBRANCE_HOME` | `~/.remembrance` | Base directory for database, models, brain repo |
| `REMEMBRANCE_DB_PATH` | `$HOME/memory.db` | SQLite database path |
| `REMEMBRANCE_GATE_MODEL_PATH` | `$HOME/models/distilbert-memory-gate` | DilBERT model path |
| `REMEMBRANCE_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API URL |
| `REMEMBRANCE_EXTRACT_MODEL` | `nemotron-3-nano:4b` | Extraction model name |
| `REMEMBRANCE_SEARCH_MODEL` | `all-MiniLM-L6-v2` | Embedding model name |
| `REMEMBRANCE_REST_HOST` | `127.0.0.1` | REST API bind address |
| `REMEMBRANCE_REST_PORT` | `8788` | REST API port |

### Data Directory Structure

```
~/.remembrance/
├── memory.db              # SQLite database (all V2 tables + FTS5)
├── models/
│   └── distilbert-memory-gate/   # DilBERT gate model
└── brain/                  # Markdown brain repo (synced from DB)
    ├── entities/
    │   ├── ema.md
    │   └── prism.md
    ├── facts/
    │   └── prism-architecture.md
    └── memories/
        └── 2026-05-19.md
```

---

## API Reference

### `MemoryPipeline`

| Method | Description |
|--------|-------------|
| `capture(text, source, category=None)` | Full pipeline: gate → extract → entity detect → graph wire → store |
| `search(query, mode="keyword", limit=10, tier=None)` | Hybrid search with RRF fusion |
| `build_context(task, project=None, agent=None)` | Build relevant context for a task |
| `consolidate()` | Run TTL-based decay/promotion |
| `dream(phases=None, dry_run=False)` | Run dream cycle maintenance |
| `stats()` | Memory, entity, edge, fact counts |
| `get(memory_id)` | Get memory by ID |
| `delete(memory_id)` | Delete memory by ID |

### Search Modes

| Mode | Strategy | Use Case |
|------|----------|----------|
| `keyword` | FTS5 + LIKE fallback | Precise term matching |
| `balanced` | FTS5 + vector + graph (RRF) | General purpose (default) |
| `semantic` | Vector similarity + graph | Conceptual/semantic matching |

### Gate Decisions

| Decision | Action | TTL |
|----------|--------|-----|
| `SKIP` | Don't store | — |
| `COLD` | Store, low priority | 1 day |
| `ACTIVE` | Store, medium priority | 30 days |
| `PERSIST` | Store, never expire | ∞ |

### Edge Types

| Type | Meaning | Example |
|------|---------|---------|
| `mentions` | General reference | "Ema mentioned Prism" |
| `decided_about` | Decision involving entity | "Ema decided Prism stays domain-agnostic" |
| `works_on` | Working relationship | "Ema works on Prism" |
| `related_to` | Loose association | "Prism related to Remembrance" |
| `depends_on` | Dependency | "Prism depends on Ollama" |

---

## Development

```bash
# Install with all dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run specific test suites
pytest tests/test_integration.py -v    # Integration tests
pytest tests/test_hybrid_search.py -v   # Search + RRF
pytest tests/test_entity_store.py -v    # Knowledge graph
pytest tests/test_rest_api.py -v        # REST API endpoints

# Format
ruff format .

# Lint
ruff check .
```

### Test Suite

| File | Tests | Coverage |
|------|-------|----------|
| `test_entity_detection.py` | 15 | Entity regex extraction, known entity bootstrap |
| `test_entity_store.py` | 27 | Entity CRUD, alias lookup, graph edges |
| `test_fact_store.py` | 8 | Temporal versioning, contradiction detection |
| `test_hybrid_search.py` | 16 | FTS5, vector, RRF, tier boost |
| `test_integration.py` | 24 | Full pipeline, dream cycle, API |
| `test_markdown_sync.py` | 16 | SQLite ↔ markdown export/import |
| `test_ollama_gate.py` | 10 | Gate classification, fallback chain |
| `test_rest_api.py` | 11 | HTTP endpoints, error handling |
| `test_rrf_edge_cases.py` | 12 | RRF fusion edge cases |
| **Total** | **133** | — |

---

## Design Patterns

| Pattern | Where | Why |
|---------|-------|-----|
| Cascading Classifier | `gate/` | Cheap model filters first, expensive model only when needed |
| Pipeline (Chain of Responsibility) | `pipeline.py` | Each stage testable, swappable, independently fail-safe |
| Repository | `store/` | Storage logic isolated from business logic |
| Strategy | `gate_backends.py` | Swap gate backends (DilBERT, Ollama, heuristic) without changing pipeline |
| Twelve-Factor Config | `config.py` | Environment-based configuration for portability |
| Fallback Chain | `gate_backends.py` | Graceful degradation: DilBERT → Ollama → heuristic |
| Reciprocal Rank Fusion | `search/hybrid.py` | Merge multiple search strategies fairly |
| Compiled Truth + Timeline | `store/memory.py` | Always-current synthesis with append-only evidence |

---

## License

Apache 2.0 — See [LICENSE](LICENSE)