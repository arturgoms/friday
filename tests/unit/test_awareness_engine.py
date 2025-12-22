"""Tests for the AwarenessEngine."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from app.services.awareness_engine import AwarenessEngine, PatternData
from app.services.proactive_monitor import ProactiveAlert, AlertPriority


@pytest.fixture
def engine():
    """Create an AwarenessEngine with mocked dependencies."""
    with patch('app.services.awareness_engine.settings') as mock_settings:
        mock_settings.paths.data = MagicMock()
        mock_settings.paths.data.__truediv__ = lambda self, x: MagicMock()
        mock_settings.user_timezone = MagicMock()
        mock_settings.awareness.daily_message_limit = 5
        mock_settings.awareness.urgent_exempt = True
        mock_settings.awareness.alert_cooldown_minutes = 60
        
        with patch.object(AwarenessEngine, '_load_patterns', return_value=PatternData()):
            with patch.object(AwarenessEngine, '_load_cooldowns', return_value={}):
                with patch.object(AwarenessEngine, '_load_acked', return_value={}):
                    engine = AwarenessEngine()
                    yield engine


class TestPatternData:
    """Tests for PatternData dataclass."""
    
    def test_default_values(self):
        """Test default pattern values."""
        p = PatternData()
        
        assert p.avg_bedtime_hour == 23.0
        assert p.avg_wake_hour == 7.0
        assert p.sleep_consistency_score == 0.0
        assert p.avg_workouts_per_week == 0.0
        assert p.typical_workout_days == []
        assert p.days_since_last_workout == 0
    
    def test_custom_values(self):
        """Test pattern with custom values."""
        p = PatternData(
            avg_bedtime_hour=22.5,
            sleep_consistency_score=85.0,
            avg_workouts_per_week=3.5,
            typical_workout_days=[0, 2, 4],  # Mon, Wed, Fri
        )
        
        assert p.avg_bedtime_hour == 22.5
        assert p.sleep_consistency_score == 85.0
        assert p.avg_workouts_per_week == 3.5
        assert p.typical_workout_days == [0, 2, 4]


class TestWorkoutReadinessCheck:
    """Tests for check_workout_readiness fusion check."""
    
    def test_no_alerts_when_no_workout_events(self, engine):
        """Test no alerts when calendar has no workout events."""
        engine._health_coach = MagicMock()
        engine._calendar_service = MagicMock()
        engine._calendar_service.get_today_events.return_value = [
            MagicMock(summary="Team Meeting", start=datetime.now() + timedelta(hours=2))
        ]
        
        alerts = engine.check_workout_readiness()
        
        assert len(alerts) == 0
    
    def test_alert_on_low_training_readiness(self, engine):
        """Test alert when training readiness is low before workout."""
        # Mock health coach
        engine._health_coach = MagicMock()
        engine._health_coach.get_recovery_status.return_value = {
            'body_battery': 20,
            'training_readiness': 25,
            'recovery_time': 24
        }
        
        # Mock calendar with workout event
        from datetime import timezone
        workout_time = datetime.now(timezone.utc) + timedelta(hours=2)
        workout_event = MagicMock()
        workout_event.summary = "Gym Workout"
        workout_event.start = workout_time
        
        engine._calendar_service = MagicMock()
        engine._calendar_service.get_today_events.return_value = [workout_event]
        
        with patch.object(engine, '_should_send_alert', return_value=True):
            with patch.object(engine, '_mark_alert_sent'):
                with patch('app.services.awareness_engine.settings') as mock_settings:
                    mock_settings.user_timezone = timezone.utc
                    alerts = engine.check_workout_readiness()
        
        assert len(alerts) >= 1
        assert any('workout' in a.title.lower() or 'gym' in a.title.lower() for a in alerts)
        assert any(a.priority in [AlertPriority.HIGH, AlertPriority.MEDIUM] for a in alerts)


class TestMeetingPreparednessCheck:
    """Tests for check_meeting_preparedness fusion check."""
    
    def test_no_alerts_when_no_meetings(self, engine):
        """Test no alerts when no meetings in calendar."""
        engine._calendar_service = MagicMock()
        engine._calendar_service.get_today_events.return_value = [
            MagicMock(summary="Lunch Break", start=datetime.now() + timedelta(hours=1))
        ]
        engine._vector_store = MagicMock()
        
        alerts = engine.check_meeting_preparedness()
        
        assert len(alerts) == 0


class TestErrandOpportunitiesCheck:
    """Tests for check_errand_opportunities fusion check."""
    
    def test_no_alerts_when_no_errands(self, engine):
        """Test no alerts when no errands in task list."""
        from datetime import timezone
        
        # Mock calendar with outing
        event_time = datetime.now(timezone.utc) + timedelta(hours=2)
        event = MagicMock()
        event.summary = "Dentist Appointment"
        event.start = event_time
        
        engine._calendar_service = MagicMock()
        engine._calendar_service.get_today_events.return_value = [event]
        
        # Mock task manager with no errands
        engine._task_manager = MagicMock()
        engine._task_manager.list_tasks.return_value = []
        
        with patch('app.services.awareness_engine.settings') as mock_settings:
            mock_settings.user_timezone = timezone.utc
            alerts = engine.check_errand_opportunities()
        
        assert len(alerts) == 0


class TestSleepConsistencyCheck:
    """Tests for check_sleep_consistency pattern check."""
    
    def test_no_alert_when_sleep_good(self, engine):
        """Test no alert when sleep score is good."""
        engine._health_coach = MagicMock()
        engine._health_coach.get_sleep_data.return_value = {
            'sleep_records': [{'sleep_score': 85}]
        }
        engine._patterns.sleep_consistency_score = 80
        
        alerts = engine.check_sleep_consistency()
        
        assert len(alerts) == 0
    
    def test_alert_on_poor_sleep_with_good_baseline(self, engine):
        """Test alert when sleep is poor but user usually sleeps well."""
        engine._health_coach = MagicMock()
        engine._health_coach.get_sleep_data.return_value = {
            'sleep_records': [{'sleep_score': 45}]
        }
        engine._patterns.sleep_consistency_score = 85  # Usually consistent
        
        with patch.object(engine, '_should_send_alert', return_value=True):
            with patch.object(engine, '_mark_alert_sent'):
                alerts = engine.check_sleep_consistency()
        
        assert len(alerts) == 1
        assert 'pattern' in alerts[0].title.lower() or 'sleep' in alerts[0].title.lower()


class TestWorkoutFrequencyCheck:
    """Tests for check_workout_frequency pattern check."""
    
    def test_no_alert_when_no_workout_pattern(self, engine):
        """Test no alert when user doesn't have a workout pattern."""
        engine._patterns.avg_workouts_per_week = 0.5  # Less than 1
        
        alerts = engine.check_workout_frequency()
        
        assert len(alerts) == 0
    
    def test_alert_when_workout_gap_too_long(self, engine):
        """Test alert when workout gap exceeds typical interval."""
        engine._patterns.avg_workouts_per_week = 3  # 3x per week = every ~2.3 days
        engine._patterns.days_since_last_workout = 5  # More than 1.5x typical
        
        with patch.object(engine, '_should_send_alert', return_value=True):
            with patch.object(engine, '_mark_alert_sent'):
                alerts = engine.check_workout_frequency()
        
        assert len(alerts) == 1
        assert 'workout' in alerts[0].title.lower() or 'pattern' in alerts[0].title.lower()


class TestInfrastructureChecks:
    """Tests for infrastructure monitoring."""
    
    def test_disk_space_warning(self, engine):
        """Test disk space warning at 80%."""
        with patch('shutil.disk_usage') as mock_disk:
            # 85% used
            total = 100 * 1024**3  # 100 GB
            used = 85 * 1024**3   # 85 GB
            free = 15 * 1024**3   # 15 GB
            mock_disk.return_value = (total, used, free)
            
            with patch.object(engine, '_should_send_alert', return_value=True):
                with patch.object(engine, '_mark_alert_sent'):
                    alerts = engine._check_disk_space()
        
        assert len(alerts) == 1
        assert 'disk' in alerts[0].title.lower()
        assert alerts[0].priority == AlertPriority.MEDIUM
    
    def test_disk_space_critical(self, engine):
        """Test disk space critical at 90%+."""
        with patch('shutil.disk_usage') as mock_disk:
            # 95% used
            total = 100 * 1024**3
            used = 95 * 1024**3
            free = 5 * 1024**3
            mock_disk.return_value = (total, used, free)
            
            with patch.object(engine, '_should_send_alert', return_value=True):
                with patch.object(engine, '_mark_alert_sent'):
                    alerts = engine._check_disk_space()
        
        assert len(alerts) == 1
        assert alerts[0].priority == AlertPriority.URGENT
    
    def test_service_down_alert(self, engine):
        """Test alert when a service is down."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(stdout='inactive')
            
            with patch.object(engine, '_should_send_alert', return_value=True):
                with patch.object(engine, '_mark_alert_sent'):
                    alerts = engine._check_services()
        
        # Should have alerts for services reporting as inactive
        assert len(alerts) >= 1
        assert any('service' in a.title.lower() or 'down' in a.title.lower() for a in alerts)


class TestGetPatterns:
    """Tests for get_patterns method."""
    
    def test_get_patterns_returns_dict(self, engine):
        """Test that get_patterns returns expected structure."""
        engine._patterns = PatternData(
            sleep_consistency_score=75,
            avg_workouts_per_week=3,
            typical_workout_days=[0, 2, 4],
            days_since_last_workout=2,
            last_workout_date='2025-01-15',
            last_updated='2025-01-16T10:00:00'
        )
        
        patterns = engine.get_patterns()
        
        assert 'sleep' in patterns
        assert 'workouts' in patterns
        assert 'last_updated' in patterns
        
        assert patterns['sleep']['consistency_score'] == 75
        assert patterns['workouts']['avg_per_week'] == 3
        assert patterns['workouts']['typical_days'] == ['Mon', 'Wed', 'Fri']
        assert patterns['workouts']['days_since_last'] == 2


class TestGetInfrastructureStatus:
    """Tests for get_infrastructure_status method."""
    
    def test_get_infrastructure_status_structure(self, engine):
        """Test infrastructure status returns expected structure."""
        with patch('shutil.disk_usage') as mock_disk:
            mock_disk.return_value = (100 * 1024**3, 50 * 1024**3, 50 * 1024**3)
            
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(stdout='active')
                
                status = engine.get_infrastructure_status()
        
        assert 'checked_at' in status
        assert 'disk' in status
        assert 'services' in status
        
        assert 'total_gb' in status['disk']
        assert 'used_gb' in status['disk']
        assert 'free_gb' in status['disk']
        assert 'percent_used' in status['disk']


class TestRunAllChecks:
    """Tests for the main run_all_checks method."""
    
    def test_run_all_checks_includes_fusion_checks(self, engine):
        """Test that run_all_checks includes the new fusion checks."""
        # Mock all the check methods
        with patch.object(engine, 'check_health_alerts', return_value=[]):
            with patch.object(engine, 'check_calendar_alerts', return_value=[]):
                with patch.object(engine, 'check_task_alerts', return_value=[]):
                    with patch.object(engine, 'check_weather_alerts', return_value=[]):
                        with patch.object(engine, 'check_activity_patterns', return_value=[]):
                            with patch.object(engine, 'check_dynamic_alerts', return_value=[]):
                                with patch.object(engine, 'check_vault_health', return_value=[]):
                                    with patch.object(engine, 'check_commitment_follow_ups', return_value=[]):
                                        with patch.object(engine, 'check_conversation_staleness', return_value=[]):
                                            with patch.object(engine, 'check_workout_readiness', return_value=[]) as mock_workout:
                                                with patch.object(engine, 'check_post_workout_recovery', return_value=[]) as mock_recovery:
                                                    with patch.object(engine, 'check_meeting_preparedness', return_value=[]) as mock_meeting:
                                                        with patch.object(engine, 'check_errand_opportunities', return_value=[]) as mock_errand:
                                                            with patch.object(engine, 'check_sleep_consistency', return_value=[]) as mock_sleep:
                                                                with patch.object(engine, 'check_workout_frequency', return_value=[]) as mock_freq:
                                                                    with patch.object(engine, 'check_infrastructure', return_value=[]) as mock_infra:
                                                                        engine.run_all_checks()
        
        # Verify fusion checks were called
        mock_workout.assert_called_once()
        mock_recovery.assert_called_once()
        mock_meeting.assert_called_once()
        mock_errand.assert_called_once()
        
        # Verify pattern checks were called
        mock_sleep.assert_called_once()
        mock_freq.assert_called_once()
        
        # Verify infrastructure check was called
        mock_infra.assert_called_once()
