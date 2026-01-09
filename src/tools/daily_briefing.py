"""
Friday 3.0 Daily Briefing Tools

Morning and evening reports with personalized insights.
"""

import sys
from pathlib import Path

# Add parent directory to path to import agent
_parent_dir = Path(__file__).parent.parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

from src.core.agent import agent

import logging
import zoneinfo
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from settings import settings
from src.core.influxdb import query as _query
from src.core.utils import format_duration

logger = logging.getLogger(__name__)

# Get user timezone
USER_TZ = zoneinfo.ZoneInfo(settings.USER["timezone"])


# =============================================================================
# Report Data Classes
# =============================================================================

@dataclass
class ReportContext:
    """Context for building a daily report."""
    now: datetime
    today_str: str
    lines: List[str] = field(default_factory=list)
    insights: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def add_section(self, title: str):
        """Add a section header."""
        if self.lines:
            self.lines.append("")
        self.lines.append(title)
    
    def add_line(self, line: str, indent: bool = False):
        """Add a line to the report."""
        self.lines.append(f"  {line}" if indent else line)
    
    def add_insight(self, insight: str):
        """Add a positive insight."""
        self.insights.append(insight)
    
    def add_warning(self, warning: str):
        """Add a warning."""
        self.warnings.append(warning)


# =============================================================================
# Garmin Sync Check
# =============================================================================

def _check_garmin_sync_freshness() -> Tuple[bool, Optional[float], Optional[str]]:
    """Check if Garmin data is fresh enough for today's report.
    
    Returns:
        Tuple of (is_fresh, hours_ago, last_sync_time_str)
    """
    points = _query('SELECT last("HeartRate") FROM "HeartRateIntraday"')
    
    if not points:
        return False, None, None
    
    last_time_str = points[0].get("time", "")
    if not last_time_str:
        return False, None, None
    
    try:
        last_time = datetime.fromisoformat(last_time_str.replace("Z", "+00:00"))
        now_utc = datetime.now(timezone.utc)
        hours_ago = (now_utc - last_time).total_seconds() / 3600
        
        # Convert to user timezone for display
        last_time_local = last_time.astimezone(USER_TZ)
        time_str = last_time_local.strftime("%H:%M")
        
        # Consider fresh if synced within last 6 hours
        is_fresh = hours_ago < 6
        return is_fresh, hours_ago, time_str
        
    except Exception:
        return False, None, None


def _add_sync_warning(ctx: ReportContext, hours_ago: Optional[float], 
                      last_sync_time: Optional[str]) -> bool:
    """Add Garmin sync warning to report if data is stale.
    
    Returns:
        True if data is fresh, False otherwise
    """
    garmin_fresh, hours_ago, last_sync_time = _check_garmin_sync_freshness()
    
    if not garmin_fresh:
        if hours_ago is not None:
            ctx.add_line(f"⚠️ **GARMIN LAST SYNCED**: {hours_ago:.1f}h ago (at {last_sync_time})")
            ctx.add_line("Some metrics may be outdated. Sync your watch for latest data.")
            ctx.add_line("")
            if hours_ago > 12:
                ctx.add_warning("Garmin hasn't synced in over 12 hours.")
        else:
            ctx.add_line("⚠️ **GARMIN SYNC UNAVAILABLE**: Could not verify data freshness.")
            ctx.add_line("")
    
    return garmin_fresh


# =============================================================================
# Morning Report Sections
# =============================================================================

def _build_sleep_section(ctx: ReportContext, garmin_fresh: bool) -> int:
    """Build sleep section for morning report.

    Returns:
        Sleep score (0 if unavailable)
    """
    ctx.add_section("*LAST NIGHT'S SLEEP*")

    # Try to fetch data regardless of sync freshness
    sleep_data = _query("""
        SELECT sleepScore, deepSleepSeconds, lightSleepSeconds, remSleepSeconds,
               avgOvernightHrv, restingHeartRate, time
        FROM SleepSummary ORDER BY time DESC LIMIT 1
    """)

    if not sleep_data:
        ctx.add_line("_No sleep data available_")
        return 0

    sleep = sleep_data[0]
    sleep_date = sleep.get("time", "").split("T")[0]
    yesterday = (ctx.now - timedelta(days=1)).strftime("%Y-%m-%d")

    if sleep_date not in [ctx.today_str, yesterday]:
        ctx.add_line(f"_Data outdated ({sleep_date})_")
        return 0

    # Parse sleep data
    deep = sleep.get("deepSleepSeconds", 0) or 0
    light = sleep.get("lightSleepSeconds", 0) or 0
    rem = sleep.get("remSleepSeconds", 0) or 0
    total_hours = (deep + light + rem) / 3600

    sleep_score = sleep.get("sleepScore", 0) or 0
    hrv = int(sleep.get("avgOvernightHrv", 0) or 0)
    rhr = int(sleep.get("restingHeartRate", 0) or 0)

    # Determine quality description
    if sleep_score >= 80:
        quality = "Excellent"
        ctx.add_insight("Great sleep - you're ready for a productive day.")
    elif sleep_score >= 65:
        quality = "Good"
    elif sleep_score >= 50:
        quality = "Fair"
        ctx.add_warning("Sleep was below average. Consider earlier bedtime tonight.")
    else:
        quality = "Poor"
        ctx.add_warning("Poor sleep - take it easy today.")

    ctx.add_line(f"• *Score:* {sleep_score}/100 _{quality}_")
    ctx.add_line(f"• *Duration:* {total_hours:.1f}h (Deep: {format_duration(deep)}, REM: {format_duration(rem)})")
    ctx.add_line(f"• *HRV:* {hrv}ms | *RHR:* {rhr}bpm")

    return sleep_score


def _build_energy_section(ctx: ReportContext, garmin_fresh: bool):
    """Build energy/recovery section for morning report."""
    ctx.add_section("*ENERGY & RECOVERY*")

    # Try to fetch data regardless of sync freshness
    # Body battery
    bb_data = _query("SELECT bodyBatteryAtWakeTime, time FROM DailyStats ORDER BY time DESC LIMIT 1")

    if bb_data:
        bb_date = bb_data[0].get("time", "").split("T")[0]
        if bb_date == ctx.today_str:
            body_battery = int(bb_data[0].get("bodyBatteryAtWakeTime", 0) or 0)

            if body_battery >= 80:
                bb_desc = "Fully charged"
                ctx.add_insight("High energy - great day for challenging tasks.")
            elif body_battery >= 60:
                bb_desc = "Good"
            elif body_battery >= 40:
                bb_desc = "Moderate"
            else:
                bb_desc = "Low"
                ctx.add_warning("Low energy - avoid overexertion.")

            ctx.add_line(f"• *Body Battery:* {body_battery}/100 _{bb_desc}_")
        else:
            ctx.add_line(f"_Data from {bb_date} (not today)_")
    else:
        ctx.add_line("_Body Battery data not available_")

    # Training readiness
    tr_data = _query("SELECT score, level, time FROM TrainingReadiness ORDER BY time DESC LIMIT 1")

    if tr_data:
        tr_date = tr_data[0].get("time", "").split("T")[0]
        if tr_date == ctx.today_str:
            tr_score = int(tr_data[0].get("score", 0) or 0)
            tr_level = tr_data[0].get("level", "").title()
            ctx.add_line(f"• *Training Readiness:* {tr_score}/100 _{tr_level}_")

            if tr_score < 50:
                ctx.add_warning("Low training readiness - rest or light activity only.")


def _build_calendar_section(ctx: ReportContext):
    """Build calendar section for morning report."""
    ctx.add_section("*TODAY'S SCHEDULE*")

    try:
        from src.tools.calendar import get_today_schedule

        schedule = get_today_schedule()

        if isinstance(schedule, dict) and not schedule.get("error"):
            # Combine all event types
            current_events = schedule.get("current_events", [])
            upcoming_events = schedule.get("upcoming_events", [])
            completed_events = schedule.get("completed_events", [])
            all_events = current_events + upcoming_events + completed_events

            if all_events:
                meeting_count = 0
                for event in all_events:
                    if event.get("all_day"):
                        ctx.add_line(f"• _All day:_ {event['title']}")
                    else:
                        cal_label = "Personal" if event.get("calendar") == "personal" else "Work"
                        # Parse ISO format datetime strings
                        start_dt = datetime.fromisoformat(event.get("start", ""))
                        end_dt = datetime.fromisoformat(event.get("end", ""))
                        start_time = start_dt.strftime("%H:%M")
                        end_time = end_dt.strftime("%H:%M")
                        ctx.add_line(f"• *{start_time}-{end_time}* ({cal_label}): {event['title']}")
                        meeting_count += 1

                if meeting_count > 5:
                    ctx.add_warning(f"Heavy meeting day ({meeting_count}). Block time for breaks.")
            else:
                ctx.add_line("_No events - open day!_")
                ctx.add_insight("Clear calendar - good for deep work.")
        else:
            ctx.add_line("_Calendar unavailable_")

    except Exception as e:
        logger.debug(f"Calendar unavailable: {e}")
        ctx.add_line("_Calendar unavailable_")


def _build_weather_section(ctx: ReportContext):
    """Build weather section for morning report."""
    ctx.add_section("*WEATHER*")

    try:
        from src.tools.weather import get_current_weather

        weather = get_current_weather()
        if isinstance(weather, dict) and not weather.get("error"):
            temp = weather.get("temp")
            feels = weather.get("feels_like")
            condition = weather.get("condition", "").lower()
            humidity = weather.get("humidity")

            ctx.add_line(f"• *Temperature:* {temp}°C (feels {feels}°C)")
            ctx.add_line(f"• *Condition:* {condition.title()}")
            ctx.add_line(f"• *Humidity:* {humidity}%")

            # Check for rain in condition
            if "rain" in condition or "drizzle" in condition or "shower" in condition:
                ctx.add_warning("Rain expected today - bring an umbrella.")
        else:
            ctx.add_line("_Weather data unavailable_")

    except Exception as e:
        logger.debug(f"Weather unavailable: {e}")
        ctx.add_line("_Weather unavailable_")


def _build_insights_section(ctx: ReportContext):
    """Build insights section at the end of report."""
    if not ctx.warnings and not ctx.insights:
        return

    ctx.add_section("*NOTES FOR TODAY*")
    for w in ctx.warnings:
        ctx.add_line(f"• _Warning:_ {w}")
    for i in ctx.insights:
        ctx.add_line(f"• {i}")


# =============================================================================
# Evening Report Sections
# =============================================================================

@dataclass
class SleepFactors:
    """Factors that influence sleep quality prediction."""
    stress: int = 0
    steps: int = 0
    active_minutes: int = 0
    meetings: int = 0
    body_battery: int = 50
    high_stress_min: int = 0
    current_stress: int = 0


def _build_activity_section(ctx: ReportContext, factors: SleepFactors):
    """Build activity section for evening report."""
    ctx.add_section("*ACTIVITY*")

    today_start = ctx.now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Steps and distance
    steps_data = _query(f"""
        SELECT totalSteps, totalDistanceMeters
        FROM DailyStats
        WHERE time >= '{today_start.strftime('%Y-%m-%dT%H:%M:%SZ')}'
        ORDER BY time DESC LIMIT 1
    """)

    if steps_data:
        steps = int(steps_data[0].get("totalSteps", 0) or 0)
        distance = (steps_data[0].get("totalDistanceMeters", 0) or 0) / 1000
        factors.steps = steps

        if steps >= 10000:
            steps_note = "Excellent"
        elif steps >= 7000:
            steps_note = "Good"
        elif steps >= 5000:
            steps_note = "Moderate"
        else:
            steps_note = "Low"

        ctx.add_line(f"• *Steps:* {steps:,} _{steps_note}_ | *Distance:* {distance:.1f}km")

    # Activities
    activities = _query(f"""
        SELECT activityName, movingDuration, calories
        FROM ActivitySummary
        WHERE time >= '{today_start.strftime('%Y-%m-%dT%H:%M:%SZ')}'
    """)

    if activities:
        total_active = sum(a.get("movingDuration", 0) or 0 for a in activities)
        factors.active_minutes = int(total_active / 60)

        for a in activities:
            name = a.get("activityName", "Activity")
            dur = format_duration(a.get("movingDuration", 0) or 0)
            cal = int(a.get("calories", 0) or 0)
            if dur != "0m":
                ctx.add_line(f"• *{name}:* {dur}, {cal} cal")


def _build_stress_section(ctx: ReportContext, factors: SleepFactors):
    """Build stress section for evening report."""
    ctx.add_section("*STRESS*")

    today_start = ctx.now.replace(hour=0, minute=0, second=0, microsecond=0)

    stress_data = _query(f"""
        SELECT stressAvg, highStressDuration, restStressDuration
        FROM DailyStats
        WHERE time >= '{today_start.strftime('%Y-%m-%dT%H:%M:%SZ')}'
        ORDER BY time DESC LIMIT 1
    """)

    if stress_data:
        stress_avg = int(stress_data[0].get("stressAvg", 0) or 0)
        high_sec = stress_data[0].get("highStressDuration", 0) or 0
        rest_sec = stress_data[0].get("restStressDuration", 0) or 0

        factors.stress = stress_avg
        factors.high_stress_min = int(high_sec / 60)

        if stress_avg < 30:
            stress_note = "Relaxed"
        elif stress_avg < 50:
            stress_note = "Moderate"
        else:
            stress_note = "High"

        ctx.add_line(f"• *Average:* {stress_avg}/100 _{stress_note}_")
        ctx.add_line(f"• *High stress:* {format_duration(high_sec)} | *Rest:* {format_duration(rest_sec)}")

    # Current stress
    current = _query("SELECT stressLevel FROM StressIntraday ORDER BY time DESC LIMIT 1")
    if current:
        curr_stress = int(current[0].get("stressLevel", 0) or 0)
        factors.current_stress = curr_stress
        ctx.add_line(f"• *Current:* {curr_stress}/100")


def _build_evening_energy_section(ctx: ReportContext, factors: SleepFactors):
    """Build energy section for evening report."""
    ctx.add_section("*ENERGY*")

    today_start = ctx.now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Current body battery
    bb_current = _query('SELECT "BodyBatteryLevel" FROM "BodyBatteryIntraday" ORDER BY time DESC LIMIT 1')

    # Wake body battery
    bb_wake = _query(f"""
        SELECT bodyBatteryAtWakeTime
        FROM DailyStats
        WHERE time >= '{today_start.strftime('%Y-%m-%dT%H:%M:%SZ')}'
        ORDER BY time DESC LIMIT 1
    """)

    if bb_current:
        current_bb = int(bb_current[0].get("BodyBatteryLevel", 0) or 0)
        factors.body_battery = current_bb

        if bb_wake:
            wake_bb = int(bb_wake[0].get("bodyBatteryAtWakeTime", 0) or 0)
            drain = wake_bb - current_bb
            ctx.add_line(f"• *Body Battery:* {current_bb}/100 (started at {wake_bb}, used {drain})")
        else:
            ctx.add_line(f"• *Body Battery:* {current_bb}/100")


def _build_evening_meetings_section(ctx: ReportContext, factors: SleepFactors):
    """Build meetings section for evening report."""
    ctx.add_section("*MEETINGS*")
    
    try:
        from src.tools.calendar import get_today_schedule
        
        schedule = get_today_schedule()
        
        if isinstance(schedule, dict) and not schedule.get("error"):
            # Combine all event types
            current_events = schedule.get("current_events", [])
            upcoming_events = schedule.get("upcoming_events", [])
            completed_events = schedule.get("completed_events", [])
            all_events = current_events + upcoming_events + completed_events
            
            meetings = [e for e in all_events if not e.get("all_day")]
            meeting_count = len(meetings)
            factors.meetings = meeting_count
            
            # Calculate total duration
            total_min = 0
            for e in meetings:
                # Calculate duration from start/end times
                start_dt = datetime.fromisoformat(e.get("start", ""))
                end_dt = datetime.fromisoformat(e.get("end", ""))
                duration_min = (end_dt - start_dt).total_seconds() / 60
                total_min += duration_min
            
            ctx.add_line(f"• *Total:* {meeting_count} meetings, {format_duration(int(total_min * 60))} duration")
        else:
            ctx.add_line("_Calendar unavailable_")

    except Exception as e:
        logger.debug(f"Calendar unavailable: {e}")
        ctx.add_line("_Calendar unavailable_")


def _build_sleep_recommendation(ctx: ReportContext, factors: SleepFactors):
    """Build sleep recommendation section for evening report."""
    ctx.add_section("*SLEEP RECOMMENDATION*")

    tips = []
    bedtime_adj = 0

    if factors.stress > 50:
        tips.append("High stress - wind down early with relaxation")
        bedtime_adj -= 30

    if factors.meetings > 5:
        tips.append("Many meetings - give your brain screen-free time before bed")
        bedtime_adj -= 15

    if factors.steps < 5000 and factors.active_minutes < 30:
        tips.append("Low activity - a short walk could help sleep quality")

    if factors.active_minutes > 60:
        tips.append("Good workout - your body needs quality recovery sleep")
        bedtime_adj -= 15

    if factors.body_battery < 30:
        tips.append("Low energy - prioritize early bedtime")
        bedtime_adj -= 30

    if factors.high_stress_min > 120:
        tips.append("Extended stress - avoid screens 1h before bed")

    if not tips:
        tips.append("Normal day - stick to your regular schedule")

    # Calculate suggested bedtime
    normal_bedtime = ctx.now.replace(hour=22, minute=30, second=0, microsecond=0)
    suggested = normal_bedtime + timedelta(minutes=bedtime_adj)
    if suggested < ctx.now:
        suggested = ctx.now + timedelta(minutes=30)

    ctx.add_line(f"• *Suggested bedtime:* {suggested.strftime('%H:%M')}")

    for tip in tips:
        ctx.add_line(f"• {tip}")

    # Sleep outlook
    good_factors = []
    if factors.stress < 40:
        good_factors.append("low stress")
    if factors.body_battery > 30:
        good_factors.append("energy reserves")
    if factors.active_minutes >= 30:
        good_factors.append("physical activity")

    if len(good_factors) >= 2:
        ctx.add_line(f"• *Outlook:* Good ({', '.join(good_factors)})")
    else:
        ctx.add_line("• *Outlook:* May need extra wind-down time")


# =============================================================================
# Main Report Functions
# =============================================================================

@agent.tool_plain
def report_morning_briefing() -> str:
    """Get morning briefing with sleep, energy, calendar, and weather.
    
    COMPOSITE REPORT: Returns formatted string for display.
    
    Returns:
        Formatted morning report string
    """
    now = datetime.now(settings.TIMEZONE)
    ctx = ReportContext(
        now=now,
        today_str=now.strftime("%Y-%m-%d"),
        lines=[
            f"Good morning, Artur! It's {now.strftime('%A, %B %d')}.",
            ""
        ]
    )
    
    # Check Garmin sync and build sections
    garmin_fresh = _add_sync_warning(ctx, None, None)
    _build_sleep_section(ctx, garmin_fresh)
    _build_energy_section(ctx, garmin_fresh)
    _build_calendar_section(ctx)
    _build_weather_section(ctx)
    _build_insights_section(ctx)
    
    return "\n".join(ctx.lines)


@agent.tool_plain
def report_evening_briefing() -> str:
    """Get evening report with activity summary and sleep recommendations.
    
    COMPOSITE REPORT: Returns formatted string for display.
    
    Returns:
        Formatted evening report string
    """
    now = datetime.now(settings.TIMEZONE)
    ctx = ReportContext(
        now=now,
        today_str=now.strftime("%Y-%m-%d"),
        lines=[
            f"Good evening, Artur! Here's your day summary.",
            ""
        ]
    )
    factors = SleepFactors()
    
    # Check Garmin sync
    garmin_fresh, hours_ago, last_sync_time = _check_garmin_sync_freshness()
    if not garmin_fresh:
        if hours_ago is not None:
            ctx.add_line(f"*WARNING:* Garmin data stale (last sync: {hours_ago:.1f}h ago at {last_sync_time})")
            ctx.add_line("_Activity metrics below may be incomplete. Sync your watch!_")
            ctx.add_line("")
        else:
            ctx.add_line("*WARNING:* Garmin sync unavailable")
            ctx.add_line("")
    
    # Build sections
    _build_activity_section(ctx, factors)
    _build_stress_section(ctx, factors)
    _build_evening_energy_section(ctx, factors)
    _build_evening_meetings_section(ctx, factors)
    _build_sleep_recommendation(ctx, factors)
    
    return "\n".join(ctx.lines)
