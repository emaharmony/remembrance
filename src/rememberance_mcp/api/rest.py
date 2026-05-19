"""
REST API — HTTP Interface for Remembrance

PATTERN: REST API (Thin HTTP Wrapper)
========================================

This module provides a REST API alongside the MCP protocol.
It wraps the same Pipeline methods as the MCP server but
exposes them as HTTP endpoints.

WHY BOTH MCP AND REST?
- MCP: For AI agents that speak MCP (Claude, Cursor, etc.)
- REST: For web apps, CLIs, scripts, and Prism's Go client
- Some consumers prefer simple HTTP over MCP's JSON-RPC

ENDPOINTS:
  POST /capture              → gate → extract → graph → enrich → store
  GET  /search?q=&mode=      → hybrid search
  GET  /memory/:id           → memory + entities + edges
  GET  /entity/:slug         → compiled truth + timeline + edges
  GET  /graph/:slug?depth=N  → N-hop graph traversal
  POST /dream                → trigger dream cycle
  GET  /context/build?task=&project=&agent=  → context building
  GET  /health               → health check
  GET  /stats                → subsystem stats
"""

from __future__ import annotations

import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional

from rememberance_mcp.pipeline import MemoryPipeline

logger = logging.getLogger(__name__)


class RemembranceHandler(BaseHTTPRequestHandler):
    """
    HTTP request handler for the Remembrance REST API.

    All responses are JSON. Errors return {"error": "message"}.
    """

    pipeline: MemoryPipeline = None  # Set before server starts

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        try:
            if path == "/health":
                self._json_response({"status": "ok", "version": "2.0.0"})

            elif path == "/stats":
                stats = self.pipeline.stats()
                self._json_response(stats)

            elif path == "/search":
                query = params.get("q", [""])[0]
                mode = params.get("mode", ["balanced"])[0]
                category = params.get("category", [None])[0]
                tier = params.get("tier", [None])[0]
                limit = int(params.get("limit", ["10"])[0])

                if not query:
                    self._json_response({"error": "Missing query parameter 'q'"}, status=400)
                    return

                results = self.pipeline.hybrid_search.search(
                    query, mode=mode, category=category, tier=tier, limit=limit
                )
                self._json_response({"results": results, "count": len(results)})

            elif path.startswith("/memory/"):
                mem_id = path.split("/")[-1]
                memory = self.pipeline.get(mem_id)
                if not memory:
                    self._json_response({"error": f"Memory {mem_id} not found"}, status=404)
                    return
                # Also include entities
                entities = self.pipeline.entity_store.get_memory_entities(mem_id)
                memory["entities"] = entities
                self._json_response(memory)

            elif path.startswith("/entity/"):
                slug = path.split("/")[-1]
                entity = self.pipeline.entity_store.find_entity(slug)
                if not entity:
                    self._json_response({"error": f"Entity '{slug}' not found"}, status=404)
                    return
                # Include edges
                edges = self.pipeline.entity_store.get_edges(entity["id"])
                entity["edges"] = edges
                self._json_response(entity)

            elif path.startswith("/graph/"):
                slug = path.split("/")[-1]
                depth = int(params.get("depth", ["1"])[0])
                edge_types = params.get("edge_types", None)
                if edge_types:
                    edge_types = edge_types[0].split(",")

                result = self.pipeline.graph_query(slug, depth=depth, edge_types=edge_types)
                if "error" in result:
                    self._json_response(result, status=404)
                    return
                self._json_response(result)

            elif path == "/context/build":
                task = params.get("task", [""])[0]
                project = params.get("project", [None])[0]
                agent = params.get("agent", [None])[0]
                limit = int(params.get("limit", ["10"])[0])

                if not task:
                    self._json_response({"error": "Missing query parameter 'task'"}, status=400)
                    return

                context = self.pipeline.build_context(
                    task=task, project=project, agent=agent, limit=limit
                )
                self._json_response(context)

            else:
                self._json_response({"error": "Not found"}, status=404)

        except Exception as e:
            logger.error(f"GET {path} error: {e}", exc_info=True)
            self._json_response({"error": str(e)}, status=500)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        try:
            body = self._read_body()

            if path == "/capture":
                text = body.get("text", "")
                source = body.get("source", "api")
                category = body.get("category")
                tier = body.get("tier")

                if not text:
                    self._json_response({"error": "Missing 'text' field"}, status=400)
                    return

                result = self.pipeline.capture(
                    text=text, source=source, category=category, tier=tier
                )
                self._json_response(result, status=201)

            elif path == "/dream":
                phases = body.get("phases")
                dry_run = body.get("dry_run", False)
                result = self.pipeline.dream(phases=phases, dry_run=dry_run)
                self._json_response(result)

            else:
                self._json_response({"error": "Not found"}, status=404)

        except Exception as e:
            logger.error(f"POST {path} error: {e}", exc_info=True)
            self._json_response({"error": str(e)}, status=500)

    # ── Helpers ────────────────────────────────────────────────

    def _json_response(self, data: dict, status: int = 200):
        """Send a JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2, default=str).encode("utf-8"))

    def _read_body(self) -> dict:
        """Read and parse the request body as JSON."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        body = self.rfile.read(content_length)
        return json.loads(body.decode("utf-8"))

    def log_message(self, format, *args):
        """Override to use our logger instead of stderr."""
        logger.debug(f"REST API: {format % args}")


def start_rest_api(pipeline: MemoryPipeline, host: str = "127.0.0.1",
                   port: int = 8788):
    """
    Start the REST API server.

    Args:
        pipeline: MemoryPipeline instance
        host: Bind address (default: all interfaces)
        port: Port number (default: 8788, matching Prism's /context/build convention)
    """
    RemembranceHandler.pipeline = pipeline
    server = HTTPServer((host, port), RemembranceHandler)
    logger.info(f"REST API starting on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("REST API shutting down")
        server.server_close()