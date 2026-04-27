"""
MCP Server — Model Context Protocol Interface

PATTERN: Protocol Server (Adapter Pattern)
============================================

This module adapts our internal MemoryPipeline into the MCP protocol.
The MCP protocol is a standard that AI agents (Claude, GPT, etc.) use
to call tools on external systems.

HOW MCP WORKS:
  1. Client (Claude Desktop, Cursor, etc.) starts our server as a subprocess
  2. Client sends JSON-RPC messages over stdin/stdout
  3. Server responds with tool results
  4. When client disconnects, server shuts down

MESSAGE FORMAT (JSON-RPC 2.0):
  Request:  {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "memory_capture", "arguments": {...}}}
  Response: {"jsonrpc": "2.0", "result": {"content": [{"type": "text", "text": "..."}]}}

  This is the same format used by JSON-RPC APIs everywhere (Ethereum, etc.)

KEY CONCEPT: Tools vs Resources vs Prompts
  MCP defines three types of server capabilities:
  - Tools: Functions the AI can CALL (capture, search, consolidate)
  - Resources: Data the AI can READ (like files, but structured)
  - Prompts: Template messages the AI can use (not needed here)

  We only expose Tools because memory is action-oriented:
  you capture, you search, you consolidate.

WHY NOT REST API?
  REST requires a running server, port management, auth, CORS...
  MCP over stdio requires: nothing. Just launch the process.
  It's simpler, more secure (no network exposure), and faster (no HTTP overhead).
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def create_server():
    """
    Create and configure the MCP server with all memory tools.

    Returns an MCP Server instance ready to run.
    """
    from mcp.server import Server
    from mcp.types import Tool, TextContent
    from rememberance_mcp.config import Settings
    from rememberance_mcp.pipeline import MemoryPipeline

    settings = Settings()
    pipeline = MemoryPipeline(settings=settings)

    server = Server(settings.MCP_SERVER_NAME)
    server.settings = settings  # stash for reference

    @server.list_tools()
    async def list_tools():
        """
        Called by the client to discover available tools.

        This is like an OpenAPI spec — it tells the AI what it can do,
        what parameters each tool takes, and what it returns.
        The AI uses this to decide which tool to call.
        """
        return [
            Tool(
                name="memory_capture",
                description=(
                    "Capture a piece of text as a memory. The system automatically "
                    "classifies its importance (skip/cold/active/persist), extracts "
                    "structured data (summary, category, topics), and stores it with "
                    "tier-based TTL. Use this for anything worth remembering: decisions, "
                    "project state, user preferences, important facts."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "The text to capture as a memory",
                        },
                        "source": {
                            "type": "string",
                            "description": "Where this came from (discord, cli, api, email, etc.)",
                            "default": "cli",
                        },
                        "category": {
                            "type": "string",
                            "enum": ["project", "person", "preference", "decision", "task", "strategy", "session"],
                            "description": "Override auto-detected category (optional)",
                        },
                        "tier": {
                            "type": "string",
                            "enum": ["cold", "active", "persist"],
                            "description": "Override auto-detected tier (optional)",
                        },
                    },
                    "required": ["text"],
                },
            ),
            Tool(
                name="memory_search",
                description=(
                    "Search stored memories by keyword and metadata filters. "
                    "Returns matching memories sorted by recency."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query (keyword matching)",
                        },
                        "category": {
                            "type": "string",
                            "description": "Filter by category (optional)",
                        },
                        "tier": {
                            "type": "string",
                            "description": "Filter by tier (optional)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results to return",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="memory_consolidate",
                description=(
                    "Run the decay/promotion cycle. Deletes expired cold memories, "
                    "promotes frequently-accessed active memories to persist, and "
                    "demotes rarely-accessed persist memories to active. Run this "
                    "periodically (e.g., daily) to keep the memory store healthy."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="memory_get",
                description="Get a specific memory by its ID.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "The memory ID (e.g., mem_1234567890_abc123)",
                        },
                    },
                    "required": ["id"],
                },
            ),
            Tool(
                name="memory_delete",
                description="Delete a specific memory by its ID.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "The memory ID to delete",
                        },
                    },
                    "required": ["id"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        """
        Called by the client when the AI decides to use a tool.

        This is the "router" — it dispatches to the right pipeline method
        based on the tool name the AI selected.
        """
        try:
            if name == "memory_capture":
                result = pipeline.capture(
                    text=arguments["text"],
                    source=arguments.get("source", "cli"),
                    category=arguments.get("category"),
                    tier=arguments.get("tier"),
                )
                if result["decision"] == "SKIP":
                    return [TextContent(type="text", text="Skipped — not important enough to store.")]
                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2),
                )]

            elif name == "memory_search":
                results = pipeline.search(
                    query=arguments["query"],
                    category=arguments.get("category"),
                    tier=arguments.get("tier"),
                    limit=arguments.get("limit", 10),
                )
                if not results:
                    return [TextContent(type="text", text="No memories found matching that query.")]
                return [TextContent(
                    type="text",
                    text=json.dumps(results, indent=2, default=str),
                )]

            elif name == "memory_consolidate":
                result = pipeline.consolidate()
                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2),
                )]

            elif name == "memory_get":
                result = pipeline.get(arguments["id"])
                if not result:
                    return [TextContent(type="text", text=f"Memory {arguments['id']} not found.")]
                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2, default=str),
                )]

            elif name == "memory_delete":
                deleted = pipeline.delete(arguments["id"])
                if deleted:
                    return [TextContent(type="text", text=f"Deleted memory {arguments['id']}.")]
                return [TextContent(type="text", text=f"Memory {arguments['id']} not found.")]

            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

        except Exception as e:
            logger.error(f"Tool call error: {e}", exc_info=True)
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    return server