"""Unit tests for InfluxDB MCP Server tools."""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta


# Mock the influxdb module before importing the server
@pytest.fixture(autouse=True)
def mock_influxdb():
    """Mock influxdb module for all tests."""
    with patch.dict('sys.modules', {'influxdb': MagicMock()}):
        yield


@pytest.fixture
def mock_client():
    """Create a mock InfluxDB client."""
    client = Mock()
    client.ping = Mock(return_value=True)
    client.query = Mock(return_value=Mock(get_points=Mock(return_value=[])))
    client.get_list_database = Mock(return_value=[{"name": "GarminStats"}, {"name": "test"}])
    return client


@pytest.fixture
def mcp_server(mock_client):
    """Create MCP server instance with mocked client."""
    # Import here to avoid import errors
    import sys
    sys.path.insert(0, 'mcp/servers/influxdb')
    
    with patch('influxdb.InfluxDBClient', return_value=mock_client):
        from mcp.servers.influxdb.server import InfluxDBHealthMCP
        server = InfluxDBHealthMCP(
            host="localhost",
            port=8086,
            username="test",
            password="test",
            database="GarminStats"
        )
        server.client = mock_client
        return server


class TestHelperFunctions:
    """Test helper functions."""
    
    def test_format_duration_hours_and_minutes(self):
        """Test duration formatting with hours and minutes."""
        from mcp.servers.influxdb.server import format_duration
        
        assert format_duration(3600) == "1h 0m"
        assert format_duration(5400) == "1h 30m"
        assert format_duration(7200) == "2h 0m"
    
    def test_format_duration_minutes_only(self):
        """Test duration formatting with only minutes."""
        from mcp.servers.influxdb.server import format_duration
        
        assert format_duration(300) == "5m"
        assert format_duration(1800) == "30m"
        assert format_duration(2700) == "45m"
    
    def test_format_duration_zero(self):
        """Test duration formatting with zero."""
        from mcp.servers.influxdb.server import format_duration
        
        assert format_duration(0) == "0m"
        assert format_duration(0.0) == "0m"
    
    def test_format_pace_valid(self):
        """Test pace formatting with valid speed."""
        from mcp.servers.influxdb.server import format_pace
        
        # 3 m/s = ~5:33/km
        result = format_pace(3.0)
        assert "/km" in result
    
    def test_format_pace_zero(self):
        """Test pace formatting with zero speed."""
        from mcp.servers.influxdb.server import format_pace
        
        assert format_pace(0) == "N/A"
        assert format_pace(0.0) == "N/A"
        assert format_pace(-1) == "N/A"


class TestRunningAnalysisTools:
    """Test running and training analysis tools."""
    
    def test_get_recent_runs_with_data(self, mcp_server, mock_client):
        """Test get_recent_runs with data."""
        mock_client.query.return_value.get_points.return_value = [
            {
                "time": "2024-01-15T10:00:00Z",
                "activityName": "Morning Run",
                "distance": 5000,
                "movingDuration": 1800,
                "averageSpeed": 2.78,
                "averageHR": 150,
                "maxHR": 175,
                "calories": 350,
                "elevationGain": 50,
                "aerobicTE": 3.5,
                "anaerobicTE": 0.5
            }
        ]
        
        result = mcp_server.get_recent_runs(limit=10, days=30)
        
        assert "runs" in result
        assert len(result["runs"]) == 1
        assert result["runs"][0]["name"] == "Morning Run"
        assert result["runs"][0]["distance_km"] == 5.0
        assert result["runs"][0]["avg_hr"] == 150
    
    def test_get_recent_runs_empty(self, mcp_server, mock_client):
        """Test get_recent_runs with no data."""
        mock_client.query.return_value.get_points.return_value = []
        
        result = mcp_server.get_recent_runs()
        
        assert result["runs"] == []
        assert "message" in result
    
    def test_get_training_load(self, mcp_server, mock_client):
        """Test get_training_load."""
        mock_client.query.return_value.get_points.return_value = [
            {
                "distance": 10000,
                "movingDuration": 3600,
                "averageHR": 145,
                "averageSpeed": 2.78,
                "aerobicTE": 3.0
            },
            {
                "distance": 8000,
                "movingDuration": 2800,
                "averageHR": 150,
                "averageSpeed": 2.86,
                "aerobicTE": 3.2
            }
        ]
        
        result = mcp_server.get_training_load(weeks=4)
        
        assert "weekly_data" in result
        assert "weeks_analyzed" in result
        assert result["weeks_analyzed"] == 4
    
    def test_get_pace_analysis(self, mcp_server, mock_client):
        """Test get_pace_analysis."""
        mock_client.query.return_value.get_points.return_value = [
            {"time": "2024-01-15T10:00:00Z", "averageSpeed": 2.78, "distance": 5000, "movingDuration": 1800},
            {"time": "2024-01-14T10:00:00Z", "averageSpeed": 2.85, "distance": 6000, "movingDuration": 2100},
        ]
        
        result = mcp_server.get_pace_analysis(days=30)
        
        assert "average_pace" in result
        assert "best_pace" in result
        assert "consistency" in result
        assert result["run_count"] == 2
    
    def test_get_vo2max_progress(self, mcp_server, mock_client):
        """Test get_vo2max_progress."""
        mock_client.query.return_value.get_points.return_value = [
            {"time": "2024-01-01T00:00:00Z", "vo2Max": 45.0},
            {"time": "2024-02-01T00:00:00Z", "vo2Max": 46.5},
            {"time": "2024-03-01T00:00:00Z", "vo2Max": 47.0},
        ]
        
        result = mcp_server.get_vo2max_progress(months=6)
        
        assert "current_vo2max" in result
        assert "starting_vo2max" in result
        assert "change" in result
        assert "trend" in result
    
    def test_get_training_status(self, mcp_server, mock_client):
        """Test get_training_status."""
        # Mock multiple queries
        def mock_query(query):
            mock_result = Mock()
            if "TrainingReadiness" in query:
                mock_result.get_points.return_value = [
                    {"score": 75, "recoveryTime": 12, "hrvFactorPercent": 85, "level": "READY"}
                ]
            elif "DailyStats" in query and "trainingStatus" in query:
                mock_result.get_points.return_value = [
                    {"trainingStatus": "PRODUCTIVE", "trainingStatusDescription": "Good progress"}
                ]
            else:
                mock_result.get_points.return_value = [{"dist": 25000, "cnt": 4, "te": 3.2}]
            return mock_result
        
        mock_client.query.side_effect = mock_query
        
        result = mcp_server.get_training_status()
        
        assert "training_readiness" in result or "recent_load" in result
    
    def test_get_heart_rate_zones(self, mcp_server, mock_client):
        """Test get_heart_rate_zones."""
        mock_client.query.return_value.get_points.return_value = [
            {
                "zone1Seconds": 600,
                "zone2Seconds": 1200,
                "zone3Seconds": 900,
                "zone4Seconds": 300,
                "zone5Seconds": 0,
                "averageHR": 145,
                "maxHR": 180
            }
        ]
        
        result = mcp_server.get_heart_rate_zones(days=30)
        
        assert "zone_distribution" in result
        assert "total_training_time" in result
        assert "polarization" in result
    
    def test_get_long_runs(self, mcp_server, mock_client):
        """Test get_long_runs."""
        mock_client.query.return_value.get_points.return_value = [
            {
                "time": "2024-01-15T06:00:00Z",
                "activityName": "Long Run",
                "distance": 18000,
                "movingDuration": 5400,
                "averageSpeed": 3.33,
                "averageHR": 145,
                "elevationGain": 150
            }
        ]
        
        result = mcp_server.get_long_runs(min_distance_km=15, months=3)
        
        assert "runs" in result
        assert len(result["runs"]) == 1
        assert result["runs"][0]["distance_km"] == 18.0
        assert result["longest_km"] == 18.0


class TestSleepRecoveryTools:
    """Test sleep and recovery analysis tools."""
    
    def test_get_sleep_analysis(self, mcp_server, mock_client):
        """Test get_sleep_analysis."""
        mock_client.query.return_value.get_points.return_value = [
            {
                "time": "2024-01-15T00:00:00Z",
                "deepSleepSeconds": 5400,
                "lightSleepSeconds": 14400,
                "remSleepSeconds": 5400,
                "awakeSleepSeconds": 1800,
                "sleepScore": 82,
                "restingHeartRate": 55,
                "avgOvernightHrv": 45,
                "avgSpo2": 96,
                "awakeCount": 2
            }
        ]
        
        result = mcp_server.get_sleep_analysis(days=7)
        
        assert "records" in result
        assert "averages" in result
        assert len(result["records"]) == 1
        assert result["records"][0]["sleep_score"] == 82
    
    def test_get_recovery_metrics(self, mcp_server, mock_client):
        """Test get_recovery_metrics."""
        def mock_query(query):
            mock_result = Mock()
            if "bodyBatteryAtWakeTime" in query:
                mock_result.get_points.return_value = [
                    {"bodyBatteryAtWakeTime": 75},
                    {"bodyBatteryAtWakeTime": 70},
                ]
            elif "sleepScore" in query:
                mock_result.get_points.return_value = [
                    {"sleepScore": 80, "avgOvernightHrv": 45}
                ]
            elif "stressAvg" in query:
                mock_result.get_points.return_value = [
                    {"stressAvg": 35}
                ]
            elif "TrainingReadiness" in query:
                mock_result.get_points.return_value = [
                    {"score": 72, "level": "READY"}
                ]
            else:
                mock_result.get_points.return_value = []
            return mock_result
        
        mock_client.query.side_effect = mock_query
        
        result = mcp_server.get_recovery_metrics(days=7)
        
        assert "days_analyzed" in result
    
    def test_get_recovery_status(self, mcp_server, mock_client):
        """Test get_recovery_status."""
        def mock_query(query):
            mock_result = Mock()
            if "TrainingReadiness" in query:
                mock_result.get_points.return_value = [
                    {"score": 80, "recoveryTime": 8, "hrvFactorPercent": 90, "level": "READY"}
                ]
            elif "BodyBatteryIntraday" in query:
                mock_result.get_points.return_value = [{"BodyBatteryLevel": 65}]
            elif "bodyBatteryAtWakeTime" in query:
                mock_result.get_points.return_value = [
                    {"bodyBatteryAtWakeTime": 80}
                ]
            elif "avgOvernightHrv" in query:
                mock_result.get_points.return_value = [
                    {"avgOvernightHrv": 48}
                ]
            else:
                mock_result.get_points.return_value = []
            return mock_result
        
        mock_client.query.side_effect = mock_query
        
        result = mcp_server.get_recovery_status(days=7)
        
        assert "recommendations" in result
    
    def test_get_hrv_analysis(self, mcp_server, mock_client):
        """Test get_hrv_analysis."""
        mock_client.query.return_value.get_points.return_value = [
            {"time": "2024-01-15T00:00:00Z", "avgOvernightHrv": 48},
            {"time": "2024-01-14T00:00:00Z", "avgOvernightHrv": 45},
            {"time": "2024-01-13T00:00:00Z", "avgOvernightHrv": 50},
        ]
        
        result = mcp_server.get_hrv_analysis(days=14)
        
        assert "readings" in result
        assert "statistics" in result
        assert "trend" in result
        assert result["statistics"]["average"] == 48  # (48+45+50)/3 rounded


class TestHealthWellnessTools:
    """Test health and wellness tools."""
    
    def test_get_weekly_health_digest(self, mcp_server, mock_client):
        """Test get_weekly_health_digest."""
        def mock_query(query):
            mock_result = Mock()
            if "ActivitySummary" in query:
                mock_result.get_points.return_value = [
                    {"activityType": "running", "distance": 10000, "movingDuration": 3600, "calories": 500}
                ]
            elif "SleepSummary" in query:
                mock_result.get_points.return_value = [
                    {"sleepScore": 80, "deepSleepSeconds": 5400, "lightSleepSeconds": 14400, "remSleepSeconds": 5400}
                ]
            elif "totalSteps" in query:
                mock_result.get_points.return_value = [{"totalSteps": 10000, "totalDistanceMeters": 8000}]
            else:
                mock_result.get_points.return_value = [{"stressAvg": 35, "bodyBatteryAtWakeTime": 70}]
            return mock_result
        
        mock_client.query.side_effect = mock_query
        
        result = mcp_server.get_weekly_health_digest(weeks_ago=0)
        
        assert "week_ending" in result
        assert "week_start" in result
    
    def test_get_stress_patterns(self, mcp_server, mock_client):
        """Test get_stress_patterns."""
        mock_client.query.return_value.get_points.return_value = [
            {
                "time": "2024-01-15T00:00:00Z",
                "stressAvg": 35,
                "stressHigh": 3600,
                "stressMedium": 7200,
                "stressLow": 14400,
                "restStress": 7200
            }
        ]
        
        result = mcp_server.get_stress_patterns(days=7)
        
        assert "daily_stress" in result
        assert "statistics" in result
        assert "interpretation" in result
    
    def test_get_activity_overview(self, mcp_server, mock_client):
        """Test get_activity_overview."""
        def mock_query(query):
            mock_result = Mock()
            if "DailyStats" in query:
                mock_result.get_points.return_value = [
                    {
                        "time": "2024-01-15T00:00:00Z",
                        "totalSteps": 10000,
                        "totalDistanceMeters": 8000,
                        "activeCalories": 500,
                        "activeSeconds": 3600,
                        "highlyActiveSeconds": 1800
                    }
                ]
            else:
                mock_result.get_points.return_value = [
                    {
                        "time": "2024-01-15T10:00:00Z",
                        "activityName": "Run",
                        "activityType": "running",
                        "distance": 5000,
                        "movingDuration": 1800,
                        "calories": 350
                    }
                ]
            return mock_result
        
        mock_client.query.side_effect = mock_query
        
        result = mcp_server.get_activity_overview(days=7)
        
        assert "period_days" in result
    
    def test_compare_weeks(self, mcp_server, mock_client):
        """Test compare_weeks."""
        call_count = [0]
        
        def mock_query(query):
            mock_result = Mock()
            call_count[0] += 1
            
            if "running" in query.lower():
                mock_result.get_points.return_value = [{"dist": 25000, "cnt": 4, "cal": 1500}]
            elif "sleepscore" in query.lower():
                mock_result.get_points.return_value = [{"score": 78, "duration": 25200}]
            else:
                mock_result.get_points.return_value = [{"steps": 10000, "stress": 35, "bb": 70}]
            return mock_result
        
        mock_client.query.side_effect = mock_query
        
        result = mcp_server.compare_weeks(week1_ago=0, week2_ago=1)
        
        assert "week1" in result
        assert "week2" in result
        assert "changes" in result


class TestRawDatabaseAccess:
    """Test raw database access tools."""
    
    def test_query_influxdb(self, mcp_server, mock_client):
        """Test query_influxdb."""
        mock_client.query.return_value.get_points.return_value = [
            {"value": 100, "time": "2024-01-15T00:00:00Z"}
        ]
        
        result = mcp_server.query_influxdb("SELECT * FROM test LIMIT 10")
        
        assert "results" in result
        assert "query" in result
        assert result["count"] == 1
    
    def test_query_influxdb_error(self, mcp_server, mock_client):
        """Test query_influxdb with error."""
        mock_client.query.side_effect = Exception("Query failed")
        
        result = mcp_server.query_influxdb("INVALID QUERY")
        
        assert "error" in result
    
    def test_list_databases(self, mcp_server, mock_client):
        """Test list_databases."""
        result = mcp_server.list_databases()
        
        assert "databases" in result
        assert "GarminStats" in result["databases"]
    
    def test_list_measurements(self, mcp_server, mock_client):
        """Test list_measurements."""
        mock_client.query.return_value.get_points.return_value = [
            {"name": "ActivitySummary"},
            {"name": "SleepSummary"},
            {"name": "DailyStats"}
        ]
        
        result = mcp_server.list_measurements()
        
        assert "measurements" in result
        assert "database" in result
    
    def test_show_field_keys(self, mcp_server, mock_client):
        """Test show_field_keys."""
        mock_client.query.return_value.get_points.return_value = [
            {"fieldKey": "distance", "fieldType": "float"},
            {"fieldKey": "duration", "fieldType": "integer"}
        ]
        
        result = mcp_server.show_field_keys("ActivitySummary")
        
        assert "fields" in result
        assert "measurement" in result
        assert len(result["fields"]) == 2
    
    def test_show_tag_keys(self, mcp_server, mock_client):
        """Test show_tag_keys."""
        mock_client.query.return_value.get_points.return_value = [
            {"tagKey": "activityType"}
        ]
        
        result = mcp_server.show_tag_keys("ActivitySummary")
        
        assert "tags" in result
        assert "measurement" in result


class TestToolHandling:
    """Test MCP tool handling."""
    
    def test_handle_tool_call_unknown_tool(self, mcp_server):
        """Test handling unknown tool."""
        result = json.loads(mcp_server.handle_tool_call("unknown_tool", {}))
        
        assert "error" in result
        assert "Unknown tool" in result["error"]
    
    def test_handle_tool_call_get_recent_runs(self, mcp_server, mock_client):
        """Test handle_tool_call for get_recent_runs."""
        mock_client.query.return_value.get_points.return_value = []
        
        result = json.loads(mcp_server.handle_tool_call("get_recent_runs", {"limit": 5, "days": 14}))
        
        assert "runs" in result
    
    def test_handle_tool_call_with_exception(self, mcp_server, mock_client):
        """Test handle_tool_call with exception."""
        mock_client.query.side_effect = Exception("Connection failed")
        
        result = json.loads(mcp_server.handle_tool_call("get_sleep_analysis", {"days": 7}))
        
        # Should return error message, not crash
        assert "error" in result or "message" in result or "records" in result
    
    def test_get_tools_returns_all_tools(self, mcp_server):
        """Test that get_tools returns all expected tools."""
        tools = mcp_server.get_tools()
        
        tool_names = [t.name for t in tools]
        
        # Running & Training
        assert "get_recent_runs" in tool_names
        assert "get_training_load" in tool_names
        assert "get_pace_analysis" in tool_names
        assert "get_vo2max_progress" in tool_names
        assert "get_race_predictions" in tool_names
        assert "get_training_status" in tool_names
        assert "get_heart_rate_zones" in tool_names
        assert "get_long_runs" in tool_names
        
        # Sleep & Recovery
        assert "get_sleep_analysis" in tool_names
        assert "get_recovery_metrics" in tool_names
        assert "get_recovery_status" in tool_names
        assert "get_hrv_analysis" in tool_names
        
        # Health & Wellness
        assert "get_weekly_health_digest" in tool_names
        assert "get_stress_patterns" in tool_names
        assert "get_body_composition_trend" in tool_names
        assert "get_heart_rate_trends" in tool_names
        assert "get_activity_overview" in tool_names
        assert "get_wellness_score_summary" in tool_names
        assert "compare_weeks" in tool_names
        
        # Raw Database Access
        assert "query_influxdb" in tool_names
        assert "list_databases" in tool_names
        assert "list_measurements" in tool_names
        assert "show_field_keys" in tool_names
        assert "show_tag_keys" in tool_names
        
        # Total count
        assert len(tools) == 23


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_data_handling(self, mcp_server, mock_client):
        """Test handling of empty data."""
        mock_client.query.return_value.get_points.return_value = []
        
        # All these should handle empty data gracefully
        assert "message" in mcp_server.get_recent_runs() or "runs" in mcp_server.get_recent_runs()
        assert "message" in mcp_server.get_sleep_analysis() or "records" in mcp_server.get_sleep_analysis()
        assert "message" in mcp_server.get_hrv_analysis() or "readings" in mcp_server.get_hrv_analysis()
    
    def test_null_value_handling(self, mcp_server, mock_client):
        """Test handling of null values in data."""
        mock_client.query.return_value.get_points.return_value = [
            {
                "time": "2024-01-15T00:00:00Z",
                "distance": None,
                "movingDuration": None,
                "averageSpeed": None,
                "averageHR": None
            }
        ]
        
        result = mcp_server.get_recent_runs()
        
        # Should not crash, should return safe defaults
        assert "runs" in result
        if result["runs"]:
            assert result["runs"][0]["distance_km"] == 0
    
    def test_negative_values(self, mcp_server, mock_client):
        """Test handling of negative values."""
        mock_client.query.return_value.get_points.return_value = [
            {
                "time": "2024-01-15T00:00:00Z",
                "averageSpeed": -1  # Invalid negative speed
            }
        ]
        
        result = mcp_server.get_pace_analysis()
        
        # Should handle gracefully
        assert "message" in result or "run_count" in result
