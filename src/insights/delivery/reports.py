"""
Friday Insights Engine - Report Generator

Generates formatted morning, evening, and weekly reports.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging

from src.insights.models import (
    Insight, Priority, Category, BRT, DeliveryChannel
)
from src.insights.config import InsightsConfig
from src.insights.store import InsightsStore
from src.insights.collectors import (
    HealthCollector, CalendarCollector, HomelabCollector, WeatherCollector
)

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Generates formatted reports for scheduled delivery.
    
    Report types:
    - Morning: Day overview (weather, calendar, health status)
    - Evening: Day summary (what happened, health recap)
    - Weekly: Week analysis (trends, patterns, insights)
    """
    
    def __init__(self, config: InsightsConfig, store: InsightsStore):
        self.config = config
        self.store = store
        
        # Initialize collectors
        self.health = HealthCollector()
        self.calendar = CalendarCollector()
        self.homelab = HomelabCollector()
        self.weather = WeatherCollector()
    
    def generate_morning_report(self) -> str:
        """Generate morning briefing report."""
        now = datetime.now(BRT)
        sections = []
        
        # Header
        sections.append(f"Good morning! Here's your briefing for {now.strftime('%A, %b %d')}")
        sections.append("")
        
        # Weather
        weather_section = self._generate_weather_section()
        if weather_section:
            sections.append(weather_section)
            sections.append("")
        
        # Calendar
        calendar_section = self._generate_calendar_section()
        if calendar_section:
            sections.append(calendar_section)
            sections.append("")
        
        # Health status
        health_section = self._generate_health_section()
        if health_section:
            sections.append(health_section)
            sections.append("")
        
        # Homelab status (brief)
        homelab_section = self._generate_homelab_brief()
        if homelab_section:
            sections.append(homelab_section)
        
        return "\n".join(sections)
    
    def generate_evening_report(self) -> str:
        """Generate evening summary report."""
        now = datetime.now(BRT)
        sections = []
        
        # Header
        sections.append(f"Good evening! Here's your day summary for {now.strftime('%A, %b %d')}")
        sections.append("")
        
        # Health recap
        health_section = self._generate_health_recap()
        if health_section:
            sections.append(health_section)
            sections.append("")
        
        # Calendar recap
        calendar_section = self._generate_calendar_recap()
        if calendar_section:
            sections.append(calendar_section)
            sections.append("")
        
        # Tomorrow preview
        tomorrow_section = self._generate_tomorrow_preview()
        if tomorrow_section:
            sections.append(tomorrow_section)
            sections.append("")
        
        # Homelab status
        homelab_section = self._generate_homelab_brief()
        if homelab_section:
            sections.append(homelab_section)
        
        return "\n".join(sections)
    
    def generate_weekly_report(self) -> str:
        """Generate weekly summary report."""
        now = datetime.now(BRT)
        sections = []
        
        # Header
        week_start = now - timedelta(days=7)
        sections.append(f"Weekly Summary ({week_start.strftime('%b %d')} - {now.strftime('%b %d')})")
        sections.append("")
        
        # Health trends
        health_trends = self._generate_health_trends()
        if health_trends:
            sections.append(health_trends)
            sections.append("")
        
        # Calendar summary
        calendar_summary = self._generate_calendar_summary()
        if calendar_summary:
            sections.append(calendar_summary)
            sections.append("")
        
        # System health
        system_summary = self._generate_system_summary()
        if system_summary:
            sections.append(system_summary)
        
        return "\n".join(sections)
    
    def _generate_weather_section(self) -> Optional[str]:
        """Generate weather section for morning report."""
        try:
            data = self.weather.collect()
            if not data:
                return None
            
            current = data.get("current", {})
            temp = current.get("temp")
            desc = current.get("description", "")
            feels_like = current.get("feels_like")
            humidity = current.get("humidity")
            
            if temp is None:
                return None
            
            lines = ["Weather"]
            lines.append(f"Currently {temp:.0f}°C, {desc}")
            if feels_like and abs(feels_like - temp) > 2:
                lines.append(f"Feels like {feels_like:.0f}°C")
            
            # Today's forecast
            forecast = data.get("today", {})
            if forecast:
                high = forecast.get("high")
                low = forecast.get("low")
                if high and low:
                    lines.append(f"High {high:.0f}°C, Low {low:.0f}°C")
            
            # Check for rain
            rain_chance = current.get("rain_chance")
            if rain_chance and rain_chance > 30:
                lines.append(f"Rain chance: {rain_chance}%")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Weather section error: {e}")
            return None
    
    def _generate_calendar_section(self) -> Optional[str]:
        """Generate calendar section for morning report."""
        try:
            data = self.calendar.collect()
            if not data:
                return None
            
            today = data.get("today", {})
            events = today.get("events", []) if isinstance(today, dict) else today
            
            if not events:
                return "Calendar\nNo events scheduled today"
            
            lines = ["Calendar"]
            
            # Count meetings
            meetings = [e for e in events if not e.get("all_day")]
            all_day = [e for e in events if e.get("all_day")]
            
            if all_day:
                lines.append(f"All day: {', '.join(e.get('title', 'Event') for e in all_day)}")
            
            lines.append(f"{len(meetings)} meetings today")
            
            # List upcoming meetings
            for event in meetings[:5]:
                title = event.get("title", "Event")[:30]
                start = event.get("start", "")
                if "T" in start:
                    time_str = datetime.fromisoformat(start.replace("Z", "+00:00")).strftime("%H:%M")
                    lines.append(f"  {time_str} - {title}")
            
            if len(meetings) > 5:
                lines.append(f"  ... and {len(meetings) - 5} more")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Calendar section error: {e}")
            return None
    
    def _generate_health_section(self) -> Optional[str]:
        """Generate health section for morning report."""
        try:
            data = self.health.collect()
            if not data:
                return None
            
            sync = data.get("sync", {})
            if sync.get("status") != "fresh":
                hours_ago = sync.get("hours_ago", 0)
                return f"Health\nGarmin data stale ({hours_ago:.0f}h ago)"
            
            lines = ["Health"]
            
            # Sleep
            sleep = data.get("sleep", {})
            sleep_score = sleep.get("sleep_score")
            sleep_dur = sleep.get("duration_hours")
            if sleep_score:
                lines.append(f"Sleep: {sleep_score} ({sleep_dur:.1f}h)" if sleep_dur else f"Sleep score: {sleep_score}")
            
            # Body battery
            bb = data.get("body_battery", {}).get("current")
            if bb:
                lines.append(f"Body battery: {bb}%")
            
            # Stress
            stress = data.get("stress", {}).get("current")
            if stress and stress > 0:
                lines.append(f"Stress: {stress}")
            
            return "\n".join(lines) if len(lines) > 1 else None
            
        except Exception as e:
            logger.error(f"Health section error: {e}")
            return None
    
    def _generate_homelab_brief(self) -> Optional[str]:
        """Generate brief homelab status."""
        try:
            self.homelab.initialize()
            data = self.homelab.collect()
            if not data:
                return None
            
            services = data.get("services", {})
            up = services.get("up", 0)
            total = services.get("total", 0)
            down = services.get("down_services", [])
            
            if down:
                return f"Homelab: {up}/{total} services ({len(down)} down: {', '.join(down[:3])})"
            else:
                return f"Homelab: All {total} services running"
            
        except Exception as e:
            logger.error(f"Homelab section error: {e}")
            return None
    
    def _generate_health_recap(self) -> Optional[str]:
        """Generate health recap for evening report."""
        try:
            data = self.health.collect()
            if not data:
                return None
            
            sync = data.get("sync", {})
            if sync.get("status") != "fresh":
                return None
            
            lines = ["Health Recap"]
            
            # Body battery change
            bb = data.get("body_battery", {})
            current = bb.get("current")
            high = bb.get("high")
            low = bb.get("low")
            if current and high and low:
                lines.append(f"Body battery: {current}% (range: {low}-{high}%)")
            
            # Steps
            activity = data.get("activity", {})
            steps = activity.get("steps")
            if steps:
                lines.append(f"Steps: {steps:,}")
            
            # Stress summary
            stress = data.get("stress", {})
            avg = stress.get("average")
            if avg:
                lines.append(f"Average stress: {avg}")
            
            return "\n".join(lines) if len(lines) > 1 else None
            
        except Exception as e:
            logger.error(f"Health recap error: {e}")
            return None
    
    def _generate_calendar_recap(self) -> Optional[str]:
        """Generate calendar recap for evening."""
        try:
            data = self.calendar.collect()
            if not data:
                return None
            
            today = data.get("today", {})
            if isinstance(today, dict):
                meeting_count = today.get("meeting_count", 0)
                meeting_hours = today.get("meeting_hours", 0)
            else:
                return None
            
            if meeting_count == 0:
                return "Calendar: No meetings today"
            
            return f"Calendar: {meeting_count} meetings ({meeting_hours:.1f}h total)"
            
        except Exception as e:
            logger.error(f"Calendar recap error: {e}")
            return None
    
    def _generate_tomorrow_preview(self) -> Optional[str]:
        """Generate tomorrow preview for evening report."""
        try:
            data = self.calendar.collect()
            if not data:
                return None
            
            tomorrow = data.get("tomorrow", {})
            if not tomorrow:
                return None
            
            if isinstance(tomorrow, dict):
                count = tomorrow.get("event_count", 0)
                meeting_count = tomorrow.get("meeting_count", 0)
            else:
                return None
            
            if count == 0:
                return "Tomorrow: No events scheduled"
            
            return f"Tomorrow: {meeting_count} meetings, {count} total events"
            
        except Exception as e:
            logger.error(f"Tomorrow preview error: {e}")
            return None
    
    def _generate_health_trends(self) -> Optional[str]:
        """Generate health trends for weekly report."""
        # TODO: Implement weekly health analysis from snapshots
        return None
    
    def _generate_calendar_summary(self) -> Optional[str]:
        """Generate calendar summary for weekly report."""
        # TODO: Implement weekly calendar analysis
        return None
    
    def _generate_system_summary(self) -> Optional[str]:
        """Generate system summary for weekly report."""
        # TODO: Implement weekly system analysis
        return None
