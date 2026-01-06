"""
Friday 3.0 Weather Tools

Tools for getting weather information using OpenWeatherMap API.
"""

import sys
from pathlib import Path

# Add parent directory to path to import agent
_parent_dir = Path(__file__).parent.parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

from src.core.agent import agent
from settings import settings

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx


# Get config from settings
WEATHER_API_KEY = settings.OPENWEATHERMAP_API_KEY or settings.WEATHER_API_KEY
WEATHER_CITY = settings.WEATHER_CITY
OPENWEATHER_BASE = "https://api.openweathermap.org/data/2.5"


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


@agent.tool_plain
def get_current_weather(city: str = "") -> Dict[str, Any]:
    """Get current weather conditions for Artur's city (Curitiba).
    
    Atomic data tool that returns a dict. Data is automatically saved as snapshot.
    
    Call this with NO arguments to get weather for the default city.
    
    Args:
        city: Optional city name. Leave empty to use default (Curitiba).
    
    Returns:
        Dict with weather data (city, condition, temp, humidity, wind, etc.)
    """
    city = city or None  # Convert empty string to None
    if not WEATHER_API_KEY:
        return {"error": "Weather API key not configured"}
    
    city = city or WEATHER_CITY
    
    try:
        params = {
            "q": city,
            "appid": WEATHER_API_KEY,
            "units": "metric"
        }
        
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{OPENWEATHER_BASE}/weather", params=params)
            response.raise_for_status()
            data = response.json()
        
        # Extract data
        weather = data["weather"][0]
        main = data["main"]
        wind = data.get("wind", {})
        
        result = {
            "city": city,
            "condition": weather["main"],
            "description": weather["description"],
            "temp": main["temp"],
            "feels_like": main["feels_like"],
            "humidity": main["humidity"],
            "pressure": main.get("pressure", 0),
            "wind_speed": wind.get("speed", 0),
            "wind_direction": wind.get("deg", 0),
            "timestamp": datetime.now(settings.TIMEZONE).isoformat(),
        }
        
        # Add rain info if present
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


@agent.tool_plain
def get_weather_forecast(city: str = "", hours: int = 24) -> str:
    """Get weather forecast for Artur's city (Curitiba).
    
    Call this with NO arguments to get forecast for the default city.
    
    Args:
        city: Optional city name. Leave empty to use default (Curitiba).
        hours: Hours to forecast (default 24, max 120)
    
    Returns:
        Formatted weather forecast
    """
    city = city or None  # Convert empty string to None
    if not WEATHER_API_KEY:
        return "Weather API key not configured. Set WEATHER_API_KEY in .env"
    
    city = city or WEATHER_CITY
    hours = min(max(3, hours), 120)
    cnt = hours // 3  # API returns 3-hour intervals
    
    try:
        params = {
            "q": city,
            "appid": WEATHER_API_KEY,
            "units": "metric",
            "cnt": cnt
        }
        
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{OPENWEATHER_BASE}/forecast", params=params)
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
            
            # Check for rain
            rain_info = ""
            pop = item.get("pop", 0)  # Probability of precipitation
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
def will_it_rain(city: str = "", hours: int = 12) -> str:
    """Check if rain is expected in Artur's city (Curitiba).
    
    Call this with NO arguments to check rain for the default city.
    
    Args:
        city: Optional city name. Leave empty to use default (Curitiba).
        hours: Hours to check (default 12, max 48)
    
    Returns:
        Rain forecast summary
    """
    city = city or None  # Convert empty string to None
    if not WEATHER_API_KEY:
        return "Weather API key not configured. Set WEATHER_API_KEY in .env"
    
    city = city or WEATHER_CITY
    hours = min(max(3, hours), 48)
    cnt = hours // 3
    
    try:
        params = {
            "q": city,
            "appid": WEATHER_API_KEY,
            "units": "metric",
            "cnt": cnt
        }
        
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{OPENWEATHER_BASE}/forecast", params=params)
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
        
        # Recommendation
        if rain_periods[0]["time"].hour < 12:
            lines.append("\n💡 Tip: Take an umbrella if going out this morning!")
        else:
            lines.append("\n💡 Tip: Consider carrying an umbrella later today.")
        
        return "\n".join(lines)
        
    except Exception as e:
        return f"Error checking rain forecast: {e}"


# =============================================================================
# Helper function for sensor
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
    if not WEATHER_API_KEY:
        return {"error": "Weather API key not configured"}
    
    city = city or WEATHER_CITY
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
        # Get current weather
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{OPENWEATHER_BASE}/weather",
                params={"q": city, "appid": WEATHER_API_KEY, "units": "metric"}
            )
            response.raise_for_status()
            current = response.json()
        
        result["condition"] = current["weather"][0]["main"]
        result["temp"] = current["main"]["temp"]
        result["humidity"] = current["main"]["humidity"]
        
        # Check forecast for rain (next 6 hours = 2 intervals)
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{OPENWEATHER_BASE}/forecast",
                params={"q": city, "appid": WEATHER_API_KEY, "units": "metric", "cnt": 4}
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
            
            # Track max probability
            if pop > result["rain_probability"]:
                result["rain_probability"] = pop
        
        return result
        
    except Exception as e:
        return {"error": str(e)}
