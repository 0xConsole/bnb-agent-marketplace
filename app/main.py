"""
BNB Agent Marketplace — FastAPI Main Application.

A marketplace that surfaces real BNB Chain ERC-8004 agents from 8004scan,
classifies them into four DeFi categories, and exposes real working MCP tools
per category. Users discover, compare, and activate agents end-to-end.

Built for the "Build the Era" hackathon (BNB Chain).
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

from app.scan_client import (
    list_agents as scan_list_agents,
    get_agent_detail as scan_get_agent_detail,
    get_chains as scan_get_chains,
    BSC_CHAIN_ID,
)
from app.categorizer import (
    CATEGORIES, CATEGORY_ORDER, enrich_agent, reference_agents,
)
from app.mcp_tools import (
    rebalancing, grid, yield_opt as yield_tools, health,
    ALL_TOOL_DEFS, ALL_TOOL_MAPS, TOTAL_TOOLS,
)
from app.advantage_report import generate_report

PROJECT_ROOT = Path(__file__).resolve().parent.parent

app = FastAPI(
    title="BNB Agent Marketplace",
    description="Discovery layer for BNB Chain AI agents — real ERC-8004 data from 8004scan + 4 DeFi agent categories with working MCP tools. Built for Build the Era hackathon.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Helpers ----------

def _load_agents(limit: int = 100) -> list[dict[str, Any]]:
    """Load real agents from 8004scan + enrich with categories + add reference agents."""
    real = scan_list_agents(chain_id=BSC_CHAIN_ID, limit=limit)
    agents = []
    if real.get("items"):
        for a in real["items"]:
            agents.append(enrich_agent(a))
    refs = reference_agents()
    return agents + refs


def _categorize_all(agents: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group agents by category. Reference agents go to their category; real agents
    go to any category they match (can appear in multiple)."""
    grouped = {cid: [] for cid in CATEGORY_ORDER}
    for a in agents:
        cats = a.get("marketplace_categories") or []
        if a.get("is_reference"):
            cats = [a.get("primary_category")]
        for cid in cats:
            if cid in grouped:
                grouped[cid].append(a)
        # uncategorized real agents → put in a "featured" pool but not a category
    return grouped


# ---------- UI ----------

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the marketplace UI."""
    index = PROJECT_ROOT / "static" / "index.html"
    if index.exists():
        return HTMLResponse(index.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>BNB Agent Marketplace</h1><p>UI not found. See <a href='/api/health'>/api/health</a></p>")


# ---------- API: Health & metadata ----------

@app.get("/api/health")
async def health_endpoint():
    return {
        "status": "ok",
        "service": "BNB Agent Marketplace",
        "version": "1.0.0",
        "8004scan_integration": "live",
        "chain_id": BSC_CHAIN_ID,
        "categories": len(CATEGORIES),
        "total_mcp_tools": TOTAL_TOOLS,
        "timestamp": time.time(),
    }


@app.get("/api/categories")
async def categories():
    """List the four agent categories with their tools."""
    return {
        "categories": [
            {**CATEGORIES[cid], "tool_count": len(ALL_TOOL_DEFS[cid]), "tools": ALL_TOOL_DEFS[cid]}
            for cid in CATEGORY_ORDER
        ],
        "total_categories": len(CATEGORIES),
        "total_tools": TOTAL_TOOLS,
    }


@app.get("/api/chains")
async def chains():
    """List supported chains from 8004scan."""
    return scan_get_chains()


# ---------- API: Agent discovery ----------

@app.get("/api/agents")
async def agents(
    limit: int = Query(50, ge=1, le=200),
    category: str | None = None,
    reference_only: bool = False,
):
    """List agents. Optional category filter. Pulls real ERC-8004 data from 8004scan."""
    all_agents = _load_agents(limit=limit)
    if reference_only:
        all_agents = [a for a in all_agents if a.get("is_reference")]
    if category:
        if category not in CATEGORIES:
            return JSONResponse({"error": f"unknown category '{category}'", "valid": list(CATEGORIES.keys())}, status_code=400)
        grouped = _categorize_all(all_agents)
        return {
            "category": category,
            "category_info": CATEGORIES[category],
            "agents": grouped[category],
            "count": len(grouped[category]),
        }
    return {
        "agents": all_agents,
        "count": len(all_agents),
        "source": "8004scan + reference",
        "timestamp": time.time(),
    }


@app.get("/api/agents/by-category")
async def agents_by_category():
    """List all agents grouped by the four categories."""
    all_agents = _load_agents(limit=100)
    grouped = _categorize_all(all_agents)
    return {
        "categories": {
            cid: {
                "info": CATEGORIES[cid],
                "agents": grouped[cid],
                "count": len(grouped[cid]),
            }
            for cid in CATEGORY_ORDER
        },
        "total_agents": len(all_agents),
        "timestamp": time.time(),
    }


@app.get("/api/agents/{chain_id}/{token_id}")
async def agent_detail(chain_id: int, token_id: int):
    """Get full agent detail from 8004scan (identity, wallet, MCP server, health, scores)."""
    detail = scan_get_agent_detail(chain_id, token_id)
    return enrich_agent(detail)


# ---------- API: MCP tools (one endpoint per tool, GET for easy testing) ----------
# Rebalancing

@app.get("/api/tools/rebalancing/analyze_lp_position")
async def tool_analyze_lp_position(
    lower_tick: int = -10000, upper_tick: int = 10000, liquidity: int = 1_000_000,
    pool_address: str = "0x36696169163f4870e324cc795b6a12a3c725a4db",
):
    return rebalancing.analyze_lp_position(pool_address=pool_address, lower_tick=lower_tick, upper_tick=upper_tick, liquidity=liquidity)


@app.get("/api/tools/rebalancing/rebalance_range")
async def tool_rebalance_range(
    lower_tick: int = -10000, upper_tick: int = 10000,
    risk_tolerance: str = "moderate",
    volatility_window_hours: int = 24,
    pool_address: str = "0x36696169163f4870e324cc795b6a12a3c725a4db",
):
    return rebalancing.rebalance_range(
        pool_address=pool_address, current_lower_tick=lower_tick, current_upper_tick=upper_tick,
        risk_tolerance=risk_tolerance, volatility_window_hours=volatility_window_hours,
    )


@app.get("/api/tools/rebalancing/simulate_rebalance")
async def tool_simulate_rebalance(
    current_lower: int = -10000, current_upper: int = 10000,
    new_lower: int = -5000, new_upper: int = 5000,
    value_usd: float = 10000, horizon_hours: int = 72,
):
    return rebalancing.simulate_rebalance(
        current_lower_tick=current_lower, current_upper_tick=current_upper,
        new_lower_tick=new_lower, new_upper_tick=new_upper,
        position_value_usd=value_usd, horizon_hours=horizon_hours,
    )


# Grid Trading

@app.get("/api/tools/grid/build_grid")
async def tool_build_grid(
    pair: str = "BNB/USDT", band_pct: float = 10, levels: int = 10, capital_usd: float = 5000,
):
    return grid.build_grid(pair=pair, price_band_pct=band_pct, levels=levels, capital_usd=capital_usd)


@app.get("/api/tools/grid/grid_pnl")
async def tool_grid_pnl():
    return grid.grid_pnl()


@app.get("/api/tools/grid/adjust_grid_spacing")
async def tool_adjust_grid_spacing(
    pair: str = "BNB/USDT", lookback_hours: int = 48, current_spacing_pct: float = 1.0, capital_usd: float = 5000,
):
    return grid.adjust_grid_spacing(pair=pair, lookback_hours=lookback_hours, current_spacing_pct=current_spacing_pct, capital_usd=capital_usd)


# Yield Optimisation

@app.get("/api/tools/yield/scan_yields")
async def tool_scan_yields(asset: str = "all", risk_level: str = "all"):
    return yield_tools.scan_yields(asset=asset, risk_level=risk_level)


@app.get("/api/tools/yield/route_optimal")
async def tool_route_optimal(
    capital_usd: float = 10000, asset: str = "BNB", max_risk: str = "medium", min_liquidity_usd: int = 10_000_000,
):
    return yield_tools.route_optimal(capital_usd=capital_usd, asset=asset, max_risk=max_risk, min_liquidity_usd=min_liquidity_usd)


@app.get("/api/tools/yield/simulate_yield_route")
async def tool_simulate_yield_route(
    capital_usd: float = 10000, horizon_days: int = 30, auto_compound: bool = True,
):
    return yield_tools.simulate_yield_route(capital_usd=capital_usd, horizon_days=horizon_days, auto_compound=auto_compound)


# Health Factor Monitoring

@app.get("/api/tools/health/check_health_factor")
async def tool_check_health_factor(
    protocol: str = "venus", collateral_bnb: float = 10, borrowed_usdt: float = 2500,
):
    return health.check_health_factor(protocol=protocol, collateral={"BNB": collateral_bnb}, borrowed={"USDT": borrowed_usdt})


@app.get("/api/tools/health/liquidation_risk")
async def tool_liquidation_risk(
    protocol: str = "venus", collateral_bnb: float = 10, borrowed_usdt: float = 2500, stress_pct: float = 20,
):
    return health.liquidation_risk(protocol=protocol, collateral={"BNB": collateral_bnb}, borrowed={"USDT": borrowed_usdt}, stress_pct=stress_pct)


@app.get("/api/tools/health/recommend_deleveraging")
async def tool_recommend_deleveraging(
    protocol: str = "venus", collateral_bnb: float = 10, borrowed_usdt: float = 2500,
    target_hf: float = 1.5, available_usd: float = 2000,
):
    return health.recommend_deleveraging(
        protocol=protocol, collateral={"BNB": collateral_bnb}, borrowed={"USDT": borrowed_usdt},
        target_health_factor=target_hf, available_usd=available_usd,
    )


# ---------- MCP manifest ----------

@app.get("/api/mcp/manifest")
async def mcp_manifest():
    """MCP-compatible manifest describing all available tools."""
    tools = []
    for cat_id, tool_defs in ALL_TOOL_DEFS.items():
        for td in tool_defs:
            tools.append({
                "name": td["name"],
                "description": td["description"],
                "category": cat_id,
                "category_name": CATEGORIES[cat_id]["name"],
                "parameters": td["parameters"],
                "endpoint": f"/api/tools/{cat_id.replace('_opt','')}/{td['name']}",
            })
    return {
        "server_name": "bnb-agent-marketplace",
        "server_version": "1.0.0",
        "mcp_version": "2025-06-18",
        "tools": tools,
        "total_tools": len(tools),
    }


# ---------- Agent Advantage Report (TermiX bounty) ----------

@app.get("/api/advantage-report", response_class=JSONResponse)
async def advantage_report_json():
    """Generate the Agent Advantage Report (JSON) — required for TermiX Challenge."""
    return generate_report()


@app.get("/api/advantage-report.md", response_class=PlainTextResponse)
async def advantage_report_markdown():
    """Generate the Agent Advantage Report as Markdown."""
    report = generate_report()
    lines = []
    lines.append(f"# {report['report_title']}")
    lines.append(f"\n**Generated for:** {report['generated_for']}")
    lines.append(f"**Generated at:** {report['generated_at']}\n")
    lines.append("## Requirements Met\n")
    for k, v in report["requirements_met"].items():
        lines.append(f"- **{k}**: {v}")
    lines.append(f"\n## Summary\n")
    s = report["summary"]
    lines.append(f"- **Total tasks:** {s['total_tasks']}")
    lines.append(f"- **Total manual time:** {s['total_manual_time_seconds']}s ({round(s['total_manual_time_seconds']/60, 1)} min)")
    lines.append(f"- **Total agent time:** {s['total_agent_time_seconds']}s")
    lines.append(f"- **Time saved:** {s['total_time_saved_seconds']}s ({round(s['total_time_saved_seconds']/60, 1)} min)")
    lines.append(f"- **Average speedup:** {s['average_speedup_factor']}×")
    lines.append(f"- **Cost saved:** ${s['total_cost_saved_usd']}")
    lines.append("\n## Tasks\n")
    for t in report["tasks"]:
        lines.append(f"### {t['task_id']}: {t['task']}")
        lines.append(f"**Category:** {t['category']} | **High-stakes:** {t.get('high_stakes', False)}\n")
        lines.append("**Without agent:**")
        wa = t["without_agent"]
        lines.append(f"- Method: {wa['method']}")
        lines.append(f"- Time: {wa['time_seconds']}s")
        lines.append(f"- Cost: ${wa['cost_usd']}")
        lines.append(f"- Quality: {wa['output_quality']}")
        if wa.get("output"):
            lines.append(f"- Output: `{wa['output']}`")
        lines.append("\n**With agent:**")
        we = t["with_agent"]
        lines.append(f"- Method: {we['method']}")
        lines.append(f"- Time: {we['time_seconds']}s")
        lines.append(f"- Cost: ${we['cost_usd']}")
        lines.append(f"- Quality: {we['output_quality']}")
        if we.get("output"):
            lines.append(f"- Output: `{we['output']}`")
        adv = t["advantage"]
        lines.append(f"\n**Advantage:** {adv['time_speedup_factor']}× faster, quality {adv['quality_improvement']}\n")
    lines.append(f"\n## Conclusion\n\n{report['conclusion']}\n")
    return "\n".join(lines)


# ---------- 8004scan passthrough ----------

@app.get("/api/scan/agents")
async def scan_agents(limit: int = Query(20, ge=1, le=100), offset: int = 0):
    """Raw 8004scan agent listing (passthrough)."""
    return scan_list_agents(chain_id=BSC_CHAIN_ID, limit=limit, offset=offset)
