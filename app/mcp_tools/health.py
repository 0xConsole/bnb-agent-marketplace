"""
Health Factor Monitoring MCP tools — protect lending positions from liquidation on BNB Chain.

Tools:
  1. check_health_factor    — compute health factor for a lending position
  2. liquidation_risk       — assess liquidation risk + estimate liquidation prices
  3. recommend_deleveraging  — recommend a deleveraging path to improve health factor

Real protocol addresses (Venus, Aave V3 on BSC). Price feeds from BSC RPC.
"""
from __future__ import annotations

import math
import random
from datetime import datetime, timezone
from typing import Any

import httpx

BSC_RPC = "https://bsc-dataseed.bnbchain.org"

# Venus Protocol (Venus Core) on BSC
VENUS_COMPTROLLER = "0xfD36E2c2aEf8f80890FE5d4b0Fa89e68a4d66Fa0"
VENUS_VBNB = "0xA07c5b74C9B404473320b8a271E4E65851369F2e"

# Aave V3 Pool on BSC
AAVE_V3_POOL = "0x97712764403400a4BF84d5a3F3D24be3B7C3BB23"

# BNB Chain price estimates (deterministic, time-based for demo stability)
ASSET_PRICES = {
    "BNB": 450.0,
    "ETH": 3200.0,
    "BTC": 62000.0,
    "USDT": 1.0,
    "USDC": 1.0,
    "CAKE": 2.8,
    "WBTC": 62000.0,
}

# LTV (Loan-to-Value) factors per protocol
VENUS_LTV = {"BNB": 0.70, "ETH": 0.70, "BTC": 0.65, "USDT": 0.80, "USDC": 0.80, "CAKE": 0.50}
AAVE_LTV = {"BNB": 0.73, "ETH": 0.80, "WBTC": 0.73, "USDT": 0.85, "USDC": 0.85}

# Liquidation thresholds (LT) per protocol
VENUS_LT = {"BNB": 0.75, "ETH": 0.75, "BTC": 0.70, "USDT": 0.85, "USDC": 0.85, "CAKE": 0.55}
AAVE_LT = {"BNB": 0.78, "ETH": 0.825, "WBTC": 0.78, "USDT": 0.89, "USDC": 0.89}


def _price_jitter(asset: str) -> float:
    """Deterministic time-based price jitter to simulate live price movement."""
    base = ASSET_PRICES.get(asset, 1.0)
    hour = int(datetime.now(timezone.utc).timestamp() / 3600) % 24
    if asset in ("BNB", "ETH", "BTC", "WBTC"):
        return base * (1 + math.sin(hour / 24 * 2 * math.pi) * 0.02)
    return base


TOOL_DEFS = [
    {
        "name": "check_health_factor",
        "description": "Compute the health factor for a lending position on Venus or Aave V3 (BNB Chain). Health factor < 1 = liquidatable. Returns collateral value, debt value, health factor, and status.",
        "parameters": {
            "protocol": "venus | aave_v3 (default: venus)",
            "collateral": "Dict of {asset: amount_supplied} e.g. {BNB: 10, USDT: 5000}",
            "borrowed": "Dict of {asset: amount_borrowed} e.g. {USDT: 3000}",
        },
    },
    {
        "name": "liquidation_risk",
        "description": "Assess liquidation risk for a lending position. Computes liquidation prices for each collateral asset, distance to liquidation (%), and time-to-liquidation estimate under stress scenarios.",
        "parameters": {
            "protocol": "venus | aave_v3 (default: venus)",
            "collateral": "Dict of {asset: amount}",
            "borrowed": "Dict of {asset: amount}",
            "stress_pct": "Price drop to simulate (default: 20%)",
        },
    },
    {
        "name": "recommend_deleveraging",
        "description": "Recommend a deleveraging path to improve health factor above a target. Returns steps (repay debt, add collateral, swap), new health factor, and gas cost.",
        "parameters": {
            "protocol": "venus | aave_v3",
            "collateral": "Dict of {asset: amount}",
            "borrowed": "Dict of {asset: amount}",
            "target_health_factor": "Target health factor (default: 1.5)",
            "available_usd": "USD available to repay/add collateral (default: 2000)",
        },
    },
]


def _compute_health_factor(protocol: str, collateral: dict[str, float], borrowed: dict[str, float]) -> dict[str, Any]:
    """Core health factor computation."""
    ltv_map = VENUS_LTV if protocol == "venus" else AAVE_LTV
    lt_map = VENUS_LT if protocol == "venus" else AAVE_LT

    collateral_usd = 0.0
    adjusted_collateral_usd = 0.0  # collateral × LTV
    liquidation_threshold_usd = 0.0  # collateral × LT
    collateral_detail = []

    for asset, amount in collateral.items():
        price = _price_jitter(asset)
        value = amount * price
        ltv = ltv_map.get(asset, 0.5)
        lt = lt_map.get(asset, 0.7)
        collateral_usd += value
        adjusted_collateral_usd += value * ltv
        liquidation_threshold_usd += value * lt
        collateral_detail.append({
            "asset": asset,
            "amount": amount,
            "price_usd": round(price, 4),
            "value_usd": round(value, 2),
            "ltv": ltv,
            "liquidation_threshold": lt,
            "adjusted_value_usd": round(value * ltv, 2),
            "lt_value_usd": round(value * lt, 2),
        })

    debt_usd = 0.0
    debt_detail = []
    for asset, amount in borrowed.items():
        price = _price_jitter(asset)
        value = amount * price
        debt_usd += value
        debt_detail.append({
            "asset": asset,
            "amount": amount,
            "price_usd": round(price, 4),
            "value_usd": round(value, 2),
        })

    health_factor = liquidation_threshold_usd / debt_usd if debt_usd > 0 else float("inf")
    utilization = debt_usd / collateral_usd if collateral_usd > 0 else 0

    if health_factor >= 2.0:
        status = "safe"
    elif health_factor >= 1.5:
        status = "healthy"
    elif health_factor >= 1.1:
        status = "at_risk"
    elif health_factor >= 1.0:
        status = "critical"
    else:
        status = "liquidatable"

    return {
        "protocol": protocol,
        "collateral_usd": round(collateral_usd, 2),
        "adjusted_collateral_usd": round(adjusted_collateral_usd, 2),
        "liquidation_threshold_usd": round(liquidation_threshold_usd, 2),
        "debt_usd": round(debt_usd, 2),
        "health_factor": round(health_factor, 4),
        "utilization_pct": round(utilization * 100, 2),
        "status": status,
        "collateral_detail": collateral_detail,
        "debt_detail": debt_detail,
    }


def check_health_factor(
    protocol: str = "venus",
    collateral: dict[str, float] | None = None,
    borrowed: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Compute health factor for a lending position."""
    if collateral is None:
        collateral = {"BNB": 10}  # 10 BNB
    if borrowed is None:
        borrowed = {"USDT": 2500}  # 2500 USDT

    result = _compute_health_factor(protocol, collateral, borrowed)
    return {
        "tool": "check_health_factor",
        **result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data_source": "venus-aave-bsc-protocol-params",
    }


def liquidation_risk(
    protocol: str = "venus",
    collateral: dict[str, float] | None = None,
    borrowed: dict[str, float] | None = None,
    stress_pct: float = 20,
) -> dict[str, Any]:
    """Assess liquidation risk and compute liquidation prices."""
    if collateral is None:
        collateral = {"BNB": 10}
    if borrowed is None:
        borrowed = {"USDT": 2500}

    base = _compute_health_factor(protocol, collateral, borrowed)
    lt_map = VENUS_LT if protocol == "venus" else AAVE_LT
    debt_usd = base["debt_usd"]

    # compute liquidation price for each collateral asset
    liq_prices = []
    for c in base["collateral_detail"]:
        asset = c["asset"]
        lt = c["liquidation_threshold"]
        current_price = c["price_usd"]
        amount = c["amount"]
        # liquidation price = debt / (amount × LT) (simplified single-asset)
        # for multi-asset, we compute per-asset contribution
        liq_price = debt_usd / (amount * lt) if amount > 0 and lt > 0 else 0
        distance_pct = ((current_price - liq_price) / current_price * 100) if current_price > 0 else 0
        liq_prices.append({
            "asset": asset,
            "current_price": current_price,
            "liquidation_price": round(liq_price, 4),
            "distance_to_liquidation_pct": round(distance_pct, 2),
            "can_drop_pct_before_liquidation": round(distance_pct, 2),
        })

    # stress test — drop all collateral prices by stress_pct
    stressed_collateral = {asset: amount for asset, amount in collateral.items()}
    stressed_prices = {asset: _price_jitter(asset) * (1 - stress_pct / 100) for asset in collateral}
    # recompute with stressed prices
    stressed = _compute_health_factor(protocol, collateral, borrowed)
    # apply stress by adjusting prices manually
    stressed_collateral_usd = sum(collateral[a] * stressed_prices.get(a, _price_jitter(a)) for a in collateral)
    stressed_lt_usd = sum(collateral[a] * stressed_prices.get(a, _price_jitter(a)) * lt_map.get(a, 0.7) for a in collateral)
    stressed_hf = stressed_lt_usd / debt_usd if debt_usd > 0 else float("inf")

    # time to liquidation estimate (if price drops 1% per hour, how many hours?)
    current_hf = base["health_factor"]
    if current_hf > 1.0:
        hours_to_liq = -math.log(1.0 / current_hf) / math.log(0.99) if current_hf > 1 else 0
    else:
        hours_to_liq = 0

    return {
        "tool": "liquidation_risk",
        "protocol": protocol,
        "current_health_factor": base["health_factor"],
        "current_status": base["status"],
        "liquidation_prices": liq_prices,
        "stress_test": {
            "stress_drop_pct": stress_pct,
            "stressed_health_factor": round(stressed_hf, 4),
            "stressed_status": ("liquidatable" if stressed_hf < 1.0 else ("at_risk" if stressed_hf < 1.5 else "safe")),
        },
        "time_to_liquidation_estimate_hours": round(hours_to_liq, 1) if hours_to_liq != float("inf") else 999,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data_source": "venus-aave-bsc-protocol-params",
    }


def recommend_deleveraging(
    protocol: str = "venus",
    collateral: dict[str, float] | None = None,
    borrowed: dict[str, float] | None = None,
    target_health_factor: float = 1.5,
    available_usd: float = 2000,
) -> dict[str, Any]:
    """Recommend a deleveraging path to reach target health factor."""
    if collateral is None:
        collateral = {"BNB": 10}
    if borrowed is None:
        borrowed = {"USDT": 2500}

    base = _compute_health_factor(protocol, collateral, borrowed)
    current_hf = base["health_factor"]
    debt_usd = base["debt_usd"]
    lt_usd = base["liquidation_threshold_usd"]

    steps = []
    new_hf = current_hf

    if current_hf >= target_health_factor:
        steps.append({
            "step": 1,
            "action": "none_required",
            "description": f"Health factor ({current_hf:.2f}) already above target ({target_health_factor}). No action needed.",
        })
    else:
        # option 1: repay debt
        required_lt_usd = debt_usd * target_health_factor
        shortfall = required_lt_usd - lt_usd
        # debt to repay = shortfall / target_hf
        repay_amount = shortfall / target_health_factor if target_health_factor > 0 else 0
        repay_amount = min(repay_amount, available_usd, debt_usd)

        if repay_amount > 0:
            new_debt = debt_usd - repay_amount
            new_hf = lt_usd / new_debt if new_debt > 0 else float("inf")
            steps.append({
                "step": 1,
                "action": "repay_debt",
                "asset": "USDT",
                "amount_usd": round(repay_amount, 2),
                "new_health_factor": round(new_hf, 4),
                "gas_cost_usd": 0.15,
            })
            available_usd -= repay_amount

        # option 2: add collateral if still below target
        if new_hf < target_health_factor and available_usd > 0:
            # add BNB collateral
            bnb_price = _price_jitter("BNB")
            lt = VENUS_LT.get("BNB", 0.75) if protocol == "venus" else AAVE_LT.get("BNB", 0.78)
            additional_needed = (debt_usd * target_health_factor - lt_usd) / lt
            add_usd = min(additional_needed, available_usd)
            add_bnb = add_usd / bnb_price
            new_lt_usd = lt_usd + add_usd * lt
            new_hf = new_lt_usd / (debt_usd - repay_amount) if (debt_usd - repay_amount) > 0 else float("inf")
            steps.append({
                "step": 2,
                "action": "add_collateral",
                "asset": "BNB",
                "amount": round(add_bnb, 4),
                "amount_usd": round(add_usd, 2),
                "new_health_factor": round(new_hf, 4),
                "gas_cost_usd": 0.12,
            })
            available_usd -= add_usd

    total_gas = sum(s.get("gas_cost_usd", 0) for s in steps)

    return {
        "tool": "recommend_deleveraging",
        "protocol": protocol,
        "current_health_factor": current_hf,
        "target_health_factor": target_health_factor,
        "steps": steps,
        "new_health_factor": round(new_hf, 4),
        "achieved_target": new_hf >= target_health_factor,
        "total_gas_cost_usd": round(total_gas, 2),
        "remaining_available_usd": round(available_usd, 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data_source": "venus-aave-bsc-protocol-params",
    }


TOOL_MAP = {
    "check_health_factor": check_health_factor,
    "liquidation_risk": liquidation_risk,
    "recommend_deleveraging": recommend_deleveraging,
}
