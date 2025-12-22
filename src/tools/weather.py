"""
Friday 3.0 Weather Tools

Tools for getting weather information using OpenWeatherMap API.
"""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from src.core.registry import friday_tool

# Get config from environment
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")
WEATHER_CITY = os.getenv("WEATHER_CITY", "London")
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


@friday_tool(name="get_current_weather")
def get_current_weather(city: str = "") -> str:
    """Get current weather conditions for Artur's city (Curitiba).
    
    Call this with NO arguments to get weather for the default city.
    
    Args:
        city: Optional city name. Leave empty to use default (Curitiba).
    
    Returns:
        Formatted current weather information
    """
    city = city or None  # Convert empty string to None
    if not WEATHER_API_KEY:
        return "Weather API key not configured. Set WEATHER_API_KEY in .env"
    
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
        
        condition = weather["main"]
        description = weather["description"]
        temp = main["temp"]
        feels_like = main["feels_like"]
        humidity = main["humidity"]
        wind_speed = wind.get("speed", 0)
        
        emoji = _get_weather_emoji(condition)
        
        lines = [
            f"Weather in {city} {emoji}",
            "=" * 40,
            f"Condition: {description.title()}",
            f"Temperature: {_format_temp(temp)} (feels like {_format_temp(feels_like)})",
            f"Humidity: {humidity}%",
            f"Wind: {wind_speed} m/s",
        ]
        
        # Add rain info if present
        if "rain" in data:
            rain_1h = data["rain"].get("1h", 0)
            lines.append(f"Rain (1h): {rain_1h} mm")
        
        return "\n".join(lines)
        
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return f"City not found: {city}"
        return f"Weather API error: HTTP {e.response.status_code}"
    except Exception as e:
        return f"Error getting weather: {e}"


@friday_tool(name="get_weather_forecast")
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


@friday_tool(name="will_it_rain")
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
