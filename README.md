# Remembrance MCP

Universal memory for AI agents. Remembrance stores useful context in SQLite, links entities into a small knowledge graph, exposes memory through MCP and REST, and can run locally without API keys.

The Python package name is `rememberance-mcp` and the import/module path is `rememberance_mcp`.

## What It Provides

- MCP stdio server for agent clients such as Claude Desktop, Cursor, and other MCP-compatible tools.
- REST API for scripts, local apps, and services.
- Python library entry point through `MemoryPipeline`.
- SQLite memory storage with TTL tiers: `cold`, `active`, and `persist`.
- Gate classification with a default `dilbert -> heuristic` fallback chain. The heuristic backend works with no model downloads.
- Optional local Ollama extraction using `nemotron-3-nano:4b`.
- Entity detection, graph wiring, hybrid keyword/graph search, fact storage, markdown export/import, and dream-cycle maintenance.

## Requirements

- Python 3.10 or newer.
- `pip` or `uv`.
- Optional: Ollama for LLM-based extraction and dream phases.
- Optional: a local DistilBERT gate model if you install the `gate` extra.
- Optional: NATS if you want event-bus capture through `rememberance_mcp.serve`.

No API key is required for the default local/heuristic path. The OpenAI gate backend is available only when `OPENAI_API_KEY` is set and `REMEMBRANCE_GATE_BACKENDS` includes `openai`.

## Quick Start

```bash
git clone https://github.com/emaharmony/rememberance-mcp.git
cd rememberance-mcp

python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip

# REST and Python library usage
pip install -e .

# Add MCP server support
pip install -e ".[mcp]"

# Add test tooling
pip install -e ".[dev]"
```

On Windows PowerShell:

```powershell
git clone https://github.com/emaharmony/rememberance-mcp.git
cd rememberance-mcp

py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[mcp,dev]"
```

If PowerShell blocks virtualenv activation:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Optional Ollama Setup

Remembrance works without Ollama by falling back to heuristic/default extraction. Install Ollama only if you want local model extraction and LLM-backed dream phases.

```bash
ollama pull nemotron-3-nano:4b
```

Current vector query generation is not wired into the default search path, so `nomic-embed-text` is not required for setup.

## Run It

### REST API

Start REST only:

```bash
python -m rememberance_mcp.api
```

Equivalent service command, with NATS disabled:

```bash
python -m rememberance_mcp.serve --no-nats
```

Custom host and port:

```bash
python -m rememberance_mcp.api --host 127.0.0.1 --port 9000
```

Try the API:

```bash
curl http://127.0.0.1:8788/health

curl -X POST http://127.0.0.1:8788/capture \
  -H "Content-Type: application/json" \
  -d '{"text": "Ema decided to keep Remembrance backed by SQLite", "source": "setup-test"}'

curl "http://127.0.0.1:8788/search?q=SQLite&mode=keyword"
```

### MCP Server

Install the MCP extra first:

```bash
pip install -e ".[mcp]"
```

Then run:

```bash
python -m rememberance_mcp
```

Example MCP client configuration:

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

On Windows, use the virtualenv interpreter if your MCP client does not inherit the activated shell:

```json
{
  "mcpServers": {
    "remembrance": {
      "command": "D:\\_projects_\\rememberance-mcp\\.venv\\Scripts\\python.exe",
      "args": ["-m", "rememberance_mcp"],
      "env": {
        "REMEMBRANCE_HOME": "C:\\Users\\you\\.remembrance"
      }
    }
  }
}
```

### Python Library

```python
from rememberance_mcp import MemoryPipeline

pipeline = MemoryPipeline()
result = pipeline.capture(
    "Ema decided to keep Remembrance backed by SQLite",
    source="example",
)
results = pipeline.search("SQLite", limit=5)
stats = pipeline.stats()
```

## Configuration

Environment variables read by the current code:

| Variable | Default | Purpose |
| --- | --- | --- |
| `REMEMBRANCE_HOME` | `~/.remembrance` | Base directory for databases and model files. |
| `REMEMBRANCE_GATE_BACKENDS` | `dilbert,heuristic` | Ordered gate backend list, for example `heuristic` or `openai,heuristic`. |
| `OPENAI_API_KEY` | unset | Enables the optional OpenAI gate backend when requested. |

Other settings are available through `rememberance_mcp.config.Settings`:

| Setting | Default |
| --- | --- |
| `DB_PATH` | `<REMEMBRANCE_HOME>/memory.db` |
| `GATE_MODEL_PATH` | `<REMEMBRANCE_HOME>/models/distilbert-memory-gate` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` |
| `EXTRACT_MODEL` | `nemotron-3-nano:4b` |
| `SEARCH_MODEL` | `all-MiniLM-L6-v2` |
| `COLD_TTL` | `86400` seconds |
| `ACTIVE_TTL` | `2592000` seconds |
| `PERSIST_TTL` | `-1`, meaning no expiry |

REST host, REST port, NATS URL, and NATS enablement are CLI arguments on `rememberance_mcp.api` or `rememberance_mcp.serve`; they are not environment variables in the current implementation.

Default data layout:

```text
~/.remembrance/
  memory.db
  metrics.db
  entities.db
  models/
    distilbert-memory-gate/
```

## REST API

Implemented endpoints:

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Health check and version. |
| `GET` | `/stats` | Memory, entity, fact, and V2 store stats. |
| `POST` | `/capture` | Capture text through gate, extraction, storage, and graph wiring. |
| `GET` | `/search?q=...&mode=...` | Search memories. Modes: `keyword`, `balanced`, `vector`, `deep`. |
| `GET` | `/memory/{id}` | Fetch one memory and linked entities. |
| `GET` | `/entity/{slug}` | Fetch one entity and edges. |
| `GET` | `/graph/{slug}?depth=1` | Traverse the graph from one entity. |
| `GET` | `/context/build?task=...` | Build context for a task. |
| `POST` | `/dream` | Run dream-cycle phases. |

Example dream request:

```bash
curl -X POST http://127.0.0.1:8788/dream \
  -H "Content-Type: application/json" \
  -d '{"phases": ["orphan_detect"], "dry_run": false}'
```

## MCP Tools

Current MCP tools:

| Tool | Description |
| --- | --- |
| `memory_capture` | Capture text as a memory. |
| `memory_search` | Search stored memories by keyword and filters. |
| `memory_consolidate` | Run TTL cleanup and promotion/demotion. |
| `memory_get` | Fetch one memory by ID. |
| `memory_delete` | Delete one memory by ID. |
| `memory_metrics` | Inspect gate backend metrics. |
| `memory_graph_query` | Query graph neighbors from an entity. |
| `memory_entity_get` | Fetch one entity. |
| `memory_entity_search` | Search entities. |
| `memory_dream` | Run dream-cycle maintenance. |
| `memory_context_build` | Build task context from search and graph data. |

## Optional Features

### NATS Subscriber

Install the extra:

```bash
pip install -e ".[nats]"
```

Run the combined REST service and NATS subscriber:

```bash
python -m rememberance_mcp.serve --nats nats://localhost:4222
```

Use REST only:

```bash
python -m rememberance_mcp.serve --no-nats
```

### DilBert v3 Gate

The DilBert gate is a fine-tuned DistilBertForSequenceClassification model that classifies text into four memory tiers: `skip`, `cold`, `active`, and `persist`. It runs locally with no API keys required.

**Model stats:** 90.1% accuracy, macro F1 0.88, PERSIST recall 0.91.

#### Install gate dependencies

```bash
pip install -e ".[gate]"
```

#### Download the model

Use the included download script:

```bash
bash scripts/download-dilbert.sh
```

Or download to a custom path:

```bash
bash scripts/download-dilbert.sh /path/to/models/distilbert-memory-gate
```

The script downloads four files (~256MB total) to `~/.remembrance/models/distilbert-memory-gate/`:

```text
config.json           — model architecture config (1KB)
tokenizer.json        — tokenizer vocabulary (696KB)
tokenizer_config.json — tokenizer settings (1KB)
model.safetensors     — fine-tuned weights (255MB)
```

**Manual download:** If the script fails (e.g., unstable connection on the 255MB model file), download directly from the [GitHub release](https://github.com/emaharmony/rememberance-mcp/releases/tag/v3.0-dilbert-gate) and place the files in `~/.remembrance/models/distilbert-memory-gate/`.

#### Verify installation

```bash
python -c "
from transformers import DistilBertForSequenceClassification, DistilBertTokenizer
model = DistilBertForSequenceClassification.from_pretrained('~/.remembrance/models/distilbert-memory-gate')
tokenizer = DistilBertTokenizer.from_pretrained('~/.remembrance/models/distilbert-memory-gate')
print('Model loaded successfully:', model.config.id2label)
"
```

Expected output:

```text
Model loaded successfully: {0: 'skip', 1: 'cold', 2: 'active', 3: 'persist'}
```

Without the model, the default gate chain (`dilbert,heuristic`) falls back to the heuristic backend automatically.

### OpenAI Gate

```bash
export OPENAI_API_KEY="..."
export REMEMBRANCE_GATE_BACKENDS="openai,heuristic"
```

PowerShell:

```powershell
$env:OPENAI_API_KEY="..."
$env:REMEMBRANCE_GATE_BACKENDS="openai,heuristic"
```

## Development

```bash
pip install -e ".[mcp,nats,dev]"
python -m pytest
```

Useful targeted test commands:

```bash
python -m pytest tests/test_rest_api.py -v
python -m pytest tests/test_integration.py -v
python -m pytest tests/test_hybrid_search.py -v
```

The repository currently contains tests for entity detection and storage, facts, hybrid search, integration behavior, markdown sync, Ollama gate parsing, REST API behavior, and RRF edge cases.

## Current Limitations

- Balanced search currently uses FTS5/LIKE plus graph augmentation. Query embedding generation is not wired into the default `search()` path yet.
- The package has optional MCP, NATS, and gate-model dependencies. Install the matching extra before using those features.
- Only `REMEMBRANCE_HOME`, `REMEMBRANCE_GATE_BACKENDS`, and `OPENAI_API_KEY` are read from the environment in the current code.

## License

Apache-2.0. See [LICENSE](LICENSE).
