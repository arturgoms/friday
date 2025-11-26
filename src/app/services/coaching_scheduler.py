"""
Scheduled Coaching Reports
Sends daily and weekly health insights via Telegram
"""
import sys
sys.path.insert(0, '/home/artur/friday/src')

from datetime import datetime, time as dtime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.core.logging import logger


class CoachingScheduler:
    """Scheduler for automated coaching reports."""
    
    def __init__(self):
        """Initialize scheduler."""
        self.scheduler = BackgroundScheduler()
        self._health_coach = None
        self._notifier = None
    
    @property
    def health_coach(self):
        """Lazy load health coach."""
        if self._health_coach is None:
            from app.services.health_coach import get_health_coach
            self._health_coach = get_health_coach()
        return self._health_coach
    
    @property
    def notifier(self):
        """Lazy load notifier."""
        if self._notifier is None:
            sys.path.insert(0, '/home/artur/friday/src')
            from notify import FridayNotifier
            self._notifier = FridayNotifier()
        return self._notifier
    
    def send_daily_report(self):
        """Send comprehensive morning report."""
        try:
            logger.info("Generating morning report...")
            
            from app.services.morning_report import generate_morning_report
            from app.services.unified_calendar_service import UnifiedCalendarService
            from app.services.llm import LLMService
            
            # Initialize services
            calendar_service = UnifiedCalendarService()
            llm_service = LLMService()
            
            # Generate the comprehensive morning report
            message = generate_morning_report(
                health_coach=self.health_coach,
                calendar_service=calendar_service,
                llm_service=llm_service
            )
            
            # Send via Telegram
            self.notifier.send_message(message, parse_mode="Markdown")
            logger.info("Daily coaching report sent!")
            
        except Exception as e:
            logger.error(f"Error sending daily report: {e}")
    
    def send_evening_report(self):
        """Send comprehensive evening report."""
        try:
            logger.info("Generating evening report...")
            
            from app.services.evening_report import generate_evening_report
            from app.services.unified_calendar_service import UnifiedCalendarService
            from app.services.llm import LLMService
            
            # Initialize services
            calendar_service = UnifiedCalendarService()
            llm_service = LLMService()
            
            # Generate the comprehensive evening report
            message = generate_evening_report(
                health_coach=self.health_coach,
                calendar_service=calendar_service,
                llm_service=llm_service
            )
            
            # Send via Telegram
            self.notifier.send_message(message, parse_mode="Markdown")
            logger.info("Evening report sent!")
            
        except Exception as e:
            logger.error(f"Error sending evening report: {e}")
    
    def send_weekly_report(self):
        """Send weekly coaching report."""
        try:
            logger.info("Generating weekly coaching report...")
            
            # Get health data
            summary = self.health_coach.get_running_summary(days=30)
            
            # Build report
            report_lines = []
            report_lines.append("📅 *WEEKLY COACHING REPORT*")
            report_lines.append("")
            report_lines.append(f"_{datetime.now().strftime('%B %d, %Y')}_")
            report_lines.append("")
            
            if "run_count" in summary:
                report_lines.append("🏃 *Last 30 Days Summary:*")
                report_lines.append(f"• Total Runs: {summary['run_count']}")
                report_lines.append(f"• Total Distance: {summary['total_distance_km']} km")
                report_lines.append(f"• Total Time: {summary['total_time_hours']} hours")
                report_lines.append(f"• Average Pace: {summary['avg_pace_min_km']} min/km")
                report_lines.append(f"• Average HR: {summary['avg_heart_rate']} bpm")
                report_lines.append(f"• Calories Burned: {summary['total_calories']}")
                report_lines.append("")
                
                # Analysis
                weekly_km = summary['total_distance_km'] * 7 / 30
                report_lines.append("📈 *Analysis:*")
                report_lines.append(f"• Weekly avg: ~{weekly_km:.1f} km/week")
                
                if summary['run_count'] < 8:  # Less than 2 per week
                    report_lines.append("• 💡 Consider increasing frequency")
                elif summary['run_count'] > 20:  # More than 5 per week
                    report_lines.append("• ⚠️ High volume - ensure adequate recovery")
                else:
                    report_lines.append("• ✅ Good training consistency!")
                
                if summary['avg_pace_min_km'] < 5:
                    report_lines.append("• 🔥 Strong pace! Keep it up!")
                elif summary['avg_pace_min_km'] > 7:
                    report_lines.append("• 💪 Focus on form and gradual speed work")
                
                report_lines.append("")
                report_lines.append("🎯 *Next Week Goals:*")
                target_km = round(weekly_km * 1.05, 1)  # 5% increase
                report_lines.append(f"• Target: {target_km} km")
                report_lines.append("• Include 1 tempo run")
                report_lines.append("• Prioritize recovery between hard efforts")
            else:
                report_lines.append("No running data available for analysis.")
            
            report_lines.append("")
            report_lines.append("_Keep up the great work! 🏆_")
            
            # Send via Telegram
            message = "\n".join(report_lines)
            self.notifier.send_message(message, parse_mode="Markdown")
            logger.info("Weekly coaching report sent!")
            
        except Exception as e:
            logger.error(f"Error sending weekly report: {e}")
    
    def start(self):
        """Start the scheduler."""
        # Morning report at 9:00 AM
        self.scheduler.add_job(
            self.send_daily_report,
            CronTrigger(hour=9, minute=0),
            id='daily_morning_report',
            name='Daily Morning Report',
            replace_existing=True
        )
        
        # Evening report at 11:00 PM
        self.scheduler.add_job(
            self.send_evening_report,
            CronTrigger(hour=23, minute=0),
            id='daily_evening_report',
            name='Daily Evening Report',
            replace_existing=True
        )
        
        # Weekly report on Monday at 8:00 AM
        self.scheduler.add_job(
            self.send_weekly_report,
            CronTrigger(day_of_week='mon', hour=8, minute=0),
            id='weekly_coaching_report',
            name='Weekly Coaching Report',
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info("✅ Coaching scheduler started (Morning: 9AM, Evening: 11PM, Weekly: Mon 8AM)")
    
    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
        logger.info("Coaching scheduler stopped")


# Singleton instance
coaching_scheduler = CoachingScheduler()
