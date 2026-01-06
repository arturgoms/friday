"""
Friday Investments Tools

Read-only investment portfolio monitoring tools using Dlombello Planilhas API.
Provides access to portfolio data, operations history, earnings (dividends), 
tax reporting, and portfolio analytics.

All tools are read-only - no write operations are available to prevent
accidental modifications to investment data.
"""

import sys
from pathlib import Path

# Add parent directory to path to import agent
_parent_dir = Path(__file__).parent.parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

from src.core.agent import agent

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

from settings import settings

logger = logging.getLogger(__name__)


# =============================================================================
# API Helper Functions
# =============================================================================


def _make_request(
    method: str,
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    json_data: Optional[Any] = None,
) -> Dict[str, Any]:
    """Make authenticated request to DLP API.
    
    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        endpoint: API endpoint (e.g., "/carteira")
        params: Query parameters
        json_data: JSON body data
        
    Returns:
        Response data as dict
    """
    if not settings.DLP_API_KEY:
        return {"error": "DLP_API_KEY not configured"}
    
    url = f"{settings.DLP_API_BASE_URL}{endpoint}"
    headers = {
        "Authorization": f"Bearer {settings.DLP_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.request(
                method=method,
                url=url,
                headers=headers,
                params=params or {},
                json=json_data
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"DLP API error: {response.status_code} - {response.text}")
                return {"error": f"API returned status {response.status_code}"}
                
    except Exception as e:
        logger.error(f"Error calling DLP API: {e}")
        return {"error": str(e)}


# =============================================================================
# Portfolio & Wallet Tools
# =============================================================================


@agent.tool_plain
def get_portfolio() -> Dict[str, Any]:
    """Get current investment portfolio with all positions.
    
    Returns portfolio with assets, quantities, average prices, current values,
    profits/losses, and asset allocation.
    
    Returns:
        Dict with portfolio positions and summary
    """
    result = _make_request("GET", "/carteira")
    
    if "error" in result:
        return result
    
    # Calculate summary stats
    if isinstance(result, list) and len(result) > 0:
        total_invested = sum(item.get("vlr_investido", 0) for item in result)
        total_market = sum(item.get("qtd", 0) * item.get("price", 0) for item in result)
        total_profit = total_market - total_invested if total_market > 0 else 0
        
        # Group by asset class
        by_class = {}
        for item in result:
            classe = item.get("classe", "N/D")
            if classe not in by_class:
                by_class[classe] = {
                    "invested": 0,
                    "market_value": 0,
                    "count": 0
                }
            by_class[classe]["invested"] += item.get("vlr_investido", 0)
            by_class[classe]["market_value"] += item.get("qtd", 0) * item.get("price", 0)
            by_class[classe]["count"] += 1
        
        return {
            "assets": result,
            "summary": {
                "total_invested": round(total_invested, 2),
                "total_market_value": round(total_market, 2),
                "total_profit": round(total_profit, 2),
                "profit_percentage": round((total_profit / total_invested * 100) if total_invested > 0 else 0, 2),
                "asset_count": len(result),
                "by_class": by_class
            }
        }
    
    return result


@agent.tool_plain
def get_portfolio_summary() -> Dict[str, Any]:
    """Get portfolio summary with key metrics and statistics.
    
    Returns aggregated portfolio performance, profits, earnings, and allocation.
    
    Returns:
        Dict with summary metrics
    """
    result = _make_request("GET", "/resumo", params={"summary": True, "wallet": True})
    
    if "error" in result:
        return result
    
    return result


@agent.tool_plain
def list_wallets() -> Dict[str, Any]:
    """List all investment wallets/portfolios.
    
    Returns:
        Dict with list of wallets
    """
    # Get user data which includes wallets
    result = _make_request("GET", "/usuario")
    
    if "error" in result:
        return result
    
    wallets = result.get("carteiras", [])
    return {
        "wallets": wallets,
        "count": len(wallets)
    }


# =============================================================================
# Operations Tools
# =============================================================================


@agent.tool_plain
def get_operations(
    ativo: Optional[str] = None,
    classe: Optional[str] = None,
    days_back: int = 90,
    limit: int = 50
) -> Dict[str, Any]:
    """Get investment operations (buy/sell transactions).
    
    Args:
        ativo: Filter by specific asset (ticker)
        classe: Filter by asset class (ação, fii, cripto, etc)
        days_back: Look back period in days (default: 90)
        limit: Maximum number of operations to return
        
    Returns:
        Dict with list of operations and summary
    """
    date_ini = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    
    params = {
        "date_ini": date_ini,
        "qtd_pagina": limit,
        "order_date_asc": False
    }
    
    if ativo:
        params["ativo"] = ativo.upper()
    if classe:
        params["classe"] = classe
    
    result = _make_request("GET", "/operacoes", params=params)
    
    if "error" in result:
        return result
    
    operations = result.get("result", [])
    
    # Calculate summary
    buy_volume = sum(op.get("volume", 0) for op in operations if op.get("evento") in ["compra", "buy"])
    sell_volume = sum(op.get("volume", 0) for op in operations if op.get("evento") in ["venda", "sell"])
    total_profit = sum(op.get("lucro", 0) for op in operations)
    
    return {
        "operations": operations,
        "summary": {
            "total": result.get("total", 0),
            "returned": len(operations),
            "buy_volume": round(buy_volume, 2),
            "sell_volume": round(sell_volume, 2),
            "total_profit": round(total_profit, 2),
            "filtered_profit": result.get("filtered_profit", [])
        }
    }





# =============================================================================
# Earnings/Dividends Tools
# =============================================================================


@agent.tool_plain
def get_earnings(
    ativo: Optional[str] = None,
    days_back: int = 365,
    limit: int = 100
) -> Dict[str, Any]:
    """Get dividend/earnings history (proventos).
    
    Returns dividends, JCP (interest on equity), and other earnings received.
    
    Args:
        ativo: Filter by specific asset
        days_back: Look back period in days (default: 365)
        limit: Maximum number of records
        
    Returns:
        Dict with earnings history and totals
    """
    date_ini = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    
    params = {
        "date_ini": date_ini,
        "qtd_pagina": limit,
        "order_date_asc": False
    }
    
    if ativo:
        params["ativo"] = ativo.upper()
    
    result = _make_request("GET", "/proventos", params=params)
    
    if "error" in result:
        return result
    
    earnings = result.get("result", [])
    
    # Calculate totals
    total_bruto = sum(e.get("vlr_bruto", 0) for e in earnings)
    total_irrf = sum(e.get("irrf_total", 0) for e in earnings)
    total_liquido = sum(e.get("vlr_liquido", 0) for e in earnings)
    
    return {
        "earnings": earnings,
        "summary": {
            "total_count": result.get("total", 0),
            "returned": len(earnings),
            "total_bruto": round(total_bruto, 2),
            "total_irrf": round(total_irrf, 2),
            "total_liquido": round(total_liquido, 2),
            "average_ttm": result.get("average_ttm_filtered", 0),
            "by_asset_type": result.get("summary_filtered", [])
        }
    }





# =============================================================================
# Tax & DARF Tools
# =============================================================================


@agent.tool_plain
def get_darf() -> Dict[str, Any]:
    """Get DARF tax report (Brazilian investment tax report).
    
    Returns monthly tax calculations for stock trades, day trades, and other operations.
    Shows amounts owed, exemptions, and payment status.
    
    Returns:
        Dict with DARF report and payment info
    """
    result = _make_request("GET", "/darf")
    
    if "error" in result:
        return result
    
    # Parse results for easy interpretation
    results = result.get("results", [])
    payments = result.get("payments", [])
    
    # Calculate totals
    total_due = sum(
        r.get("vlr_devido_total", 0) 
        for r in results 
        if isinstance(r, dict)
    )
    
    total_paid = sum(p.get("valor_pago", 0) for p in payments)
    
    return {
        "monthly_results": results,
        "payments": payments,
        "user_config": result.get("user_config", {}),
        "manual_values": result.get("valores_manuais", []),
        "summary": {
            "total_due": round(total_due, 2),
            "total_paid": round(total_paid, 2),
            "balance": round(total_due - total_paid, 2)
        }
    }


@agent.tool_plain
def get_irpf(ano: int) -> Dict[str, Any]:
    """Get IRPF (annual income tax) report data.
    
    Args:
        ano: Tax year (e.g., 2024)
        
    Returns:
        Dict with IRPF report for the year
    """
    result = _make_request("GET", "/dirpf", params={"ano": ano})
    
    if "error" in result:
        return result
    
    return result


# =============================================================================
# Historical Performance Tools
# =============================================================================


@agent.tool_plain
def get_portfolio_history(
    ativo: Optional[str] = None,
    classe: Optional[str] = None,
    days_back: int = 365
) -> Dict[str, Any]:
    """Get historical portfolio performance.
    
    Shows daily snapshots of portfolio value, positions, profits, and dividends over time.
    
    Args:
        ativo: Filter by specific asset
        classe: Filter by asset class
        days_back: Look back period in days
        
    Returns:
        Dict with historical data
    """
    date_ini = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    
    params = {
        "date_ini": date_ini
    }
    
    if ativo:
        params["ativo"] = ativo.upper()
    if classe:
        params["classe"] = classe
    
    result = _make_request("GET", "/historico", params=params)
    
    if "error" in result:
        return result
    
    # Extract data
    if isinstance(result, dict):
        historico = result.get("historico", [])
        
        # Calculate performance metrics
        if historico:
            initial_value = historico[0].get("vlr_investido", 0)
            final_value = historico[-1].get("vlr_mercado", 0)
            total_return = final_value - initial_value if final_value > 0 else 0
            return_pct = (total_return / initial_value * 100) if initial_value > 0 else 0
            
            return {
                "historico": historico,
                "current_month_operations": result.get("lucro_mes_atual", []),
                "current_month_earnings": result.get("proventos_mes_atual", []),
                "performance": {
                    "initial_value": round(initial_value, 2),
                    "final_value": round(final_value, 2),
                    "total_return": round(total_return, 2),
                    "return_percentage": round(return_pct, 2),
                    "days_tracked": len(historico)
                }
            }
    
    return result


# =============================================================================
# Multi-wallet & Allocation Tools
# =============================================================================


@agent.tool_plain
def get_multiwallets() -> Dict[str, Any]:
    """Get multi-wallet configurations and target allocations.
    
    Returns strategic allocation plans with target weights and rebalancing data.
    
    Returns:
        Dict with multi-wallet configurations
    """
    result = _make_request("GET", "/multicarteiras")
    
    if "error" in result:
        return result
    
    return {
        "multiwallets": result,
        "count": len(result) if isinstance(result, list) else 0
    }


# =============================================================================
# Asset Configuration Tools
# =============================================================================


@agent.tool_plain
def get_asset_config() -> Dict[str, Any]:
    """Get custom asset configurations (others/outros).
    
    Returns custom settings for assets not in the standard database,
    including custom classifications, sectors, and price update rules.
    
    Returns:
        Dict with asset configurations
    """
    result = _make_request("GET", "/outros")
    
    if "error" in result:
        return result
    
    return {
        "configurations": result,
        "count": len(result) if isinstance(result, list) else 0
    }


# =============================================================================
# User Configuration Tools
# =============================================================================


@agent.tool_plain
def get_user_config() -> Dict[str, Any]:
    """Get user configuration and preferences.
    
    Returns base currency, calculation settings, tax configuration, and other preferences.
    
    Returns:
        Dict with user configuration
    """
    result = _make_request("GET", "/usuario")
    
    if "error" in result:
        return result
    
    return {
        "email": result.get("email"),
        "moeda_base": result.get("moeda_base", "BRL"),
        "calc_por_corretora": result.get("calc_por_corretora", True),
        "wallets": result.get("carteiras", []),
        "alpha": result.get("alpha", {}),
        "ui_preferences": {
            "dark_mode": result.get("in_dark_mode", False),
            "show_details": result.get("in_show_details", False),
            "show_currency": result.get("in_show_currency", False),
            "group_fx_assets": result.get("in_group_fx_asset", False)
        }
    }
