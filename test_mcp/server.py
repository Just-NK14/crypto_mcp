# server.py
from fastmcp import FastMCP

mcp = FastMCP("Demo 🚀")

@mcp.tool
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

# 3. This is the entry point to start the server.
if __name__ == "__main__":
    mcp.run(transport="stdio")