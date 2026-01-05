"""
Friday Insights Engine - Weather Collector

Collects weather data from OpenWeatherMap API.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

from settings import settings
def get_brt():
    return settings.TIMEZONE
from src.awareness.collectors.base import BaseCollector

logger = logging.getLogger(__name__)


class WeatherCollector(BaseCollector):
    """
    Collects weather data from OpenWeatherMap.
    
    Data collected:
    - Current conditions
    - Temperature and humidity
    - Rain forecast
    """
    
    def __init__(self):
        super().__init__("weather")
        self._api_key = None
        self._city = "Curitiba"
    
    def initialize(self) -> bool:
        """Load API key from environment."""
        self._api_key = settings.OPENWEATHERMAP_API_KEY
        if not self._api_key:
            logger.warning("OPENWEATHERMAP_API_KEY not set")
            return False
        
        self._city = settings.WEATHER_CITY
        self._initialized = True
        logger.info(f"WeatherCollector initialized for {self._city}")
        return True
    
    def collect(self) -> Optional[Dict[str, Any]]:
        """Collect weather data."""
        if not self._api_key:
            if not self.initialize():
                return None
        
        import httpx
        
        now = datetime.now(get_brt())
        
        try:
            # Current weather
            current_url = f"https://api.openweathermap.org/data/2.5/weather"
            params = {
                "q": self._city,
                "appid": self._api_key,
                "units": "metric",
            }
            
            with httpx.Client(timeout=10.0) as client:
                current_resp = client.get(current_url, params=params)
                current_resp.raise_for_status()
                current = current_resp.json()
                
                # Forecast
                forecast_url = f"https://api.openweathermap.org/data/2.5/forecast"
                params["cnt"] = 8  # Next 24 hours (3h intervals)
                forecast_resp = client.get(forecast_url, params=params)
                forecast_resp.raise_for_status()
                forecast = forecast_resp.json()
            
            # Parse current
            current_data = {
                "condition": current.get("weather", [{}])[0].get("description", ""),
                "temp": round(current.get("main", {}).get("temp", 0), 1),
                "feels_like": round(current.get("main", {}).get("feels_like", 0), 1),
                "humidity": current.get("main", {}).get("humidity", 0),
                "wind_speed": round(current.get("wind", {}).get("speed", 0) * 3.6, 1),  # m/s to km/h
            }
            
            # Parse forecast for rain
            rain_expected = False
            rain_time = None
            rain_probability = 0
            
            for item in forecast.get("list", []):
                pop = item.get("pop", 0)  # Probability of precipitation
                weather = item.get("weather", [{}])[0]
                main = weather.get("main", "").lower()
                
                if pop > 0.3 or "rain" in main:
                    rain_expected = True
                    rain_probability = max(rain_probability, pop)
                    if not rain_time:
                        dt = datetime.fromtimestamp(item.get("dt", 0), tz=timezone.utc)
                        rain_time = dt.astimezone(get_brt()).strftime("%H:%M")
                    break
            
            return {
                "collected_at": now.isoformat(),
                "city": self._city,
                "current": current_data,
                "rain": {
                    "expected": rain_expected,
                    "probability": round(rain_probability, 2),
                    "expected_time": rain_time,
                },
            }
            
        except Exception as e:
            logger.error(f"Weather collection failed: {e}")
            return None
