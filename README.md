# Memory MCP Server

A universal memory system for AI agents. Works with Claude Desktop, Cursor, OpenAI agents, OpenClaw, and any MCP-compatible environment.

## Architecture

```
AI Agent (Claude, GPT, OpenClaw, etc.)
    ↕  JSON-RPC (MCP protocol)
MCP Server (Python)
    ↕  3-layer pipeline
┌─────────────────────────────────┐
│  GATE    → DilBERT 4-class      │  "Should I save this?"  (<100ms)
│  EXTRACT → Nemotron structured  │  "What's the data?"      (~2s)
│  STORE   → SQLite with TTL      │  "Save it with metadata"  (<1ms)
└─────────────────────────────────┘
```

### Gate Classes (Cascading Classifier)

| Class | Meaning | TTL | Example |
|-------|---------|-----|---------|
| SKIP | Don't store | — | "hello", "thanks" |
| COLD | Low value | 1 day | Casual mentions |
| ACTIVE | Current context | 30 days | Project state, tasks |
| PERSIST | Important forever | None | Decisions, people, architecture |

## Setup

```bash
# Clone
git clone https://github.com/emaharmony/memory-mcp-server.git
cd memory-mcp-server

# Install
pip install -e .

# Or with uv (recommended)
uv pip install -e .
```

### Model Setup

The DilBERT gate model needs to be available at `~/.memory-mcp/models/distilbert-memory-gate/`.
Copy your trained model there, or train one using `scripts/train-gate.py`.

## Usage

### As MCP Server (stdio)

Add to your MCP client config (e.g., Claude Desktop):

```json
{
  "mcpServers": {
    "memory": {
      "command": "python",
      "args": ["-m", "memory_mcp_server"],
      "env": {
        "MEMORY_DB_PATH": "~/.memory-mcp/memory.db",
        "GATE_MODEL_PATH": "~/.memory-mcp/models/distilbert-memory-gate"
      }
    }
  }
}
```

### As Python Library

```python
from memory_mcp_server import MemoryPipeline

pipeline = MemoryPipeline()

# Capture a memory
result = pipeline.capture("Ema finished the SelfQuest audit", source="discord")

# Search memories
results = pipeline.search("SelfQuest PR status", limit=5)

# Consolidate (decay + promote)
pipeline.consolidate()
```

### As REST API

```bash
python -m memory_mcp_server.api --port 8080

# Then:
curl -X POST http://localhost:8080/capture -d '{"text": "...", "source": "discord"}'
curl http://localhost:8080/search?q=SelfQuest&limit=5
```

## Tools Provided (MCP)

| Tool | Description |
|------|-------------|
| `memory_capture` | Gate → Extract → Store a piece of text |
| `memory_search` | Semantic search across stored memories |
| `memory_consolidate` | Run decay/promotion cycle |
| `memory_get` | Get a specific memory by ID |
| `memory_list` | List memories by category/tier |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format
ruff format .
```

## License

MIT