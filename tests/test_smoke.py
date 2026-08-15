"""Tests for BNB Agent Marketplace — runs against the local FastAPI app."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["categories"] == 4
    assert data["total_mcp_tools"] >= 12


def test_categories():
    r = client.get("/api/categories")
    assert r.status_code == 200
    data = r.json()
    assert data["total_categories"] == 4
    cat_ids = {c["id"] for c in data["categories"]}
    assert cat_ids == {"rebalancing", "grid_trading", "yield_opt", "health_factor"}
    # each category has 3 tools
    for c in data["categories"]:
        assert c["tool_count"] == 3, f"{c['id']} should have 3 tools"


def test_mcp_manifest():
    r = client.get("/api/mcp/manifest")
    assert r.status_code == 200
    data = r.json()
    assert data["total_tools"] == 12
    tool_names = {t["name"] for t in data["tools"]}
    assert "analyze_lp_position" in tool_names
    assert "scan_yields" in tool_names
    assert "check_health_factor" in tool_names
    assert "build_grid" in tool_names


def test_tool_rebalancing_analyze():
    r = client.get("/api/tools/rebalancing/analyze_lp_position")
    assert r.status_code == 200
    data = r.json()
    assert data["tool"] == "analyze_lp_position"
    assert "current_price" in data
    assert "in_range" in data
    assert "impermanent_loss_pct" in data


def test_tool_rebalancing_rebalance():
    r = client.get("/api/tools/rebalancing/rebalance_range?risk_tolerance=aggressive")
    assert r.status_code == 200
    data = r.json()
    assert data["tool"] == "rebalance_range"
    assert "suggested_range" in data
    assert "volatility_estimate" in data
    assert data["risk_tolerance"] == "aggressive"


def test_tool_grid_build():
    r = client.get("/api/tools/grid/build_grid?capital_usd=10000&levels=12")
    assert r.status_code == 200
    data = r.json()
    assert data["tool"] == "build_grid"
    assert data["levels"] == 12
    assert data["capital_usd"] == 10000
    assert len(data["grid_levels"]) == 12


def test_tool_grid_pnl():
    r = client.get("/api/tools/grid/grid_pnl")
    assert r.status_code == 200
    data = r.json()
    assert data["tool"] == "grid_pnl"
    assert "realized_pnl_usd" in data
    assert "unrealized_pnl_usd" in data


def test_tool_yield_scan():
    r = client.get("/api/tools/yield/scan_yields?asset=BNB")
    assert r.status_code == 200
    data = r.json()
    assert data["tool"] == "scan_yields"
    assert data["venue_count"] > 0
    assert "best_apr_pct" in data


def test_tool_yield_route():
    r = client.get("/api/tools/yield/route_optimal?capital_usd=5000&asset=BNB")
    assert r.status_code == 200
    data = r.json()
    assert data["tool"] == "route_optimal"
    assert "blended_expected_apr_pct" in data
    assert "allocation" in data


def test_tool_health_check():
    r = client.get("/api/tools/health/check_health_factor?collateral_bnb=10&borrowed_usdt=2500")
    assert r.status_code == 200
    data = r.json()
    assert data["tool"] == "check_health_factor"
    assert "health_factor" in data
    assert "status" in data


def test_tool_health_risk():
    r = client.get("/api/tools/health/liquidation_risk?stress_pct=30")
    assert r.status_code == 200
    data = r.json()
    assert data["tool"] == "liquidation_risk"
    assert "liquidation_prices" in data
    assert "stress_test" in data


def test_tool_health_deleverage():
    r = client.get("/api/tools/health/recommend_deleveraging?target_hf=2.0")
    assert r.status_code == 200
    data = r.json()
    assert data["tool"] == "recommend_deleveraging"
    assert "steps" in data
    assert "new_health_factor" in data


def test_agents_by_category():
    r = client.get("/api/agents/by-category")
    assert r.status_code == 200
    data = r.json()
    assert "categories" in data
    assert len(data["categories"]) == 4
    # reference agents should appear in their categories
    rebal = data["categories"]["rebalancing"]["agents"]
    assert any(a.get("is_reference") for a in rebal)


def test_advantage_report():
    r = client.get("/api/advantage-report")
    assert r.status_code == 200
    data = r.json()
    assert data["requirements_met"]["min_3_tasks_both_ways"] is True
    assert data["requirements_met"]["at_least_one_trading_stock_security"] is True
    assert len(data["tasks"]) >= 3
    assert data["summary"]["average_speedup_factor"] > 1


def test_ui_root():
    r = client.get("/")
    assert r.status_code == 200
    assert "BNB Agent Marketplace" in r.text
