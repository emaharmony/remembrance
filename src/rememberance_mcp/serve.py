"""
Serve command — Start Remembrance REST API + NATS subscriber.

PATTERN: Service Runner (Process Manager)
============================================

This starts Remembrance as a long-running service with:
  1. REST API on port 8788 (HTTP interface for Go client, CLI, scripts)
  2. NATS subscriber on *.agent.output (automatic capture from Prism)

The service is designed to run alongside Prism. Prism publishes
agent output events to NATS; Remembrance subscribes and auto-captures.

Usage:
    python -m rememberance_mcp.serve
    python -m rememberance_mcp.serve --port 8788 --nats nats://localhost:4222
    python -m rememberance_mcp.serve --no-nats  # REST API only
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading

from rememberance_mcp.config import Settings
from rememberance_mcp.pipeline import MemoryPipeline
from rememberance_mcp.api.rest import start_rest_api

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Remembrance Memory Service")
    parser.add_argument("--host", default="127.0.0.1", help="REST API bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8788, help="REST API port (default: 8788)")
    parser.add_argument("--nats", default="nats://localhost:4222", help="NATS server URL (default: nats://localhost:4222)")
    parser.add_argument("--no-nats", action="store_true", help="Disable NATS subscriber (REST API only)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Initialize pipeline
    settings = Settings()
    pipeline = MemoryPipeline(settings=settings)
    logger.info(f"Remembrance pipeline initialized (db: {settings.DB_PATH})")

    # Start NATS subscriber (optional)
    nats_sub = None
    if not args.no_nats:
        try:
            from rememberance_mcp.nats_sub import NatsSubscriber
            nats_sub = NatsSubscriber(
                pipeline=pipeline,
                nats_url=args.nats,
                settings=settings,
            )
            nats_sub.start()
            logger.info(f"NATS subscriber started on {args.nats}")
        except Exception as e:
            logger.warning(f"NATS subscriber failed to start: {e}")
            logger.info("Continuing in REST-only mode")

    # Graceful shutdown handler
    def shutdown(signum, frame):
        logger.info("Shutting down Remembrance service...")
        if nats_sub:
            nats_sub.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Start REST API (blocking)
    logger.info(f"Remembrance service ready — REST API on http://{args.host}:{args.port}")
    if nats_sub:
        logger.info("NATS subscriber active — listening for agent output events")
    try:
        start_rest_api(pipeline, host=args.host, port=args.port)
    except KeyboardInterrupt:
        logger.info("Interrupted")
    finally:
        if nats_sub:
            nats_sub.stop()


if __name__ == "__main__":
    main()