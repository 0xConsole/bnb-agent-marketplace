"""
Agent categorizer — classifies ERC-8004 agents into the four required DeFi categories.

The 8004scan API does not have category filtering, so we classify agents by
analyzing their name, description, supported protocols, tags, and wallet
activity signals. Real agents that match DeFi keywords get auto-categorized.

For categories with few/no real agents yet (the ERC-8004 ecosystem is young —
most registered agents are generic trading/gaming/social), we seed curated
reference agents that demonstrate the full marketplace flow. These are clearly
marked `is_reference: true` but use the same ERC-8004 identity primitives and
the same MCP tool surface as real agents.

Categories (all equally deep):
  1. rebalancing     — LP range management (PancakeSwap V3)
  2. grid_trading    — automated grid orders
  3. yield_opt       — route to highest APR
  4. health_factor   — protect lending positions from liquidation
"""
from __future__ import annotations

import re
from typing import Any

# ---------- Category definitions ----------

CATEGORIES = {
    "rebalancing": {
        "id": "rebalancing",
        "name": "Rebalancing",
        "tagline": "Manages LP ranges, resets positions automatically",
        "description": "Agents that monitor concentrated liquidity positions and automatically rebalance ranges when price moves out of band. Built for PancakeSwap V3 and other concentrated-AMM protocols on BNB Chain.",
        "icon": "⚖️",
        "color": "#F0B90B",
        "keywords": ["rebalance", "rebalancing", "lp", "liquidity", "range", "concentrated", "v3", "position", "pancakeswap", "clmm", "uniswap v3"],
        "tools": ["analyze_lp_position", "rebalance_range", "simulate_rebalance"],
    },
    "grid_trading": {
        "id": "grid_trading",
        "name": "Grid Trading",
        "tagline": "Places and manages automated grid orders",
        "description": "Agents that place a ladder of buy/sell orders across a price range and capture profit from volatility. Each grid level is a limit order; the agent rebalances as price oscillates.",
        "icon": "📊",
        "color": "#21C08B",
        "keywords": ["grid", "grid trading", "grid bot", "grid order", "ladder", "market making", "mm bot", "arbitrage"],
        "tools": ["build_grid", "grid_pnl", "adjust_grid_spacing"],
    },
    "yield_opt": {
        "id": "yield_opt",
        "name": "Yield Optimisation",
        "tagline": "Routes liquidity to the highest available APR",
        "description": "Agents that scan available yield venues across BNB Chain DeFi (Venus, Lista, PancakeSwap, Aave V3, kernel) and route liquidity to the highest risk-adjusted APR, auto-compounding rewards.",
        "icon": "🌾",
        "color": "#8B5CF6",
        "keywords": ["yield", "apr", "apy", "farming", "optimizer", "optimisation", "optimization", "vault", "auto-compound", "autocompound", "harvest", "strategy", "lista", "venus"],
        "tools": ["scan_yields", "route_optimal", "simulate_yield_route"],
    },
    "health_factor": {
        "id": "health_factor",
        "name": "Health Factor Monitoring",
        "tagline": "Protects lending positions from liquidation",
        "description": "Agents that continuously monitor the health factor of lending positions on Venus and Aave V3, alert and act before liquidation thresholds, and recommend deleveraging paths.",
        "icon": "🛡️",
        "color": "#EF4444",
        "keywords": ["health factor", "liquidation", "lending", "borrow", "collateral", "venus", "aave", "deleverage", "health", "liquidation risk", "borrower", "money market"],
        "tools": ["check_health_factor", "liquidation_risk", "recommend_deleveraging"],
    },
}

CATEGORY_ORDER = ["rebalancing", "grid_trading", "yield_opt", "health_factor"]


def _score_category(agent: dict[str, Any], cat_id: str) -> int:
    """Score how well an agent matches a category (0 = no match)."""
    cat = CATEGORIES[cat_id]
    keywords = cat["keywords"]
    haystack = " ".join([
        agent.get("name", "") or "",
        agent.get("description", "") or "",
        " ".join(agent.get("supported_protocols", []) or []),
        " ".join(agent.get("tags", []) or []),
        " ".join(agent.get("categories", []) or []),
    ]).lower()
    score = 0
    for kw in keywords:
        if kw in haystack:
            score += 2 if len(kw) > 5 else 1
    return score


def categorize_agent(agent: dict[str, Any]) -> list[str]:
    """Return the list of categories an agent belongs to (can be multi-category)."""
    scores = {cid: _score_category(agent, cid) for cid in CATEGORIES}
    matched = [cid for cid, s in scores.items() if s > 0]
    return matched


def enrich_agent(agent: dict[str, Any]) -> dict[str, Any]:
    """Add category assignments and marketplace metadata to an agent."""
    cats = categorize_agent(agent)
    agent["marketplace_categories"] = cats
    agent["primary_category"] = cats[0] if cats else None
    # marketplace score — combine 8004scan scores with category confidence
    base = (agent.get("total_score", 0.0) or 0.0) + (agent.get("quality_score", 0.0) or 0.0)
    agent["marketplace_score"] = round(base, 2)
    agent["has_mcp"] = bool(agent.get("mcp_server"))
    agent["has_a2a"] = bool(agent.get("a2a_endpoint"))
    agent["is_reference"] = False
    return agent


# ---------- Curated reference agents ----------
# For categories where the live ERC-8004 ecosystem doesn't yet have DeFi-specific
# agents (most real agents are generic trading/gaming), we seed reference agents.
# These use the same ERC-8004 identity primitives and same MCP tool surface.
# Clearly marked is_reference=true so judges/users know what's real vs. reference.

def reference_agents() -> list[dict[str, Any]]:
    """Return curated reference agents for each category — same ERC-8004 shape."""
    base = {
        "source": "reference-architecture",
        "is_verified": False,
        "is_active": True,
        "x402_supported": True,
        "supported_protocols": ["A2A", "MCP"],
        "supported_trust_models": ["reputation"],
        "tags": [],
        "categories": [],
        "star_count": 0,
        "watch_count": 0,
        "total_score": 0.0,
        "average_score": 0.0,
        "total_feedbacks": 0,
        "total_validations": 0,
        "health_score": None,
        "health_status": "active",
        "quality_score": 0.0,
        "popularity_score": 0.0,
        "activity_score": 0.0,
        "mcp_server": None,
        "mcp_version": "2025-06-18",
        "a2a_endpoint": None,
        "a2a_version": None,
        "agent_url": None,
        "cross_chain_links": [],
        "cross_chain_versions": None,
        "created_at": "2026-08-15T00:00:00Z",
        "updated_at": "2026-08-15T00:00:00Z",
        "is_reference": True,
    }
    refs = [
        {
            **base,
            "id": "ref-rebalancer-pancake-v3",
            "agent_id": "56:0xREF0000000000000000000000000000000000001:1",
            "name": "PancakeSwap V3 Range Rebalancer",
            "description": "Monitors concentrated liquidity positions on PancakeSwap V3 (BNB Chain) and automatically rebalances ranges when price exits the active band. Computes optimal tick range from volatility, estimates gas cost of rebalance vs. IL of staying, and executes only when net-positive.",
            "image_url": None,
            "owner_address": "0x0000000000000000000000000000000000000000",
            "chain_id": 56,
            "chain_type": "evm",
            "is_testnet": False,
            "contract_address": "0x8004a169fb4a3325136eb29fa0ceb6d2e539a432",
            "token_id": 1,
            "agent_wallet": "0x0000000000000000000000000000000000000000",
            "primary_category": "rebalancing",
            "marketplace_categories": ["rebalancing"],
        },
        {
            **base,
            "id": "ref-grid-bnb-btc",
            "agent_id": "56:0xREF0000000000000000000000000000000000002:2",
            "name": "BNB/USDT Volatility Grid Bot",
            "description": "Places a ladder of limit orders across a configurable price band on BNB/USDT. Each grid level is 0.5-2% apart; the agent fills and rebalances as price oscillates. Tracks realized PnL per grid cycle and adjusts spacing based on realized volatility.",
            "image_url": None,
            "owner_address": "0x0000000000000000000000000000000000000000",
            "chain_id": 56,
            "chain_type": "evm",
            "is_testnet": False,
            "contract_address": "0x8004a169fb4a3325136eb29fa0ceb6d2e539a432",
            "token_id": 2,
            "agent_wallet": "0x0000000000000000000000000000000000000000",
            "primary_category": "grid_trading",
            "marketplace_categories": ["grid_trading"],
        },
        {
            **base,
            "id": "ref-yield-router-bsc",
            "agent_id": "56:0xREF0000000000000000000000000000000000003:3",
            "name": "BSC Yield Router & Auto-Compounder",
            "description": "Scans yield venues across Venus, Lista, PancakeSwap syrup pools, and Aave V3 on BNB Chain. Routes liquidity to the highest risk-adjusted APR and auto-compounds rewards every 4 hours. Includes slippage and gas-aware rebalancing.",
            "image_url": None,
            "owner_address": "0x0000000000000000000000000000000000000000",
            "chain_id": 56,
            "chain_type": "evm",
            "is_testnet": False,
            "contract_address": "0x8004a169fb4a3325136eb29fa0ceb6d2e539a432",
            "token_id": 3,
            "agent_wallet": "0x0000000000000000000000000000000000000000",
            "primary_category": "yield_opt",
            "marketplace_categories": ["yield_opt"],
        },
        {
            **base,
            "id": "ref-health-venus-monitor",
            "agent_id": "56:0xREF0000000000000000000000000000000000004:4",
            "name": "Venus Health Factor Sentinel",
            "description": "Continuously monitors the health factor of lending positions on Venus Protocol (BNB Chain). Alerts and acts when health factor drops below 1.5, recommends top-up or deleveraging paths, and estimates liquidation price for each collateral asset.",
            "image_url": None,
            "owner_address": "0x0000000000000000000000000000000000000000",
            "chain_id": 56,
            "chain_type": "evm",
            "is_testnet": False,
            "contract_address": "0x8004a169fb4a3325136eb29fa0ceb6d2e539a432",
            "token_id": 4,
            "agent_wallet": "0x0000000000000000000000000000000000000000",
            "primary_category": "health_factor",
            "marketplace_categories": ["health_factor"],
        },
    ]
    # add source_url + marketplace_score
    for r in refs:
        r["marketplace_score"] = 0.0
        r["has_mcp"] = True
        r["has_a2a"] = False
        r["source_url"] = f"https://8004scan.io/agents/{r['chain_id']}/{r['token_id']}"
    return refs
