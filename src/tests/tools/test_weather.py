"""
Tests for weather tools.

These tests mock httpx to avoid real API calls.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime


@pytest.fixture
def mock_weather_response():
    """Mock OpenWeatherMap API response."""
    return {
        'weather': [
            {'main': 'Clear', 'description': 'clear sky'}
        ],
        'main': {
            'temp': 22.5,
            'feels_like': 21.0,
            'humidity': 65,
            'pressure': 1013,
            'temp_min': 20.0,
            'temp_max': 25.0
        },
        'wind': {
            'speed': 3.5,
            'deg': 180
        },
        'clouds': {
            'all': 10
        },
        'name': 'Curitiba',
        'sys': {
            'country': 'BR',
            'sunrise': 1704700800,
            'sunset': 1704750000
        }
    }


@pytest.fixture
def mock_forecast_response():
    """Mock OpenWeatherMap forecast API response."""
    return {
        'list': [
            {
                'dt': 1704700800,
                'main': {
                    'temp': 22.5,
                    'temp_min': 20.0,
                    'temp_max': 25.0
                },
                'weather': [
                    {'main': 'Clear', 'description': 'clear sky'}
                ],
                'wind': {'speed': 3.5},
                'pop': 0.1
            },
            {
                'dt': 1704787200,
                'main': {
                    'temp': 24.0,
                    'temp_min': 22.0,
                    'temp_max': 26.0
                },
                'weather': [
                    {'main': 'Rain', 'description': 'light rain'}
                ],
                'wind': {'speed': 4.0},
                'pop': 0.6
            }
        ],
        'city': {'name': 'Curitiba', 'country': 'BR'}
    }


def test_get_current_weather_success(mock_weather_response):
    """Test successful current weather retrieval."""
    mock_response = Mock()
    mock_response.json.return_value = mock_weather_response
    mock_response.raise_for_status = Mock()
    
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        
        from src.tools.weather import get_current_weather
        
        result = get_current_weather()
        
        assert "Curitiba" in result
        assert "22.5°C" in result or "22.5" in result
        assert "Clear" in result or "clear" in result


def test_get_current_weather_custom_city(mock_weather_response):
    """Test current weather for custom city."""
    mock_response = Mock()
    mock_weather_response['name'] = 'São Paulo'
    mock_response.json.return_value = mock_weather_response
    mock_response.raise_for_status = Mock()
    
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        
        from src.tools.weather import get_current_weather
        
        result = get_current_weather("São Paulo")
        
        assert "São Paulo" in result


def test_get_current_weather_no_api_key():
    """Test weather tool with missing API key."""
    with patch('src.tools.weather.WEATHER_API_KEY', ''):
        from src.tools.weather import get_current_weather
        
        result = get_current_weather()
        
        assert "not configured" in result.lower() or "not set" in result.lower()


def test_get_current_weather_api_error():
    """Test handling of API errors."""
    import httpx
    
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.get.side_effect = \
            httpx.HTTPStatusError("Not Found", request=Mock(), response=Mock(status_code=404))
        
        from src.tools.weather import get_current_weather
        
        result = get_current_weather()
        
        assert "error" in result.lower() or "not found" in result.lower()


def test_get_weather_forecast_success(mock_forecast_response):
    """Test successful weather forecast retrieval."""
    mock_response = Mock()
    mock_response.json.return_value = mock_forecast_response
    mock_response.raise_for_status = Mock()
    
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        
        from src.tools.weather import get_weather_forecast
        
        result = get_weather_forecast()
        
        assert "Curitiba" in result
        assert "forecast" in result.lower() or "day" in result.lower()


def test_get_weather_forecast_with_days(mock_forecast_response):
    """Test forecast with specific number of days."""
    mock_response = Mock()
    mock_response.json.return_value = mock_forecast_response
    mock_response.raise_for_status = Mock()
    
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        
        from src.tools.weather import get_weather_forecast
        
        result = get_weather_forecast(hours=72)  # 3 days = 72 hours
        
        assert result is not None
        assert len(result) > 0


def test_weather_emoji_mapping():
    """Test weather emoji selection."""
    from src.tools.weather import _get_weather_emoji
    
    assert _get_weather_emoji("Clear") == "☀️"
    assert _get_weather_emoji("Clouds") == "☁️"
    assert _get_weather_emoji("Rain") == "🌧️"
    assert _get_weather_emoji("Snow") == "❄️"
    assert _get_weather_emoji("Thunderstorm") == "⛈️"
    assert _get_weather_emoji("Drizzle") == "🌦️"
    assert _get_weather_emoji("Mist") == "🌫️"


def test_temperature_formatting():
    """Test temperature formatting."""
    from src.tools.weather import _format_temp
    
    assert _format_temp(22.5) == "22.5°C"
    assert _format_temp(0) == "0.0°C"
    assert _format_temp(-5.3) == "-5.3°C"
