"""
8004scan API client — real ERC-8004 agent data discovery.

Integrates with the live 8004scan.io API (by AltLayer) to pull real
ERC-8004 registered agent data from BNB Chain and other EVM chains.

API base: https://api.8004scan.io/api/v1
Key endpoints (verified working 2026-08-15):
  - GET /agents?chain={id}&limit={n}&offset={n}   — list agents
  - GET /agents/{chain_id}/{token_id}              — agent detail (rich)
  - GET /chains                                     — all supported chains

Free Pro-tier for hackathon participants: 500 req/min, 100K req/day.
No API key required for basic listing/detail endpoints.
"""
from __future__ import annotations

import os
import time
import random
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

API_BASE = os.getenv("SCAN8004_API_BASE", "https://api.8004scan.io/api/v1")
BSC_CHAIN_ID = 56
DEFAULT_TIMEOUT = 15.0
CACHE_TTL = 60  # seconds — keep the marketplace snappy without hammering the API

# Simple in-memory cache (fine for serverless; each invocation is fresh)
_cache: dict[str, tuple[float, Any]] = {}


def _cache_get(key: str) -> Any | None:
    entry = _cache.get(key)
    if entry and (time.time() - entry[0]) < CACHE_TTL:
        return entry[1]
    return None


def _cache_set(key: str, value: Any) -> Any:
    _cache[key] = (time.time(), value)
    return value


def _normalize_agent(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize the 8004scan agent shape into our marketplace model."""
    name = raw.get("name", "") or "Unnamed Agent"
    desc = raw.get("description", "") or ""
    agent_id = raw.get("agent_id", "")
    chain_id = raw.get("chain_id")
    token_id = raw.get("token_id")
    return {
        "id": raw.get("id", ""),
        "agent_id": agent_id,
        "name": name,
        "description": desc,
        "image_url": raw.get("image_url"),
        "owner_address": raw.get("owner_address"),
        "owner_username": raw.get("owner_username"),
        "owner_avatar_url": raw.get("owner_avatar_url"),
        "chain_id": chain_id,
        "chain_type": raw.get("chain_type", "evm"),
        "is_testnet": raw.get("is_testnet", False),
        "contract_address": raw.get("contract_address"),
        "token_id": token_id,
        "agent_wallet": raw.get("agent_wallet"),
        "is_verified": raw.get("is_verified", False),
        "is_active": raw.get("is_active", True) if raw.get("is_active") is not None else True,
        "x402_supported": raw.get("x402_supported", False),
        "supported_protocols": raw.get("supported_protocols", []) or [],
        "supported_trust_models": raw.get("supported_trust_models", []) or [],
        "tags": raw.get("tags", []) or [],
        "categories": raw.get("categories", []) or [],
        "star_count": raw.get("star_count", 0) or 0,
        "watch_count": raw.get("watch_count", 0) or 0,
        "total_score": raw.get("total_score", 0.0) or 0.0,
        "average_score": raw.get("average_score", 0.0) or 0.0,
        "total_feedbacks": raw.get("total_feedbacks", 0) or 0,
        "total_validations": raw.get("total_validations", 0) or 0,
        "health_score": raw.get("health_score"),
        "health_status": raw.get("health_status"),
        "quality_score": raw.get("quality_score", 0.0) or 0.0,
        "popularity_score": raw.get("popularity_score", 0.0) or 0.0,
        "activity_score": raw.get("activity_score", 0.0) or 0.0,
        "mcp_server": raw.get("mcp_server"),
        "mcp_version": raw.get("mcp_version"),
        "a2a_endpoint": raw.get("a2a_endpoint"),
        "a2a_version": raw.get("a2a_version"),
        "agent_url": raw.get("agent_url"),
        "services": raw.get("services"),
        "created_at": raw.get("created_at"),
        "updated_at": raw.get("updated_at"),
        "created_tx_hash": raw.get("created_tx_hash"),
        "created_block_number": raw.get("created_block_number"),
        # fields only on detail endpoint
        "cross_chain_links": raw.get("cross_chain_links", []) or [],
        "cross_chain_versions": raw.get("cross_chain_versions"),
        "source": "8004scan",
        "source_url": f"https://8004scan.io/agents/{chain_id}/{token_id}" if chain_id and token_id else None,
    }


def list_agents(
    chain_id: int = BSC_CHAIN_ID,
    limit: int = 50,
    offset: int = 0,
    include_testnet: bool = False,
) -> dict[str, Any]:
    """List ERC-8004 agents from 8004scan. Returns normalized dict with items + total."""
    cache_key = f"list:{chain_id}:{limit}:{offset}:{include_testnet}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    params = {"chain": chain_id, "limit": limit, "offset": offset}
    url = f"{API_BASE}/agents?{urlencode(params)}"
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            resp = client.get(url, headers={"User-Agent": "bnb-agent-marketplace/1.0"})
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        return _cache_set(cache_key, {
            "items": [],
            "total": 0,
            "error": str(e),
            "source": "8004scan",
            "fallback": True,
        })

    items = []
    for raw in data.get("items", []):
        agent = _normalize_agent(raw)
        if not include_testnet and agent["is_testnet"]:
            continue
        items.append(agent)

    return _cache_set(cache_key, {
        "items": items,
        "total": data.get("total", 0),
        "limit": data.get("limit", limit),
        "offset": data.get("offset", offset),
        "source": "8004scan",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    })


def get_agent_detail(chain_id: int, token_id: int) -> dict[str, Any]:
    """Get full agent detail from 8004scan (includes MCP server, A2A, health, scores)."""
    cache_key = f"detail:{chain_id}:{token_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    url = f"{API_BASE}/agents/{chain_id}/{token_id}"
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            resp = client.get(url, headers={"User-Agent": "bnb-agent-marketplace/1.0"})
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        return {"error": str(e), "chain_id": chain_id, "token_id": token_id}

    return _cache_set(cache_key, _normalize_agent(data))


def get_chains() -> dict[str, Any]:
    """List all chains supported by 8004scan."""
    cached = _cache_get("chains")
    if cached is not None:
        return cached
    url = f"{API_BASE}/chains"
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            resp = client.get(url, headers={"User-Agent": "bnb-agent-marketplace/1.0"})
            resp.raise_for_status()
            return _cache_set("chains", resp.json())
    except Exception as e:
        return {"error": str(e)}


def search_agents_by_keyword(keyword: str, chain_id: int = BSC_CHAIN_ID, limit: int = 100) -> list[dict[str, Any]]:
    """Client-side keyword search across fetched agents (8004scan has no server-side search)."""
    # fetch a larger pool then filter client-side
    pool = list_agents(chain_id=chain_id, limit=min(limit, 200))
    if pool.get("error"):
        return []
    kw = keyword.lower()
    matches = []
    for agent in pool.get("items", []):
        haystack = f"{agent.get('name','')} {agent.get('description','')} {' '.join(agent.get('supported_protocols',[]))} {' '.join(agent.get('tags',[]))}".lower()
        if kw in haystack:
            matches.append(agent)
    return matches
