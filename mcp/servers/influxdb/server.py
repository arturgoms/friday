"""
InfluxDB v1 MCP Server for Health & Running Data
Provides tools for querying health metrics and coaching analysis
"""
import json
from datetime import datetime, timedelta
from typing import Any, Optional
from influxdb import InfluxDBClient
from mcp.server import Server
from mcp.types import Tool, TextContent


class InfluxDBHealthMCP:
    """MCP Server for InfluxDB health/running data."""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8086,
        username: str = "",
        password: str = "",
        database: str = "health"
    ):
        """Initialize InfluxDB connection."""
        self.client = InfluxDBClient(
            host=host,
            port=port,
            username=username,
            password=password,
            database=database
        )
        self.database = database
        
        # Test connection
        try:
            self.client.ping()
            print(f"✅ Connected to InfluxDB at {host}:{port}")
        except Exception as e:
            print(f"❌ Failed to connect to InfluxDB: {e}")
    
    def get_tools(self) -> list[Tool]:
        """Define available MCP tools."""
        return [
            Tool(
                name="get_running_summary",
                description="Get running statistics for a time period (today, week, month, year)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "period": {
                            "type": "string",
                            "enum": ["today", "week", "month", "year", "all"],
                            "description": "Time period to analyze"
                        }
                    },
                    "required": ["period"]
                }
            ),
            Tool(
                name="get_heart_rate_zones",
                description="Analyze heart rate training zones from recent activities",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "Number of days to analyze (default: 7)"
                        }
                    }
                }
            ),
            Tool(
                name="get_pace_trends",
                description="Analyze pace improvements over time",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "weeks": {
                            "type": "integer",
                            "description": "Number of weeks to analyze (default: 4)"
                        }
                    }
                }
            ),
            Tool(
                name="get_weekly_mileage",
                description="Get weekly running mileage for the last N weeks",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "weeks": {
                            "type": "integer",
                            "description": "Number of weeks (default: 8)"
                        }
                    }
                }
            ),
            Tool(
                name="get_recovery_metrics",
                description="Get recovery indicators (resting HR, sleep, etc.)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "Number of days to analyze (default: 7)"
                        }
                    }
                }
            ),
            Tool(
                name="query_custom",
                description="Execute custom InfluxQL query for advanced analysis",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "InfluxQL query to execute"
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="get_personal_records",
                description="Get personal records (longest run, fastest pace, etc.)",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            )
        ]
    
    def _get_time_range(self, period: str) -> tuple[datetime, datetime]:
        """Get time range for a period."""
        now = datetime.now()
        
        if period == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            start = now - timedelta(days=7)
        elif period == "month":
            start = now - timedelta(days=30)
        elif period == "year":
            start = now - timedelta(days=365)
        else:  # all
            start = datetime(2020, 1, 1)  # Adjust based on your data
        
        return start, now
    
    def get_running_summary(self, period: str = "week") -> dict:
        """Get running summary for a period."""
        start, end = self._get_time_range(period)
        
        # Query total distance
        query = f"""
        SELECT SUM(distance) as total_distance,
               COUNT(distance) as run_count,
               MEAN(pace) as avg_pace,
               SUM(duration) as total_time,
               SUM(elevation_gain) as total_elevation
        FROM runs
        WHERE time >= '{start.isoformat()}Z' AND time <= '{end.isoformat()}Z'
        """
        
        try:
            result = self.client.query(query)
            points = list(result.get_points())
            
            if points:
                data = points[0]
                return {
                    "period": period,
                    "total_distance_km": round(data.get("total_distance", 0) / 1000, 2),
                    "run_count": int(data.get("run_count", 0)),
                    "avg_pace_min_km": round(data.get("avg_pace", 0), 2),
                    "total_time_hours": round(data.get("total_time", 0) / 3600, 2),
                    "total_elevation_m": round(data.get("total_elevation", 0), 0),
                    "start_date": start.strftime("%Y-%m-%d"),
                    "end_date": end.strftime("%Y-%m-%d")
                }
            else:
                return {"error": "No running data found for this period"}
        
        except Exception as e:
            return {"error": str(e)}
    
    def get_heart_rate_zones(self, days: int = 7) -> dict:
        """Analyze heart rate zones."""
        start = datetime.now() - timedelta(days=days)
        
        query = f"""
        SELECT heart_rate
        FROM runs
        WHERE time >= '{start.isoformat()}Z'
        """
        
        try:
            result = self.client.query(query)
            hr_data = [point["heart_rate"] for point in result.get_points() if point.get("heart_rate")]
            
            if not hr_data:
                return {"error": "No heart rate data found"}
            
            # Calculate zones (adjust based on your max HR)
            # Assuming max HR = 220 - age (adjust as needed)
            zones = {
                "zone1_recovery": [0.5, 0.6],
                "zone2_aerobic": [0.6, 0.7],
                "zone3_tempo": [0.7, 0.8],
                "zone4_threshold": [0.8, 0.9],
                "zone5_max": [0.9, 1.0]
            }
            
            max_hr = 185  # TODO: Make this configurable
            zone_counts = {zone: 0 for zone in zones.keys()}
            
            for hr in hr_data:
                hr_pct = hr / max_hr
                for zone, (low, high) in zones.items():
                    if low <= hr_pct < high:
                        zone_counts[zone] += 1
                        break
            
            total = len(hr_data)
            zone_percentages = {
                zone: round(count / total * 100, 1)
                for zone, count in zone_counts.items()
            }
            
            return {
                "days_analyzed": days,
                "total_readings": total,
                "avg_heart_rate": round(sum(hr_data) / len(hr_data), 0),
                "max_heart_rate": max(hr_data),
                "min_heart_rate": min(hr_data),
                "zone_distribution": zone_percentages
            }
        
        except Exception as e:
            return {"error": str(e)}
    
    def get_pace_trends(self, weeks: int = 4) -> dict:
        """Analyze pace improvements."""
        data_by_week = []
        
        for week in range(weeks):
            start = datetime.now() - timedelta(weeks=week+1)
            end = datetime.now() - timedelta(weeks=week)
            
            query = f"""
            SELECT MEAN(pace) as avg_pace,
                   MIN(pace) as best_pace
            FROM runs
            WHERE time >= '{start.isoformat()}Z' AND time <= '{end.isoformat()}Z'
            """
            
            try:
                result = self.client.query(query)
                points = list(result.get_points())
                
                if points and points[0].get("avg_pace"):
                    data_by_week.append({
                        "week": week + 1,
                        "avg_pace": round(points[0]["avg_pace"], 2),
                        "best_pace": round(points[0].get("best_pace", 0), 2)
                    })
            except:
                continue
        
        return {
            "weeks_analyzed": weeks,
            "pace_by_week": list(reversed(data_by_week))
        }
    
    def get_weekly_mileage(self, weeks: int = 8) -> dict:
        """Get weekly mileage."""
        mileage_by_week = []
        
        for week in range(weeks):
            start = datetime.now() - timedelta(weeks=week+1)
            end = datetime.now() - timedelta(weeks=week)
            
            query = f"""
            SELECT SUM(distance) as total_distance,
                   COUNT(distance) as run_count
            FROM runs
            WHERE time >= '{start.isoformat()}Z' AND time <= '{end.isoformat()}Z'
            """
            
            try:
                result = self.client.query(query)
                points = list(result.get_points())
                
                if points:
                    data = points[0]
                    mileage_by_week.append({
                        "week": week + 1,
                        "distance_km": round(data.get("total_distance", 0) / 1000, 2),
                        "run_count": int(data.get("run_count", 0))
                    })
            except:
                continue
        
        return {
            "weeks_analyzed": weeks,
            "mileage_by_week": list(reversed(mileage_by_week))
        }
    
    def get_recovery_metrics(self, days: int = 7) -> dict:
        """Get recovery indicators."""
        start = datetime.now() - timedelta(days=days)
        
        queries = {
            "resting_hr": f"SELECT MEAN(resting_heart_rate) as avg_rhr FROM health WHERE time >= '{start.isoformat()}Z'",
            "sleep": f"SELECT MEAN(sleep_hours) as avg_sleep FROM health WHERE time >= '{start.isoformat()}Z'",
            "hrv": f"SELECT MEAN(hrv) as avg_hrv FROM health WHERE time >= '{start.isoformat()}Z'"
        }
        
        metrics = {}
        
        for metric, query in queries.items():
            try:
                result = self.client.query(query)
                points = list(result.get_points())
                if points:
                    metrics[metric] = round(points[0].get(f"avg_{metric.split('_')[-1]}", 0), 1)
            except:
                metrics[metric] = None
        
        return {
            "days_analyzed": days,
            "metrics": metrics
        }
    
    def get_personal_records(self) -> dict:
        """Get personal records."""
        records = {}
        
        queries = {
            "longest_run": "SELECT MAX(distance) as distance FROM runs",
            "fastest_pace": "SELECT MIN(pace) as pace FROM runs",
            "most_elevation": "SELECT MAX(elevation_gain) as elevation FROM runs",
            "longest_duration": "SELECT MAX(duration) as duration FROM runs"
        }
        
        for record, query in queries.items():
            try:
                result = self.client.query(query)
                points = list(result.get_points())
                if points:
                    value = points[0].get(list(points[0].keys())[0])
                    if record == "longest_run":
                        records[record] = f"{round(value / 1000, 2)} km"
                    elif record == "fastest_pace":
                        records[record] = f"{round(value, 2)} min/km"
                    elif record == "most_elevation":
                        records[record] = f"{round(value, 0)} m"
                    elif record == "longest_duration":
                        records[record] = f"{round(value / 3600, 2)} hours"
            except:
                records[record] = "N/A"
        
        return {"personal_records": records}
    
    def query_custom(self, query: str) -> dict:
        """Execute custom query."""
        try:
            result = self.client.query(query)
            points = list(result.get_points())
            return {"results": points[:100]}  # Limit to 100 results
        except Exception as e:
            return {"error": str(e)}
    
    def handle_tool_call(self, tool_name: str, arguments: dict) -> str:
        """Handle MCP tool calls."""
        try:
            if tool_name == "get_running_summary":
                result = self.get_running_summary(arguments.get("period", "week"))
            elif tool_name == "get_heart_rate_zones":
                result = self.get_heart_rate_zones(arguments.get("days", 7))
            elif tool_name == "get_pace_trends":
                result = self.get_pace_trends(arguments.get("weeks", 4))
            elif tool_name == "get_weekly_mileage":
                result = self.get_weekly_mileage(arguments.get("weeks", 8))
            elif tool_name == "get_recovery_metrics":
                result = self.get_recovery_metrics(arguments.get("days", 7))
            elif tool_name == "get_personal_records":
                result = self.get_personal_records()
            elif tool_name == "query_custom":
                result = self.query_custom(arguments.get("query", ""))
            else:
                result = {"error": f"Unknown tool: {tool_name}"}
            
            return json.dumps(result, indent=2)
        
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)


# Initialize the MCP server
def create_influxdb_mcp(config: dict) -> InfluxDBHealthMCP:
    """Create InfluxDB MCP instance."""
    return InfluxDBHealthMCP(
        host=config.get("host", "localhost"),
        port=config.get("port", 8086),
        username=config.get("username", ""),
        password=config.get("password", ""),
        database=config.get("database", "health")
    )
