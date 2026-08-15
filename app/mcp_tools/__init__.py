"""MCP tools package — aggregates all four category tool modules."""
from app.mcp_tools import rebalancing, grid, health
from app.mcp_tools import yield_opt as yield_tools

ALL_TOOL_DEFS = {
    "rebalancing": rebalancing.TOOL_DEFS,
    "grid_trading": grid.TOOL_DEFS,
    "yield_opt": yield_tools.TOOL_DEFS,
    "health_factor": health.TOOL_DEFS,
}

ALL_TOOL_MAPS = {
    "rebalancing": rebalancing.TOOL_MAP,
    "grid_trading": grid.TOOL_MAP,
    "yield_opt": yield_tools.TOOL_MAP,
    "health_factor": health.TOOL_MAP,
}

TOTAL_TOOLS = sum(len(m) for m in ALL_TOOL_MAPS.values())
