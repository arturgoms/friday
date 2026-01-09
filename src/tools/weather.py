"""
Friday 3.0 Weather Tools

Tools for getting weather information using OpenWeatherMap API.

Supports:
- Current weather (free tier - /data/2.5/weather)
- Weather forecast (free tier - /data/2.5/forecast)
- Historical weather by date (One Call 3.0 - /data/3.0/onecall/day_summary)
- Weather for any timestamp (One Call 3.0 - /data/3.0/onecall/timemachine)
- Weather overview with AI summary (One Call 3.0 - /data/3.0/onecall/overview)

API Limit: 1000 calls/day for One Call 3.0, but we limit to 30/day to be safe.
"""

import sys
from pathlib import Path

# Add parent directory to path to import agent
_parent_dir = Path(__file__).parent.parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

from src.core.agent import agent
from settings import settings

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration from settings
# =============================================================================

WEATHER_CONFIG = settings.WEATHER
API_KEY = WEATHER_CONFIG["api_key"]
DEFAULT_CITY = WEATHER_CONFIG["city"]
DEFAULT_LAT = WEATHER_CONFIG["lat"]
DEFAULT_LON = WEATHER_CONFIG["lon"]
UNITS = WEATHER_CONFIG["units"]
BASE_URL_V25 = WEATHER_CONFIG["base_url_v25"]
BASE_URL_V30 = WEATHER_CONFIG["base_url_v30"]


# =============================================================================
# Helper Functions
# =============================================================================

def _get_weather_emoji(condition: str) -> str:
    """Get emoji for weather condition."""
    condition = condition.lower()
    emojis = {
        "clear": "☀️",
        "clouds": "☁️",
        "rain": "🌧️",
        "drizzle": "🌦️",
        "thunderstorm": "⛈️",
        "snow": "❄️",
        "mist": "🌫️",
        "fog": "🌫️",
        "haze": "🌫️",
    }
    for key, emoji in emojis.items():
        if key in condition:
            return emoji
    return "🌡️"


def _format_temp(temp: float) -> str:
    """Format temperature."""
    return f"{temp:.1f}°C"


def _is_past_date(date_str: str) -> bool:
    """Check if a date string is in the past."""
    try:
        request_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        now = datetime.now(settings.TIMEZONE)
        return request_date < now.date()
    except ValueError:
        return False


def _is_future_date(date_str: str) -> bool:
    """Check if a date string is in the future."""
    try:
        request_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        now = datetime.now(settings.TIMEZONE)
        return request_date > now.date()
    except ValueError:
        return False


# =============================================================================
# One Call API 3.0 Functions (require subscription)
# =============================================================================

def _get_historical_weather(date: str, lat: float = None, lon: float = None) -> Dict[str, Any]:
    """
    Get historical weather data using One Call API 3.0 Daily Aggregation.
    
    This uses the /data/3.0/onecall/day_summary endpoint which provides
    aggregated weather data for any date from 1979-01-02 onwards.
    
    Args:
        date: Date in YYYY-MM-DD format
        lat: Latitude (defaults to configured location)
        lon: Longitude (defaults to configured location)
    
    Returns:
        Dict with aggregated weather data for the date
    """
    lat = lat or DEFAULT_LAT
    lon = lon or DEFAULT_LON
    
    try:
        params = {
            "lat": lat,
            "lon": lon,
            "date": date,
            "appid": API_KEY,
            "units": UNITS,
        }
        
        with httpx.Client(timeout=15.0) as client:
            response = client.get(f"{BASE_URL_V30}/onecall/day_summary", params=params)
            response.raise_for_status()
            data = response.json()
        
        # Extract temperature data
        temp = data.get("temperature", {})
        
        return {
            "date": date,
            "lat": lat,
            "lon": lon,
            "source": "onecall_day_summary",
            "temp_min": temp.get("min", 0),
            "temp_max": temp.get("max", 0),
            "temp_afternoon": temp.get("afternoon", 0),
            "temp_morning": temp.get("morning", 0),
            "temp_evening": temp.get("evening", 0),
            "temp_night": temp.get("night", 0),
            "humidity": data.get("humidity", {}).get("afternoon", 0),
            "cloud_cover": data.get("cloud_cover", {}).get("afternoon", 0),
            "pressure": data.get("pressure", {}).get("afternoon", 0),
            "precipitation_total": data.get("precipitation", {}).get("total", 0),
            "wind_max_speed": data.get("wind", {}).get("max", {}).get("speed", 0),
            "wind_max_direction": data.get("wind", {}).get("max", {}).get("direction", 0),
            "timestamp": datetime.now(settings.TIMEZONE).isoformat(),
        }
        
    except httpx.HTTPStatusError as e:
        logger.error(f"Historical weather API error: {e.response.status_code}")
        return {"error": f"API error: {e.response.status_code}"}
    except Exception as e:
        logger.error(f"Historical weather fetch failed: {e}")
        return {"error": str(e)}


def _get_weather_overview(date: str = None, lat: float = None, lon: float = None) -> Dict[str, Any]:
    """
    Get AI-generated weather overview using One Call API 3.0.
    
    This uses the /data/3.0/onecall/overview endpoint which provides
    a human-readable weather summary for today or tomorrow.
    
    Args:
        date: Date in YYYY-MM-DD format (only today or tomorrow supported)
        lat: Latitude (defaults to configured location)
        lon: Longitude (defaults to configured location)
    
    Returns:
        Dict with weather overview including AI-generated summary
    """
    lat = lat or DEFAULT_LAT
    lon = lon or DEFAULT_LON
    
    try:
        params = {
            "lat": lat,
            "lon": lon,
            "appid": API_KEY,
            "units": UNITS,
        }
        if date:
            params["date"] = date
        
        with httpx.Client(timeout=15.0) as client:
            response = client.get(f"{BASE_URL_V30}/onecall/overview", params=params)
            response.raise_for_status()
            data = response.json()
        
        return {
            "date": data.get("date", date),
            "lat": data.get("lat", lat),
            "lon": data.get("lon", lon),
            "timezone": data.get("tz", ""),
            "units": data.get("units", UNITS),
            "overview": data.get("weather_overview", ""),
            "source": "onecall_overview",
            "timestamp": datetime.now(settings.TIMEZONE).isoformat(),
        }
        
    except httpx.HTTPStatusError as e:
        logger.error(f"Weather overview API error: {e.response.status_code}")
        return {"error": f"API error: {e.response.status_code}"}
    except Exception as e:
        logger.error(f"Weather overview fetch failed: {e}")
        return {"error": str(e)}


# =============================================================================
# Agent Tools
# =============================================================================

@agent.tool_plain
def get_weather(city: str = "", date: str = None) -> Dict[str, Any]:
    """Get weather conditions for any date.
    
    Supports:
    - Today: Returns current weather (free API)
    - Past dates: Returns historical daily aggregation (One Call 3.0)
    - Future dates: Not supported (use get_weather_forecast instead)
    
    Args:
        city: Optional city name. Leave empty to use default (Curitiba).
              Note: For historical data, city is ignored (uses lat/lon).
        date: Optional date in YYYY-MM-DD format. Defaults to today.
    
    Returns:
        Dict with weather data (condition, temp, humidity, etc.)
    """
    if not API_KEY:
        return {"error": "Weather API key not configured"}
    
    city = city or DEFAULT_CITY
    now = datetime.now(settings.TIMEZONE)
    target_date = date or now.strftime("%Y-%m-%d")
    
    # Validate date format
    if date:
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return {"error": f"Invalid date format: {date}. Use YYYY-MM-DD."}
    
    # Future date - not supported for weather (use forecast)
    if date and _is_future_date(date):
        return {
            "error": "Future dates not supported. Use get_weather_forecast() for forecasts.",
            "date": date,
        }
    
    # Past date - use One Call 3.0 historical data
    if date and _is_past_date(date):
        logger.info(f"Fetching historical weather for {date}")
        historical = _get_historical_weather(date)
        
        if "error" in historical:
            return historical
        
        # Format response similar to current weather
        return {
            "city": city,
            "date": date,
            "condition": "historical",
            "description": f"Historical data for {date}",
            "temp": historical.get("temp_afternoon", 0),
            "temp_min": historical.get("temp_min", 0),
            "temp_max": historical.get("temp_max", 0),
            "humidity": historical.get("humidity", 0),
            "pressure": historical.get("pressure", 0),
            "cloud_cover": historical.get("cloud_cover", 0),
            "precipitation": historical.get("precipitation_total", 0),
            "wind_speed": historical.get("wind_max_speed", 0),
            "source": "onecall_day_summary",
            "timestamp": now.isoformat(),
        }
    
    # Today - use current weather API (free tier)
    try:
        params = {
            "q": city,
            "appid": API_KEY,
            "units": UNITS
        }
        
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{BASE_URL_V25}/weather", params=params)
            response.raise_for_status()
            data = response.json()
        
        weather = data["weather"][0]
        main = data["main"]
        wind = data.get("wind", {})
        
        result = {
            "city": city,
            "date": target_date,
            "condition": weather["main"],
            "description": weather["description"],
            "temp": main["temp"],
            "feels_like": main["feels_like"],
            "humidity": main["humidity"],
            "pressure": main.get("pressure", 0),
            "wind_speed": wind.get("speed", 0),
            "wind_direction": wind.get("deg", 0),
            "source": "current",
            "timestamp": now.isoformat(),
        }
        
        if "rain" in data:
            result["rain_1h"] = data["rain"].get("1h", 0)
        else:
            result["rain_1h"] = 0
        
        return result
        
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return {"error": f"City not found: {city}"}
        return {"error": f"Weather API error: HTTP {e.response.status_code}"}
    except Exception as e:
        return {"error": f"Error getting weather: {e}"}


# Alias for backward compatibility
def get_current_weather(city: str = "") -> Dict[str, Any]:
    """Alias for get_weather() - returns current weather."""
    return get_weather(city=city)


@agent.tool_plain
def get_weather_forecast(city: str = "", hours: int = 24) -> str:
    """Get weather forecast for Artur's city (Curitiba).
    
    Uses the free tier forecast API (3-hour intervals up to 5 days).
    
    Args:
        city: Optional city name. Leave empty to use default (Curitiba).
        hours: Hours to forecast (default 24, max 120)
    
    Returns:
        Formatted weather forecast
    """
    if not API_KEY:
        return "Weather API key not configured. Set OPENWEATHERMAP_API_KEY in .env"
    
    city = city or DEFAULT_CITY
    hours = min(max(3, hours), 120)
    cnt = hours // 3
    
    try:
        params = {
            "q": city,
            "appid": API_KEY,
            "units": UNITS,
            "cnt": cnt
        }
        
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{BASE_URL_V25}/forecast", params=params)
            response.raise_for_status()
            data = response.json()
        
        forecasts = data.get("list", [])
        
        if not forecasts:
            return f"No forecast data available for {city}"
        
        lines = [f"Weather Forecast for {city}", "=" * 50]
        
        for item in forecasts:
            dt = datetime.fromtimestamp(item["dt"])
            weather = item["weather"][0]
            main = item["main"]
            
            condition = weather["main"]
            temp = main["temp"]
            emoji = _get_weather_emoji(condition)
            
            rain_info = ""
            pop = item.get("pop", 0)
            if pop > 0:
                rain_info = f" | Rain: {int(pop * 100)}%"
            if "rain" in item:
                rain_3h = item["rain"].get("3h", 0)
                rain_info += f" ({rain_3h}mm)"
            
            time_str = dt.strftime("%a %H:%M")
            lines.append(f"{time_str}: {emoji} {_format_temp(temp)} - {condition}{rain_info}")
        
        return "\n".join(lines)
        
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return f"City not found: {city}"
        return f"Weather API error: HTTP {e.response.status_code}"
    except Exception as e:
        return f"Error getting forecast: {e}"


@agent.tool_plain
def get_weather_overview(date: str = None) -> Dict[str, Any]:
    """Get an AI-generated weather overview summary.
    
    Uses One Call API 3.0 to get a human-readable weather summary.
    Only supports today or tomorrow.
    
    Args:
        date: Optional date in YYYY-MM-DD format (today or tomorrow only)
    
    Returns:
        Dict with weather overview including AI-generated summary text
    """
    if not API_KEY:
        return {"error": "Weather API key not configured"}
    
    now = datetime.now(settings.TIMEZONE)
    today = now.strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Validate date
    if date and date not in [today, tomorrow]:
        return {
            "error": "Weather overview only supports today or tomorrow",
            "today": today,
            "tomorrow": tomorrow,
        }
    
    return _get_weather_overview(date=date)


@agent.tool_plain
def will_it_rain(city: str = "", hours: int = 12) -> str:
    """Check if rain is expected in Artur's city (Curitiba).
    
    Args:
        city: Optional city name. Leave empty to use default (Curitiba).
        hours: Hours to check (default 12, max 48)
    
    Returns:
        Rain forecast summary
    """
    if not API_KEY:
        return "Weather API key not configured. Set OPENWEATHERMAP_API_KEY in .env"
    
    city = city or DEFAULT_CITY
    hours = min(max(3, hours), 48)
    cnt = hours // 3
    
    try:
        params = {
            "q": city,
            "appid": API_KEY,
            "units": UNITS,
            "cnt": cnt
        }
        
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{BASE_URL_V25}/forecast", params=params)
            response.raise_for_status()
            data = response.json()
        
        forecasts = data.get("list", [])
        rain_periods = []
        total_rain = 0
        
        for item in forecasts:
            dt = datetime.fromtimestamp(item["dt"])
            weather = item["weather"][0]
            condition = weather["main"].lower()
            pop = item.get("pop", 0)
            
            is_rainy = condition in ("rain", "drizzle", "thunderstorm") or pop > 0.3
            
            if is_rainy:
                rain_mm = 0
                if "rain" in item:
                    rain_mm = item["rain"].get("3h", 0)
                total_rain += rain_mm
                
                rain_periods.append({
                    "time": dt,
                    "condition": weather["description"],
                    "probability": pop,
                    "amount": rain_mm
                })
        
        if not rain_periods:
            return f"☀️ No rain expected in {city} for the next {hours} hours!"
        
        lines = [f"🌧️ Rain expected in {city}!", "=" * 40]
        
        for period in rain_periods:
            time_str = period["time"].strftime("%a %H:%M")
            prob = int(period["probability"] * 100)
            lines.append(f"{time_str}: {period['condition']} ({prob}% chance)")
        
        if total_rain > 0:
            lines.append(f"\nTotal expected: {total_rain:.1f}mm")
        
        if rain_periods[0]["time"].hour < 12:
            lines.append("\n💡 Tip: Take an umbrella if going out this morning!")
        else:
            lines.append("\n💡 Tip: Consider carrying an umbrella later today.")
        
        return "\n".join(lines)
        
    except Exception as e:
        return f"Error checking rain forecast: {e}"


# =============================================================================
# Helper function for sensors/awareness engine
# =============================================================================

def get_weather_data(city: Optional[str] = None) -> Dict[str, Any]:
    """Get weather data as a dictionary (for sensor use).
    
    Returns dict with:
        - condition: Current weather condition
        - temp: Current temperature
        - humidity: Current humidity
        - rain_expected: Whether rain is expected in next 6 hours
        - rain_probability: Max probability of rain in next 6 hours
        - rain_time: When rain is expected (if any)
    """
    if not API_KEY:
        return {"error": "Weather API key not configured"}
    
    city = city or DEFAULT_CITY
    result = {
        "city": city,
        "condition": "",
        "temp": 0,
        "humidity": 0,
        "rain_expected": False,
        "rain_probability": 0,
        "rain_time": None,
        "rain_description": "",
    }
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{BASE_URL_V25}/weather",
                params={"q": city, "appid": API_KEY, "units": UNITS}
            )
            response.raise_for_status()
            current = response.json()
        
        result["condition"] = current["weather"][0]["main"]
        result["temp"] = current["main"]["temp"]
        result["humidity"] = current["main"]["humidity"]
        
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{BASE_URL_V25}/forecast",
                params={"q": city, "appid": API_KEY, "units": UNITS, "cnt": 4}
            )
            response.raise_for_status()
            forecast = response.json()
        
        for item in forecast.get("list", []):
            weather = item["weather"][0]
            condition = weather["main"].lower()
            pop = item.get("pop", 0)
            
            is_rainy = condition in ("rain", "drizzle", "thunderstorm") or pop > 0.4
            
            if is_rainy and not result["rain_expected"]:
                result["rain_expected"] = True
                result["rain_probability"] = pop
                result["rain_time"] = datetime.fromtimestamp(item["dt"]).strftime("%H:%M")
                result["rain_description"] = weather["description"]
            
            if pop > result["rain_probability"]:
                result["rain_probability"] = pop
        
        return result
        
    except Exception as e:
        return {"error": str(e)}
