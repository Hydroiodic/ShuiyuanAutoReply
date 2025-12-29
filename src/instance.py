from mcp.server.fastmcp import FastMCP

# Create an MCP server
mcp = FastMCP("ShuiyuanAutoReply", json_response=True)

__all__ = ["mcp"]
