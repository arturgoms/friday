"""
Friday 3.0 InfluxDB Client

Shared InfluxDB client for health data queries.
Used by sensors, tools, and collectors that access Garmin health data.

Usage:
    from src.core.influxdb import get_influx_client, query_latest, query
    
    # Get the shared client
    client = get_influx_client()
    
    # Query latest record from a measurement
    data = query_latest("BodyBattery")
    
    # Execute custom query
    results = query("SELECT * FROM StressLevel WHERE time > now() - 1h")
"""

import json
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path to import settings
_parent_dir = Path(__file__).parent.parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

from settings import settings

logger = logging.getLogger(__name__)

# Thread-safe singleton
_influx_client = None
_influx_client_lock = threading.Lock()


def get_influx_client():
    """Get the shared InfluxDB client (thread-safe singleton).
    
    Returns:
        InfluxDBClient instance or None if connection fails
    """
    global _influx_client
    
    if _influx_client is not None:
        return _influx_client
    
    with _influx_client_lock:
        # Double-check pattern
        if _influx_client is not None:
            return _influx_client
        
        try:
            from influxdb import InfluxDBClient
            
            # Get config from settings
            config = settings.INFLUXDB
            
            client = InfluxDBClient(
                host=config.get("host", "localhost"),
                port=config.get("port", 8086),
                username=config.get("username", ""),
                password=config.get("password", ""),
                database=config.get("database", "health")
            )
            
            # Test connection
            client.ping()
            
            _influx_client = client
            logger.info(f"[INFLUXDB] Connected to {config.get('host')}:{config.get('port')} db={config.get('database')}")
            return _influx_client
            
        except ImportError:
            logger.error("[INFLUXDB] influxdb package not installed. Run: pip install influxdb")
            return None
        except Exception as e:
            logger.error(f"[INFLUXDB] Connection failed: {e}")
            return None


def query(query_str: str) -> List[Dict[str, Any]]:
    """Execute an InfluxDB query and return results as a list of dicts.
    
    Args:
        query_str: InfluxQL query string
        
    Returns:
        List of result dictionaries, empty list on error
    """
    client = get_influx_client()
    if not client:
        return []
    
    try:
        result = client.query(query_str)
        return list(result.get_points())
    except Exception as e:
        logger.error(f"[INFLUXDB] Query error: {e}")
        logger.debug(f"[INFLUXDB] Failed query: {query_str}")
        return []


def query_latest(measurement: str, fields: str = "*") -> Optional[Dict[str, Any]]:
    """Query the latest record from a measurement.
    
    Args:
        measurement: InfluxDB measurement name
        fields: Fields to select (default: all)
        
    Returns:
        Latest record as dict, or None if not found/error
    """
    results = query(f"SELECT {fields} FROM {measurement} ORDER BY time DESC LIMIT 1")
    return results[0] if results else None


def query_time_range(
    measurement: str, 
    fields: str = "*", 
    time_range: str = "1h",
    order: str = "DESC",
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Query records from a measurement within a time range.
    
    Args:
        measurement: InfluxDB measurement name
        fields: Fields to select (default: all)
        time_range: Time range like "1h", "24h", "7d" (default: 1h)
        order: Sort order, "ASC" or "DESC" (default: DESC)
        limit: Maximum records to return (default: no limit)
        
    Returns:
        List of records as dicts
    """
    query_str = f"SELECT {fields} FROM {measurement} WHERE time > now() - {time_range} ORDER BY time {order}"
    if limit:
        query_str += f" LIMIT {limit}"
    return query(query_str)


def close_client():
    """Close the InfluxDB client connection."""
    global _influx_client
    with _influx_client_lock:
        if _influx_client:
            try:
                _influx_client.close()
            except Exception:
                pass
            _influx_client = None
            logger.info("[INFLUXDB] Connection closed")
