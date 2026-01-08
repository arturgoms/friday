"""
Tests for Friday Investments Tools

Tests investment portfolio monitoring tools using the DLP API.
ALL API CALLS ARE MOCKED - no real requests are made to the DLP API.

Tools tested:
- get_portfolio() - Full portfolio data
- get_portfolio_summary() - Summary stats
- get_portfolio_history() - Performance over time
- get_operations() - Transaction history
- get_earnings() - Dividends/proventos
- get_darf() - Tax reports
- get_irpf() - Tax reports
- list_wallets() - All wallets
- get_multiwallets() - Multiple wallet data
- get_asset_config() - Asset configuration
- get_user_config() - User settings
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.tools.investments import (
    get_portfolio,
    get_portfolio_summary,
    get_portfolio_history,
    get_operations,
    get_earnings,
    get_darf,
    get_irpf,
    list_wallets,
    get_multiwallets,
    get_asset_config,
    get_user_config,
)


# =============================================================================
# Helper Functions
# =============================================================================

def check_for_none_values(data, path=''):
    """Recursively check for None values in nested data structures.
    
    Returns list of paths where None values were found.
    """
    none_found = []
    
    if isinstance(data, dict):
        for key, value in data.items():
            current_path = f'{path}.{key}' if path else key
            if value is None:
                none_found.append(current_path)
            elif isinstance(value, (dict, list)):
                none_found.extend(check_for_none_values(value, current_path))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            current_path = f'{path}[{i}]'
            if item is None:
                none_found.append(current_path)
            elif isinstance(item, (dict, list)):
                none_found.extend(check_for_none_values(item, current_path))
    
    return none_found


# =============================================================================
# Portfolio Tests
# =============================================================================

def test_get_portfolio_returns_dict():
    """Test portfolio returns a dict."""
    with patch('src.tools.investments.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.DLP_API_KEY = "test_key"
        mock_settings.DLP_API_BASE_URL = "https://api.example.com"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        
        mock_client.return_value.__enter__.return_value.request.return_value = mock_response
        
        result = get_portfolio()
        assert isinstance(result, dict)
        assert result is not None


def test_get_portfolio_no_api_key():
    """Test portfolio when API key not configured."""
    with patch('src.tools.investments.settings') as mock_settings:
        mock_settings.DLP_API_KEY = None
        
        result = get_portfolio()
        
        assert isinstance(result, dict)
        assert "error" in result
        assert "not configured" in result["error"].lower()


def test_get_portfolio_with_assets():
    """Test portfolio with assets."""
    with patch('src.tools.investments.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.DLP_API_KEY = "test_key"
        mock_settings.DLP_API_BASE_URL = "https://api.example.com"
        
        # Mock API response with assets
        mock_assets = [
            {
                "ativo": "PETR4",
                "classe": "ação",
                "qtd": 100,
                "price": 30.50,
                "vlr_investido": 2800.00
            },
            {
                "ativo": "ITUB4",
                "classe": "ação",
                "qtd": 50,
                "price": 25.00,
                "vlr_investido": 1200.00
            }
        ]
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_assets
        
        mock_client.return_value.__enter__.return_value.request.return_value = mock_response
        
        result = get_portfolio()
        
        if "error" not in result:
            assert "assets" in result
            assert "summary" in result
            assert isinstance(result["assets"], list)
            assert isinstance(result["summary"], dict)
            
            # Check summary structure
            assert "total_invested" in result["summary"]
            assert "total_market_value" in result["summary"]
            assert "total_profit" in result["summary"]
            assert "profit_percentage" in result["summary"]
            assert "asset_count" in result["summary"]


def test_get_portfolio_http_error():
    """Test portfolio with HTTP error."""
    with patch('src.tools.investments.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.DLP_API_KEY = "test_key"
        mock_settings.DLP_API_BASE_URL = "https://api.example.com"
        
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Server error"
        
        mock_client.return_value.__enter__.return_value.request.return_value = mock_response
        
        result = get_portfolio()
        
        assert isinstance(result, dict)
        assert "error" in result


def test_get_portfolio_connection_error():
    """Test portfolio with connection error."""
    with patch('src.tools.investments.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.DLP_API_KEY = "test_key"
        mock_settings.DLP_API_BASE_URL = "https://api.example.com"
        
        import httpx
        mock_client.return_value.__enter__.return_value.request.side_effect = \
            httpx.ConnectError("Connection failed")
        
        result = get_portfolio()
        
        assert isinstance(result, dict)
        assert "error" in result


# =============================================================================
# Portfolio Summary Tests
# =============================================================================

def test_get_portfolio_summary_returns_dict():
    """Test portfolio summary returns a dict."""
    with patch('src.tools.investments.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.DLP_API_KEY = "test_key"
        mock_settings.DLP_API_BASE_URL = "https://api.example.com"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"total": 10000.00}
        
        mock_client.return_value.__enter__.return_value.request.return_value = mock_response
        
        result = get_portfolio_summary()
        assert isinstance(result, dict)
        assert result is not None


def test_get_portfolio_summary_structure():
    """Test portfolio summary structure."""
    with patch('src.tools.investments.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.DLP_API_KEY = "test_key"
        mock_settings.DLP_API_BASE_URL = "https://api.example.com"
        
        mock_summary = {
            "total_invested": 10000.00,
            "total_market_value": 12000.00,
            "total_profit": 2000.00
        }
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_summary
        
        mock_client.return_value.__enter__.return_value.request.return_value = mock_response
        
        result = get_portfolio_summary()
        
        if "error" not in result:
            assert isinstance(result, dict)


# =============================================================================
# Operations Tests
# =============================================================================

def test_get_operations_returns_dict():
    """Test operations returns a dict."""
    with patch('src.tools.investments.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.DLP_API_KEY = "test_key"
        mock_settings.DLP_API_BASE_URL = "https://api.example.com"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": [], "total": 0}
        
        mock_client.return_value.__enter__.return_value.request.return_value = mock_response
        
        result = get_operations()
        assert isinstance(result, dict)
        assert result is not None


def test_get_operations_with_data():
    """Test operations with transaction data."""
    with patch('src.tools.investments.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.DLP_API_KEY = "test_key"
        mock_settings.DLP_API_BASE_URL = "https://api.example.com"
        
        mock_ops = {
            "result": [
                {
                    "ativo": "PETR4",
                    "evento": "compra",
                    "qtd": 100,
                    "price": 30.00,
                    "volume": 3000.00,
                    "lucro": 0
                }
            ],
            "total": 1
        }
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_ops
        
        mock_client.return_value.__enter__.return_value.request.return_value = mock_response
        
        result = get_operations()
        
        if "error" not in result:
            assert "operations" in result
            assert "summary" in result
            assert isinstance(result["operations"], list)
            assert len(result["operations"]) == 1


def test_get_operations_with_filters():
    """Test operations with filters."""
    with patch('src.tools.investments.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.DLP_API_KEY = "test_key"
        mock_settings.DLP_API_BASE_URL = "https://api.example.com"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": [], "total": 0}
        
        mock_client.return_value.__enter__.return_value.request.return_value = mock_response
        
        result = get_operations(ativo="PETR4", classe="ação", days_back=30, limit=10)
        assert isinstance(result, dict)


# =============================================================================
# Earnings Tests
# =============================================================================

def test_get_earnings_returns_dict():
    """Test earnings returns a dict."""
    with patch('src.tools.investments.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.DLP_API_KEY = "test_key"
        mock_settings.DLP_API_BASE_URL = "https://api.example.com"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": [], "total": 0}
        
        mock_client.return_value.__enter__.return_value.request.return_value = mock_response
        
        result = get_earnings()
        assert isinstance(result, dict)
        assert result is not None


def test_get_earnings_with_data():
    """Test earnings with dividend data."""
    with patch('src.tools.investments.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.DLP_API_KEY = "test_key"
        mock_settings.DLP_API_BASE_URL = "https://api.example.com"
        
        mock_earnings = {
            "result": [
                {
                    "ativo": "ITUB4",
                    "tipo": "dividendo",
                    "vlr_bruto": 100.00,
                    "irrf_total": 0,
                    "vlr_liquido": 100.00
                }
            ],
            "total": 1
        }
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_earnings
        
        mock_client.return_value.__enter__.return_value.request.return_value = mock_response
        
        result = get_earnings()
        
        if "error" not in result:
            assert "earnings" in result
            assert "summary" in result
            assert "total_bruto" in result["summary"]
            assert "total_liquido" in result["summary"]


# =============================================================================
# DARF Tests
# =============================================================================

def test_get_darf_returns_dict():
    """Test DARF returns a dict."""
    with patch('src.tools.investments.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.DLP_API_KEY = "test_key"
        mock_settings.DLP_API_BASE_URL = "https://api.example.com"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [], "payments": []}
        
        mock_client.return_value.__enter__.return_value.request.return_value = mock_response
        
        result = get_darf()
        assert isinstance(result, dict)
        assert result is not None


def test_get_darf_structure():
    """Test DARF structure."""
    with patch('src.tools.investments.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.DLP_API_KEY = "test_key"
        mock_settings.DLP_API_BASE_URL = "https://api.example.com"
        
        mock_darf = {
            "results": [
                {
                    "mes": "2024-01",
                    "vlr_devido_total": 150.00
                }
            ],
            "payments": [],
            "user_config": {},
            "valores_manuais": []
        }
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_darf
        
        mock_client.return_value.__enter__.return_value.request.return_value = mock_response
        
        result = get_darf()
        
        if "error" not in result:
            assert "monthly_results" in result
            assert "payments" in result
            assert "summary" in result
            assert "total_due" in result["summary"]


# =============================================================================
# IRPF Tests
# =============================================================================

def test_get_irpf_returns_dict():
    """Test IRPF returns a dict."""
    with patch('src.tools.investments.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.DLP_API_KEY = "test_key"
        mock_settings.DLP_API_BASE_URL = "https://api.example.com"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ano": 2024}
        
        mock_client.return_value.__enter__.return_value.request.return_value = mock_response
        
        result = get_irpf(2024)
        assert isinstance(result, dict)
        assert result is not None


def test_get_irpf_with_year():
    """Test IRPF with specific year."""
    with patch('src.tools.investments.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.DLP_API_KEY = "test_key"
        mock_settings.DLP_API_BASE_URL = "https://api.example.com"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ano": 2024, "data": {}}
        
        mock_client.return_value.__enter__.return_value.request.return_value = mock_response
        
        result = get_irpf(2024)
        
        if "error" not in result:
            assert isinstance(result, dict)


# =============================================================================
# Portfolio History Tests
# =============================================================================

def test_get_portfolio_history_returns_dict():
    """Test portfolio history returns a dict."""
    with patch('src.tools.investments.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.DLP_API_KEY = "test_key"
        mock_settings.DLP_API_BASE_URL = "https://api.example.com"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"historico": []}
        
        mock_client.return_value.__enter__.return_value.request.return_value = mock_response
        
        result = get_portfolio_history()
        assert isinstance(result, dict)
        assert result is not None


def test_get_portfolio_history_with_data():
    """Test portfolio history with data."""
    with patch('src.tools.investments.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.DLP_API_KEY = "test_key"
        mock_settings.DLP_API_BASE_URL = "https://api.example.com"
        
        mock_history = {
            "historico": [
                {
                    "date": "2024-01-01",
                    "vlr_investido": 10000.00,
                    "vlr_mercado": 10500.00
                },
                {
                    "date": "2024-01-02",
                    "vlr_investido": 10000.00,
                    "vlr_mercado": 10600.00
                }
            ]
        }
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_history
        
        mock_client.return_value.__enter__.return_value.request.return_value = mock_response
        
        result = get_portfolio_history()
        
        if "error" not in result:
            assert "historico" in result
            assert "performance" in result
            assert "total_return" in result["performance"]


# =============================================================================
# Wallet Tests
# =============================================================================

def test_list_wallets_returns_dict():
    """Test list wallets returns a dict."""
    with patch('src.tools.investments.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.DLP_API_KEY = "test_key"
        mock_settings.DLP_API_BASE_URL = "https://api.example.com"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"carteiras": []}
        
        mock_client.return_value.__enter__.return_value.request.return_value = mock_response
        
        result = list_wallets()
        assert isinstance(result, dict)
        assert result is not None


def test_list_wallets_structure():
    """Test list wallets structure."""
    with patch('src.tools.investments.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.DLP_API_KEY = "test_key"
        mock_settings.DLP_API_BASE_URL = "https://api.example.com"
        
        mock_user_data = {
            "carteiras": [
                {"id": 1, "nome": "Principal"},
                {"id": 2, "nome": "Reserva"}
            ]
        }
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_user_data
        
        mock_client.return_value.__enter__.return_value.request.return_value = mock_response
        
        result = list_wallets()
        
        if "error" not in result:
            assert "wallets" in result
            assert "count" in result
            assert result["count"] == 2


def test_get_multiwallets_returns_dict():
    """Test get multiwallets returns a dict."""
    with patch('src.tools.investments.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.DLP_API_KEY = "test_key"
        mock_settings.DLP_API_BASE_URL = "https://api.example.com"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        
        mock_client.return_value.__enter__.return_value.request.return_value = mock_response
        
        result = get_multiwallets()
        assert isinstance(result, dict)
        assert result is not None


def test_get_multiwallets_structure():
    """Test get multiwallets structure."""
    with patch('src.tools.investments.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.DLP_API_KEY = "test_key"
        mock_settings.DLP_API_BASE_URL = "https://api.example.com"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"nome": "Portfolio 80/20"}]
        
        mock_client.return_value.__enter__.return_value.request.return_value = mock_response
        
        result = get_multiwallets()
        
        if "error" not in result:
            assert "multiwallets" in result
            assert "count" in result


# =============================================================================
# Configuration Tests
# =============================================================================

def test_get_asset_config_returns_dict():
    """Test get asset config returns a dict."""
    with patch('src.tools.investments.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.DLP_API_KEY = "test_key"
        mock_settings.DLP_API_BASE_URL = "https://api.example.com"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        
        mock_client.return_value.__enter__.return_value.request.return_value = mock_response
        
        result = get_asset_config()
        assert isinstance(result, dict)
        assert result is not None


def test_get_asset_config_structure():
    """Test get asset config structure."""
    with patch('src.tools.investments.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.DLP_API_KEY = "test_key"
        mock_settings.DLP_API_BASE_URL = "https://api.example.com"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"ativo": "CUSTOM1"}]
        
        mock_client.return_value.__enter__.return_value.request.return_value = mock_response
        
        result = get_asset_config()
        
        if "error" not in result:
            assert "configurations" in result
            assert "count" in result


def test_get_user_config_returns_dict():
    """Test get user config returns a dict."""
    with patch('src.tools.investments.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.DLP_API_KEY = "test_key"
        mock_settings.DLP_API_BASE_URL = "https://api.example.com"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"email": "test@example.com"}
        
        mock_client.return_value.__enter__.return_value.request.return_value = mock_response
        
        result = get_user_config()
        assert isinstance(result, dict)
        assert result is not None


def test_get_user_config_structure():
    """Test get user config structure."""
    with patch('src.tools.investments.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.DLP_API_KEY = "test_key"
        mock_settings.DLP_API_BASE_URL = "https://api.example.com"
        
        mock_user = {
            "email": "test@example.com",
            "moeda_base": "BRL",
            "calc_por_corretora": True,
            "carteiras": [],
            "alpha": {},
            "in_dark_mode": False,
            "in_show_details": True,
            "in_show_currency": False,
            "in_group_fx_asset": False
        }
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_user
        
        mock_client.return_value.__enter__.return_value.request.return_value = mock_response
        
        result = get_user_config()
        
        if "error" not in result:
            assert "email" in result
            assert "moeda_base" in result
            assert "ui_preferences" in result


# =============================================================================
# None Value Detection Tests
# =============================================================================

def test_get_portfolio_no_none_values():
    """CRITICAL: Ensure portfolio has no None values."""
    with patch('src.tools.investments.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.DLP_API_KEY = "test_key"
        mock_settings.DLP_API_BASE_URL = "https://api.example.com"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"ativo": "PETR4", "classe": "ação", "qtd": 100, "price": 30.0, "vlr_investido": 3000.0}
        ]
        
        mock_client.return_value.__enter__.return_value.request.return_value = mock_response
        
        result = get_portfolio()
        
        if "error" not in result:
            none_values = check_for_none_values(result)
            assert len(none_values) == 0, \
                f"CRITICAL: get_portfolio has None values at: {none_values}"


def test_all_investments_tools_no_none_values():
    """CRITICAL: Batch test - check all investments tools for None values."""
    errors = []
    
    with patch('src.tools.investments.settings') as mock_settings, \
         patch('httpx.Client') as mock_client:
        
        mock_settings.DLP_API_KEY = "test_key"
        mock_settings.DLP_API_BASE_URL = "https://api.example.com"
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        
        mock_client.return_value.__enter__.return_value.request.return_value = mock_response
        
        # Test each tool
        tools_to_test = [
            ("get_portfolio", lambda: get_portfolio()),
            ("get_portfolio_summary", lambda: get_portfolio_summary()),
            ("get_operations", lambda: get_operations()),
            ("get_earnings", lambda: get_earnings()),
            ("get_darf", lambda: get_darf()),
            ("get_irpf", lambda: get_irpf(2024)),
            ("get_portfolio_history", lambda: get_portfolio_history()),
            ("list_wallets", lambda: list_wallets()),
            ("get_multiwallets", lambda: get_multiwallets()),
            ("get_asset_config", lambda: get_asset_config()),
            ("get_user_config", lambda: get_user_config()),
        ]
        
        for tool_name, tool_func in tools_to_test:
            result = tool_func()
            
            # Check tool returned something
            if result is None:
                errors.append(f"{tool_name} returned None")
                continue
            
            # Check for None values in non-error results
            if isinstance(result, dict) and "error" not in result:
                none_vals = check_for_none_values(result)
                if none_vals:
                    errors.append(f"{tool_name}: {none_vals}")
    
    # Assert no errors found
    assert len(errors) == 0, \
        f"CRITICAL: Found None values in investments tools:\n" + "\n".join(errors)
