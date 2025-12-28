"""
Android Shell Manager - MCP Server
Entry point for the MCP server.
"""
from mcp.server.fastmcp import FastMCP

# Create MCP server instance
mcp = FastMCP("AndroidShellManager")

# Register tools - import is deferred to avoid blocking
from tools import register_tools
register_tools(mcp)


def main():
    """Main entry point for script execution."""
    mcp.run()


if __name__ == "__main__":
    main()
