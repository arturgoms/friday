"""
Friday 3.0 Weather Sensor

Monitors weather conditions and alerts on rain forecast.
"""

import logging
from datetime import datetime
from typing import Any, Dict

from src.core.registry import friday_sensor

logger = logging.getLogger(__name__)


@friday_sensor(name="weather_forecast", interval_seconds=1800)  # Every 30 minutes
def check_weather_forecast() -> Dict[str, Any]:
    """Check weather forecast for rain alerts.
    
    Returns dict with:
        - city: City name
        - condition: Current weather condition
        - temp: Current temperature
        - rain_expected: Whether rain is expected soon
        - rain_probability: Probability of rain (0-1)
        - rain_time: When rain is expected
        - rain_description: Description of expected rain
    """
    try:
        # Import here to avoid circular imports
        from src.tools.weather import get_weather_data
        
        data = get_weather_data()
        
        if "error" in data:
            logger.warning(f"Weather sensor error: {data['error']}")
            return data
        
        logger.debug(f"Weather: {data['condition']}, {data['temp']}°C, Rain: {data['rain_expected']}")
        
        return data
        
    except Exception as e:
        logger.error(f"Weather sensor error: {e}")
        return {"error": str(e)}
