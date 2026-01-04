"""
Friday Insights Engine - Report Generator

Generates formatted morning, evening, and weekly reports.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.core.config import get_brt
from src.insights.collectors import (
    CalendarCollector,
    HealthCollector,
    HomelabCollector,
    WeatherCollector,
)
from src.insights.config import InsightsConfig
from src.insights.models import Category, DeliveryChannel, Insight, Priority
from src.insights.store import InsightsStore

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
        now = datetime.now(get_brt())
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
        now = datetime.now(get_brt())
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
        now = datetime.now(get_brt())
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

            sync = data.get("sync_status", {})
            if sync.get("status") not in ["current", "recent"]:
                hours_ago = sync.get("hours_ago", 0)
                return f"Health\nGarmin data stale ({hours_ago:.0f}h ago)"

            lines = ["Health"]

            # Sleep
            sleep = data.get("sleep", {})
            sleep_score = sleep.get("score")
            sleep_dur = sleep.get("total_hours")
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
            if not self.homelab._initialized:
                self.homelab.initialize()
            data = self.homelab.collect()
            if not data:
                return None

            services = data.get("services", {})
            up = services.get("up", 0)
            total = services.get("total", 0)
            down = services.get("down_services", [])

            # Skip if no services are configured
            if total == 0:
                return None

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

            sync = data.get("sync_status", {})
            if sync.get("status") not in ["current", "recent"]:
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
            daily_stats = data.get("daily_stats", {})
            steps = daily_stats.get("steps")
            if steps:
                lines.append(f"Steps: {steps:,}")

            # Stress summary
            stress = data.get("stress", {})
            avg = stress.get("daily_avg")
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
        try:
            # Get health snapshots from past week (168 hours)
            snapshots = self.store.get_snapshots("health", hours=168, limit=200)
            if not snapshots:
                return None

            # Extract metrics from snapshots
            sleep_scores = []
            sleep_hours = []
            stress_avgs = []
            body_batteries = []
            steps_list = []
            hrv_values = []

            for snapshot in snapshots:
                data = snapshot.data

                # Sleep data
                sleep = data.get("sleep", {})
                if sleep.get("score"):
                    sleep_scores.append(sleep["score"])
                if sleep.get("total_hours"):
                    sleep_hours.append(sleep["total_hours"])
                if sleep.get("hrv"):
                    hrv_values.append(sleep["hrv"])

                # Stress data
                stress = data.get("stress", {})
                if stress.get("daily_avg"):
                    stress_avgs.append(stress["daily_avg"])

                # Body battery
                bb = data.get("body_battery", {})
                if bb.get("current"):
                    body_batteries.append(bb["current"])

                # Daily stats
                daily = data.get("daily_stats", {})
                if daily.get("steps"):
                    steps_list.append(daily["steps"])

            lines = ["Health Trends"]

            # Sleep summary
            if sleep_scores:
                avg_score = sum(sleep_scores) / len(sleep_scores)
                avg_hours = sum(sleep_hours) / len(sleep_hours) if sleep_hours else 0
                lines.append(f"  Sleep: avg {avg_score:.0f} score, {avg_hours:.1f}h/night")

                # Trend indicator
                if len(sleep_scores) >= 3:
                    recent = sum(sleep_scores[:3]) / 3
                    older = sum(sleep_scores[-3:]) / 3
                    if recent > older + 5:
                        lines[-1] += " (improving)"
                    elif recent < older - 5:
                        lines[-1] += " (declining)"

            # Stress summary
            if stress_avgs:
                avg_stress = sum(stress_avgs) / len(stress_avgs)
                max_stress = max(stress_avgs)
                lines.append(f"  Stress: avg {avg_stress:.0f}, peak {max_stress}")

            # HRV summary
            if hrv_values:
                avg_hrv = sum(hrv_values) / len(hrv_values)
                lines.append(f"  HRV: avg {avg_hrv:.0f}ms")

            # Activity summary
            if steps_list:
                avg_steps = sum(steps_list) / len(steps_list)
                total_steps = sum(steps_list)
                lines.append(f"  Steps: {avg_steps:,.0f} avg/day, {total_steps:,.0f} total")

            # Body battery summary
            if body_batteries:
                avg_bb = sum(body_batteries) / len(body_batteries)
                lines.append(f"  Body Battery: avg {avg_bb:.0f}%")

            return "\n".join(lines) if len(lines) > 1 else None

        except Exception as e:
            logger.error(f"[REPORTS] Health trends error: {e}")
            return None

    def _generate_calendar_summary(self) -> Optional[str]:
        """Generate calendar summary for weekly report."""
        try:
            # Get calendar snapshots from past week
            snapshots = self.store.get_snapshots("calendar", hours=168, limit=50)
            if not snapshots:
                # Fallback to current week data from collector
                data = self.calendar.collect()
                if not data:
                    return None
                week = data.get("week_summary", {})
                if not week:
                    return None

                lines = ["Calendar Summary"]
                total_events = week.get("total_events", 0)
                total_meetings = week.get("total_meetings", 0)
                meeting_hours = week.get("total_meeting_hours", 0)
                busiest = week.get("busiest_day")

                if total_events > 0:
                    lines.append(f"  {total_events} events, {total_meetings} meetings")
                    lines.append(f"  {meeting_hours:.1f}h in meetings")
                    if busiest:
                        busiest_hours = week.get("busiest_day_hours", 0)
                        lines.append(f"  Busiest: {busiest} ({busiest_hours:.1f}h)")

                return "\n".join(lines) if len(lines) > 1 else None

            # Aggregate data from snapshots
            total_events = 0
            total_meetings = 0
            total_meeting_hours = 0
            days_with_conflicts = 0
            busiest_day = None
            busiest_day_hours = 0
            days_by_name = {}

            seen_dates = set()
            for snapshot in snapshots:
                data = snapshot.data

                # Get today's data from each snapshot (avoid double counting)
                today = data.get("today", {})
                if not today:
                    continue

                # Extract date from snapshot timestamp
                snapshot_date = snapshot.timestamp.strftime("%Y-%m-%d")
                if snapshot_date in seen_dates:
                    continue
                seen_dates.add(snapshot_date)

                event_count = today.get("event_count", 0)
                meeting_count = today.get("meeting_count", 0)
                meeting_hours = today.get("meeting_hours", 0)
                has_conflicts = today.get("has_conflicts", False)

                total_events += event_count
                total_meetings += meeting_count
                total_meeting_hours += meeting_hours
                if has_conflicts:
                    days_with_conflicts += 1

                # Track busiest day
                day_name = snapshot.timestamp.strftime("%A")
                days_by_name[day_name] = days_by_name.get(day_name, 0) + meeting_hours
                if meeting_hours > busiest_day_hours:
                    busiest_day_hours = meeting_hours
                    busiest_day = day_name

            if total_events == 0:
                return None

            lines = ["Calendar Summary"]
            lines.append(f"  {total_events} events, {total_meetings} meetings")
            lines.append(f"  {total_meeting_hours:.1f}h in meetings")

            if busiest_day:
                lines.append(f"  Busiest: {busiest_day} ({busiest_day_hours:.1f}h)")

            if days_with_conflicts > 0:
                lines.append(f"  {days_with_conflicts} days with conflicts")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"[REPORTS] Calendar summary error: {e}")
            return None

    def _generate_system_summary(self) -> Optional[str]:
        """Generate system summary for weekly report."""
        try:
            # Get homelab snapshots from past week
            snapshots = self.store.get_snapshots("homelab", hours=168, limit=200)

            if not snapshots:
                # Fallback to current data
                data = self.homelab.collect()
                if not data:
                    return None

                services = data.get("services", {})
                local = data.get("local", {})

                lines = ["System Summary"]
                total = services.get("total", 0)
                up = services.get("up", 0)
                if total > 0:
                    lines.append(f"  Services: {up}/{total} up")

                if local:
                    lines.append(f"  Local: {local.get('memory_percent', 0):.0f}% mem, {local.get('disk_percent', 0):.0f}% disk")
                    if local.get("gpu_temp"):
                        lines.append(f"  GPU: {local['gpu_temp']}C")

                return "\n".join(lines) if len(lines) > 1 else None

            # Aggregate data from snapshots
            service_downtimes = {}  # service_name -> count of down occurrences
            total_checks = 0
            cpu_values = []
            memory_values = []
            disk_values = []
            gpu_temps = []

            for snapshot in snapshots:
                data = snapshot.data

                # Service health
                services = data.get("services", {})
                if services:
                    total_checks += 1
                    down_services = services.get("down_services", [])
                    for svc in down_services:
                        service_downtimes[svc] = service_downtimes.get(svc, 0) + 1

                # Hardware stats
                hardware = data.get("hardware", {})
                servers = hardware.get("servers", [])
                for srv in servers:
                    if srv.get("status") == "ok":
                        if srv.get("cpu_percent"):
                            cpu_values.append(srv["cpu_percent"])
                        if srv.get("memory_percent"):
                            memory_values.append(srv["memory_percent"])
                        if srv.get("disk_percent"):
                            disk_values.append(srv["disk_percent"])

                # Local stats
                local = data.get("local", {})
                if local:
                    if local.get("memory_percent"):
                        memory_values.append(local["memory_percent"])
                    if local.get("disk_percent"):
                        disk_values.append(local["disk_percent"])
                    if local.get("gpu_temp"):
                        gpu_temps.append(local["gpu_temp"])

            lines = ["System Summary"]

            # Service uptime
            if total_checks > 0:
                problematic = [(svc, count) for svc, count in service_downtimes.items()
                               if count >= 2]  # At least 2 downtimes
                if problematic:
                    problematic.sort(key=lambda x: -x[1])
                    top_issues = problematic[:3]
                    issues_str = ", ".join(f"{svc} ({count}x)" for svc, count in top_issues)
                    lines.append(f"  Issues: {issues_str}")
                else:
                    lines.append("  Services: All stable")

            # Resource averages
            if cpu_values:
                avg_cpu = sum(cpu_values) / len(cpu_values)
                max_cpu = max(cpu_values)
                lines.append(f"  CPU: avg {avg_cpu:.0f}%, peak {max_cpu:.0f}%")

            if memory_values:
                avg_mem = sum(memory_values) / len(memory_values)
                max_mem = max(memory_values)
                lines.append(f"  Memory: avg {avg_mem:.0f}%, peak {max_mem:.0f}%")

            if disk_values:
                max_disk = max(disk_values)
                lines.append(f"  Disk: max {max_disk:.0f}% used")

            if gpu_temps:
                avg_gpu = sum(gpu_temps) / len(gpu_temps)
                max_gpu = max(gpu_temps)
                lines.append(f"  GPU: avg {avg_gpu:.0f}C, peak {max_gpu}C")

            return "\n".join(lines) if len(lines) > 1 else None

        except Exception as e:
            logger.error(f"[REPORTS] System summary error: {e}")
            return None
