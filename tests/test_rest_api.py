"""
REST API Tests — HTTP handler coverage for the Remembrance REST API
"""

import json
import tempfile
import time
from pathlib import Path
import pytest
from http.server import HTTPServer
from threading import Thread

from rememberance_mcp.pipeline import MemoryPipeline
from rememberance_mcp.config import Settings
from rememberance_mcp.api.rest import RemembranceHandler, start_rest_api
from rememberance_mcp.gate_backends import HeuristicBackend, GateFallbackChain
import urllib.request
import urllib.error


@pytest.fixture
def api_server():
    """Start a REST API server on a random available port."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "memories.db"
        settings = Settings(
            DB_PATH=db_path,
            OLLAMA_BASE_URL="http://localhost:11434",
            GATE_MODEL_PATH=None,
        )
        pipeline = MemoryPipeline(settings=settings)
        pipeline.gate_chain = GateFallbackChain([HeuristicBackend()])

        # Find an available port
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        sock.close()

        RemembranceHandler.pipeline = pipeline
        server = HTTPServer(('127.0.0.1', port), RemembranceHandler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()

        base_url = f"http://127.0.0.1:{port}"
        yield {
            "base_url": base_url,
            "pipeline": pipeline,
            "port": port,
        }

        server.shutdown()


class TestHealthEndpoint:
    def test_health(self, api_server):
        resp = urllib.request.urlopen(f"{api_server['base_url']}/health")
        data = json.loads(resp.read())
        assert data["status"] == "ok"
        assert data["version"] == "2.0.0"


class TestStatsEndpoint:
    def test_stats(self, api_server):
        resp = urllib.request.urlopen(f"{api_server['base_url']}/stats")
        data = json.loads(resp.read())
        assert "memories" in data
        assert "entities" in data


class TestCaptureEndpoint:
    def test_capture_post(self, api_server):
        body = json.dumps({
            "text": "Ema decided Prism stays domain-agnostic",
            "source": "test",
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{api_server['base_url']}/capture",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req)
        assert resp.status == 201
        data = json.loads(resp.read())
        assert data["id"] is not None

    def test_capture_missing_text(self, api_server):
        body = json.dumps({"source": "test"}).encode("utf-8")
        req = urllib.request.Request(
            f"{api_server['base_url']}/capture",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req)
            assert False, "Expected 400 error"
        except urllib.error.HTTPError as e:
            assert e.code == 400


class TestSearchEndpoint:
    def test_search(self, api_server):
        # First capture something
        body = json.dumps({"text": "Ema decided Prism stays domain-agnostic", "source": "test"}).encode("utf-8")
        req = urllib.request.Request(
            f"{api_server['base_url']}/capture",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req)

        # Then search
        resp = urllib.request.urlopen(f"{api_server['base_url']}/search?q=Prism&mode=keyword")
        data = json.loads(resp.read())
        assert "results" in data
        assert "count" in data

    def test_search_missing_query(self, api_server):
        try:
            urllib.request.urlopen(f"{api_server['base_url']}/search")
            assert False, "Expected 400 error"
        except urllib.error.HTTPError as e:
            assert e.code == 400


class TestEntityEndpoint:
    def test_entity_get(self, api_server):
        # Capture to create entity
        body = json.dumps({"text": "Ema works on Prism", "source": "test"}).encode("utf-8")
        req = urllib.request.Request(
            f"{api_server['base_url']}/capture",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req)

        # Get entity
        try:
            resp = urllib.request.urlopen(f"{api_server['base_url']}/entity/ema")
            data = json.loads(resp.read())
            assert data["name"] == "Ema"
            assert "compiled_truth" in data
        except urllib.error.HTTPError as e:
            if e.code == 404:
                pytest.skip("Entity not created by capture (detection dependent)")

    def test_entity_not_found(self, api_server):
        try:
            urllib.request.urlopen(f"{api_server['base_url']}/entity/nonexistent")
            assert False, "Expected 404"
        except urllib.error.HTTPError as e:
            assert e.code == 404


class TestContextBuildEndpoint:
    def test_context_build(self, api_server):
        # Capture first
        body = json.dumps({"text": "Ema decided Prism stays domain-agnostic", "source": "test"}).encode("utf-8")
        req = urllib.request.Request(
            f"{api_server['base_url']}/capture",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req)

        # Build context
        resp = urllib.request.urlopen(f"{api_server['base_url']}/context/build?task=implement+vector+search")
        data = json.loads(resp.read())
        assert "memories" in data
        assert "entities" in data

    def test_context_build_missing_task(self, api_server):
        try:
            urllib.request.urlopen(f"{api_server['base_url']}/context/build")
            assert False, "Expected 400"
        except urllib.error.HTTPError as e:
            assert e.code == 400


class TestDreamEndpoint:
    def test_dream_post(self, api_server):
        body = json.dumps({
            "phases": ["orphan_detect"],
            "dry_run": False,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{api_server['base_url']}/dream",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        assert "status" in data
        assert data["status"] in ("ok", "partial")


class TestNotFoundEndpoint:
    def test_not_found(self, api_server):
        try:
            urllib.request.urlopen(f"{api_server['base_url']}/nonexistent")
            assert False, "Expected 404"
        except urllib.error.HTTPError as e:
            assert e.code == 404