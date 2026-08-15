# BNB Agent Marketplace

**Discovery layer for BNB Chain AI agents — built for the [Build the Era](https://www.bnbchain.org/en/hackathons/smart-money-era) hackathon.**

A marketplace that surfaces real ERC-8004 agent data from [8004scan](https://8004scan.io),
classifies agents into four DeFi categories, and exposes real working MCP tools per category.
Users can discover → understand → activate agents end-to-end.

🌐 **Live:** deployed to Vercel free tier  
📦 **Repo:** [github.com/0xConsole/bnb-agent-marketplace](https://github.com/0xConsole/bnb-agent-marketplace)

---

## What It Does

| Category | What the agent does | MCP Tools |
|----------|---------------------|-----------|
| ⚖️ **Rebalancing** | Manages LP ranges, resets positions automatically (PancakeSwap V3) | `analyze_lp_position`, `rebalance_range`, `simulate_rebalance` |
| 📊 **Grid Trading** | Places and manages automated grid orders | `build_grid`, `grid_pnl`, `adjust_grid_spacing` |
| 🌾 **Yield Optimisation** | Routes liquidity to the highest available APR | `scan_yields`, `route_optimal`, `simulate_yield_route` |
| 🛡️ **Health Factor Monitoring** | Protects lending positions from liquidation (Venus, Aave V3) | `check_health_factor`, `liquidation_risk`, `recommend_deleveraging` |

**12 MCP tools total** — 3 per category, all equally deep.

## Data Layer — Real 8004scan Integration

The marketplace pulls **real ERC-8004 agent data** from the 8004scan API (by AltLayer):
- `GET /api/v1/agents?chain=56` — 737,000+ real BSC agents
- `GET /api/v1/agents/{chain_id}/{token_id}` — full agent detail (wallet, MCP server, A2A endpoint, health score, ERC-8004 identity)
- `GET /api/v1/chains` — multi-chain support

Real agents are auto-categorized by analyzing their name, description, supported protocols, and tags. For DeFi categories where the live ecosystem doesn't yet have category-specific agents, we seed **reference agents** (clearly marked `is_reference: true`) that use the same ERC-8004 identity primitives and the same MCP tool surface.

## Agent Advantage Report (TermiX Bounty)

The `/api/advantage-report` endpoint runs **4 real tasks both ways** — with a marketplace agent vs. without — and reports time, cost, and output quality with actual outputs attached. 3 of 4 tasks are high-stakes (trading/security), satisfying the TermiX requirement. View it live at `/api/advantage-report.md`.

## Architecture

```
8004scan API (real ERC-8004 data, 737K+ agents)
        ↓
  app/scan_client.py     ← live HTTP integration
  app/categorizer.py     ← classifies agents into 4 categories
        ↓
  app/mcp_tools/         ← 12 real working tools (3 per category)
    rebalancing.py         (PancakeSwap V3 LP math, BSC RPC)
    grid.py               (grid construction, PnL, vol-optimal spacing)
    yield_opt.py          (Venus/Lista/PancakeSwap/Aave yield scanning)
    health.py             (Venus/Aave V3 health factor, liquidation, deleveraging)
        ↓
  app/advantage_report.py ← Agent Advantage Report (TermiX)
        ↓
  app/main.py (FastAPI)   ← marketplace UI + API + MCP endpoints
  api/index.py            ← Vercel serverless entry
        ↓
  Vercel free tier
```

## Tech Stack (all free tier)

- **Backend:** FastAPI (Python) on Vercel serverless
- **Data:** 8004scan API (free Pro-tier, 500 req/min) + BSC public RPCs
- **Frontend:** Single-page HTML/JS (no framework)
- **Deploy:** Vercel free tier
- **Tests:** pytest (15 tests, all passing)

## Local Development

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# open http://localhost:8000
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Marketplace UI |
| `GET /api/health` | Health check |
| `GET /api/categories` | Four agent categories + tools |
| `GET /api/agents` | List agents (real 8004scan + reference) |
| `GET /api/agents/by-category` | Agents grouped by 4 categories |
| `GET /api/agents/{chain_id}/{token_id}` | Full agent detail from 8004scan |
| `GET /api/mcp/manifest` | MCP-compatible tool manifest (12 tools) |
| `GET /api/tools/rebalancing/*` | 3 rebalancing tools |
| `GET /api/tools/grid/*` | 3 grid trading tools |
| `GET /api/tools/yield/*` | 3 yield optimisation tools |
| `GET /api/tools/health/*` | 3 health factor tools |
| `GET /api/advantage-report` | Agent Advantage Report (JSON) |
| `GET /api/advantage-report.md` | Agent Advantage Report (Markdown) |

## What's Real vs. Reference

| Component | Status |
|-----------|--------|
| 8004scan API integration | ✅ Real (live HTTP to api.8004scan.io) |
| ERC-8004 agent data (identity, wallet, scores) | ✅ Real |
| Rebalancing MCP tools (BSC RPC, PancakeSwap V3 math) | ✅ Real working |
| Grid trading MCP tools | ✅ Real working |
| Yield optimisation MCP tools (real protocol addresses) | ✅ Real working |
| Health factor MCP tools (Venus/Aave V3 params) | ✅ Real working |
| Agent Advantage Report (4 real A/B tasks) | ✅ Real working |
| DeFi-specific reference agents | 📋 Reference architecture (marked `is_reference`) |

## License

MIT
