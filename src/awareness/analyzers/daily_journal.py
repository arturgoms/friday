"""
Friday Insights Engine - Daily Journal Analyzer

Processes collected journal data and generates structured daily notes.
Runs at 23:59 to process the full day.
"""

import logging
from datetime import datetime, date as date_type
from typing import Dict, Any, List

from settings import settings
def get_brt():
    return settings.TIMEZONE
from src.awareness.analyzers.base import ScheduledAnalyzer
from src.awareness.models import Insight, Priority, Category, InsightType
# TODO: Refactor JournalCollector to use tools instead of collectors
# from src.awareness.collectors.journal import JournalCollector
from src.tools.vault import vault_write_note
from pathlib import Path

logger = logging.getLogger(__name__)


class DailyJournalAnalyzer(ScheduledAnalyzer):
    """
    TODO: Needs refactoring to use tools instead of JournalCollector
    
    Processes journal entries and creates daily notes in Obsidian.
    
    Runs once per day at 23:59 to collect and process:
    - Journal entries (text and voice)
    - Calendar events
    - Weather data
    - Health metrics with anomalies
    
    Generates a structured markdown note using LLM for organization.
    """
    
    def __init__(self, config, store):
        super().__init__("daily_journal", config, store)
        # TODO: Replace JournalCollector with direct tool calls
        # self.journal_collector = JournalCollector(store)
        logger.warning("DailyJournalAnalyzer needs refactoring - JournalCollector is disabled")
    
    def analyze(self, data: Dict[str, Any]) -> List[Insight]:
        """Process daily journal data and create the daily note.
        
        Args:
            data: Dict that may contain 'target_date' key for specific date processing
            
        Returns:
            List with single insight confirming note creation
        """
        # Get target date (from data or default to today)
        if "target_date" in data and isinstance(data["target_date"], date_type):
            today = data["target_date"]
        else:
            today = datetime.now(get_brt()).date()
        
        # Collect all journal data
        logger.info(f"[DAILY_JOURNAL] Processing journal for {today}")
        journal_data = self.journal_collector.collect(target_date=today)
        
        if not journal_data:
            logger.warning(f"[DAILY_JOURNAL] No data collected for {today}")
            return []
        
        # Generate the daily note using LLM
        try:
            note_content = self._generate_note_with_llm(journal_data)
            
            # Write the note to Obsidian
            success = self._write_daily_note(today, journal_data, note_content)
            
            if success:
                # Create insight for notification
                entry_count = journal_data.get("entry_count", 0)
                event_count = journal_data.get("event_count", 0)
                health = journal_data.get("health")
                
                # Get health flag
                health_flag = ""
                if health and health.get("anomalies"):
                    health_flag = health["anomalies"][0]  # First anomaly
                
                # Generate summary
                summary = self._generate_summary(journal_data)
                
                # Format notification
                date_str = today.strftime("%Y-%m-%d")
                message = (
                    f"Daily note created: {date_str}.md\n\n"
                    f"{event_count} events | {entry_count} entries"
                )
                
                if health_flag:
                    message += f" | {health_flag}"
                
                if summary:
                    message += f"\n\nSummary: {summary}"
                
                insight = Insight(
                    type=InsightType.INFO,
                    category=Category.JOURNAL,
                    priority=Priority.LOW,
                    title="Daily Journal Created",
                    message=message,
                    data={"date": date_str, "path": f"2. Time/2.2 Daily/{date_str}.md"}
                )
                
                logger.info(f"[DAILY_JOURNAL] Successfully created daily note for {today}")
                return [insight]
            else:
                logger.error(f"[DAILY_JOURNAL] Failed to write daily note for {today}")
                return []
                
        except Exception as e:
            logger.error(f"[DAILY_JOURNAL] Error generating daily note: {e}", exc_info=True)
            return []
    
    def _generate_note_with_llm(self, journal_data: Dict[str, Any]) -> str:
        """Use LLM to structure the journal data into sections.
        
        Args:
            journal_data: Collected journal snapshot
            
        Returns:
            Structured markdown content (without frontmatter)
        """
        import httpx
        from src.core.api_client import get_api_url, get_api_headers
        
        # Build prompt with all the data
        prompt = self._build_llm_prompt(journal_data)
        
        try:
            with httpx.Client(timeout=180.0) as client:
                # Use a unique session ID with timestamp to avoid history accumulation
                import time
                session_id = f"daily_journal_{int(time.time())}"
                
                response = client.post(
                    f"{get_api_url()}/chat",
                    headers=get_api_headers(),
                    json={
                        "text": prompt,
                        "user_id": "daily_journal_analyzer",
                        "session_id": session_id,
                        "fresh": True  # Clear any existing history
                    }
                )
                response.raise_for_status()
                data = response.json()
            
            # Extract the structured content from response
            content = data.get("text", "")
            
            # Clean up any markdown code blocks if LLM wrapped it
            if content.startswith("```markdown"):
                content = content.replace("```markdown", "", 1)
            if content.endswith("```"):
                content = content[:-3]
            
            return content.strip()
            
        except Exception as e:
            logger.error(f"[DAILY_JOURNAL] LLM processing failed: {e}")
            # Fallback to simple formatting
            return self._fallback_format(journal_data)
    
    def _build_llm_prompt(self, journal_data: Dict[str, Any]) -> str:
        """Build the prompt for LLM to structure the journal.
        
        Args:
            journal_data: Collected journal snapshot
            
        Returns:
            Formatted prompt string
        """
        entries = journal_data.get("entries", [])
        events = journal_data.get("calendar_events", [])
        weather = journal_data.get("weather")
        health = journal_data.get("health")
        habits = self.config.get("journal", {}).get("habits", [])
        
        # Format entries - keep it concise
        entries_text = ""
        if entries:
            entries_text = "\n".join([
                f"{e['content']}"
                for e in entries
            ])
        else:
            entries_text = "None"
        
        # Format calendar events
        events_text = ""
        if events:
            events_text = "\n".join([
                f"{e['start'].strftime('%H:%M')} - {e['title']}"
                for e in events
            ])
        else:
            events_text = "None"
        
        # Format weather - concise
        weather_text = f"{weather.get('conditions')}, {weather.get('temp_high')}°C" if weather else "N/A"
        
        # Format health - concise
        health_text = ""
        if health:
            parts = []
            if health.get('sleep_hours'):
                parts.append(f"Sleep:{health['sleep_hours']:.1f}h")
            if health.get('body_battery_start') and health.get('body_battery_end'):
                parts.append(f"BB:{health['body_battery_start']}→{health['body_battery_end']}")
            if health.get('avg_stress'):
                parts.append(f"Stress:{health['avg_stress']}")
            if health.get('steps'):
                parts.append(f"Steps:{health['steps']}")
            if health.get('anomalies'):
                parts.append(f"Note:{health['anomalies'][0]}")
            health_text = ", ".join(parts)
        else:
            health_text = "N/A"
        
        # Build the prompt - super explicit
        habits_str = ', '.join(habits)
        prompt = (
            f"Organize journal entries. TRANSLATE ALL Portuguese to English.\n\n"
            f"Entries:\n{entries_text}\n\n"
            f"Events: {events_text}\nWeather: {weather_text}\nHealth: {health_text}\n\n"
            f"Output format:\n\n"
            f"## Weather\n{weather_text}\n\n"
            f"## Health\n- **Sleep:** [X]\n- **Body Battery:** [X%→X%]\n- **Stress:** [X%]\n- **Steps:** [X]\n> [anomaly]\n\n"
            f"## Calendar\n{events_text if events_text != 'None' else '(None)'}\n\n"
            f"## Habits\n"
            f"- [ ] Read\n- [ ] Exercise\n- [ ] Quality time with wife\n- [ ] Quality time with pets\n- [ ] Play games\n- [ ] Meditation\n"
            f"(Check [x] if detected in entries)\n\n"
            f"## Journal\n\n### Events\n- [past actions]\n\n### Thoughts\n- [feelings]\n\n### Ideas\n- [creative/future]\n\n### Concerns\n- [worries]\n\n### Reminders\n- [ ] Task one\n- [ ] Task two\n\n"
            f"CRITICAL:\n"
            f"1. TRANSLATE Portuguese→English\n"
            f"2. Reminders format: SPACE before bracket: '- [ ] task'\n"
            f"3. Habits: '- [x]' if detected, '- [ ]' if not\n"
            f"4. No duplicates"
        )
        
        # Log the prompt for debugging
        prompt_tokens = len(prompt) // 4  # Rough estimate
        logger.info(f"[DAILY_JOURNAL] Prompt length: {len(prompt)} chars (~{prompt_tokens} tokens)")
        logger.debug(f"[DAILY_JOURNAL] Full prompt:\n{prompt}")
        
        return prompt
    
    def _fallback_format(self, journal_data: Dict[str, Any]) -> str:
        """Simple formatting fallback if LLM fails.
        
        Args:
            journal_data: Collected journal snapshot
            
        Returns:
            Basic markdown formatting
        """
        entries = journal_data.get("entries", [])
        events = journal_data.get("calendar_events", [])
        weather = journal_data.get("weather")
        health = journal_data.get("health")
        
        lines = []
        
        # Weather
        lines.append("## Weather")
        if weather:
            lines.append(f"{weather.get('conditions', 'Unknown')}, {weather.get('temp_high', '?')}°C")
        else:
            lines.append("(No weather data)")
        lines.append("")
        
        # Health
        lines.append("## Health")
        if health:
            if health.get('sleep_hours'):
                lines.append(f"- Sleep: {health['sleep_hours']:.1f}h")
            if health.get('steps'):
                lines.append(f"- Steps: {health['steps']}")
            if health.get('anomalies'):
                lines.append(f"- Note: {'; '.join(health['anomalies'])}")
        else:
            lines.append("(No health data)")
        lines.append("")
        
        # Calendar
        lines.append("## Calendar")
        if events:
            for event in events:
                start_time = event['start'].strftime("%H:%M")
                lines.append(f"- {start_time} - {event['title']}")
        else:
            lines.append("(No events)")
        lines.append("")
        
        # Habits
        lines.append("## Habits")
        habits = self.config.get("journal", {}).get("habits", [])
        for habit in habits:
            lines.append(f"- [ ] {habit}")
        lines.append("")
        
        # Journal
        lines.append("## Journal")
        lines.append("")
        if entries:
            for entry in entries:
                timestamp = entry['timestamp'].strftime("%H:%M")
                lines.append(f"**{timestamp}** - {entry['content']}")
                lines.append("")
        else:
            lines.append("(No journal entries)")
        
        return "\n".join(lines)
    
    def _write_daily_note(
        self, 
        date: date_type, 
        journal_data: Dict[str, Any],
        content: str
    ) -> bool:
        """Write the daily note to Obsidian vault.
        
        Args:
            date: Date for the note
            journal_data: Raw journal data
            content: Structured content from LLM
            
        Returns:
            True if successful
        """
        try:
            from datetime import timedelta
            import os
            
            # Get vault path
            vault_path = settings.VAULT_PATH
            
            # Prepare frontmatter
            weather = journal_data.get("weather")
            health = journal_data.get("health")
            
            weather_str = ""
            if weather:
                weather_str = f"{weather.get('conditions', '?')}, {weather.get('temp_high', '?')}°C"
            
            sleep_str = ""
            if health and health.get('sleep_hours'):
                sleep_str = f"{health['sleep_hours']:.1f}h"
            
            # Detect checked habits from content
            habits = self.config.get("journal", {}).get("habits", [])
            checked_habits = []
            for habit in habits:
                if f"- [x] {habit}" in content:
                    checked_habits.append(habit)
            
            frontmatter = {
                "tags": ["time/daily", "area/friday"],
                "date": date.isoformat(),
                "day": date.strftime("%A"),
            }
            
            if weather_str:
                frontmatter["weather"] = weather_str
            if sleep_str:
                frontmatter["sleep"] = sleep_str
            if checked_habits:
                frontmatter["habits"] = checked_habits
            
            # Build navigation links
            yesterday = date - timedelta(days=1)
            tomorrow = date + timedelta(days=1)
            nav_links = f"<< [[{yesterday.isoformat()}|Yesterday]] | [[{tomorrow.isoformat()}|Tomorrow]] >>"
            
            # Build title as self-referencing link
            title = f"# [[{date.isoformat()}]]"
            
            # Add raw entries at the end
            raw_entries_section = self._build_raw_entries_section(journal_data)
            
            # Combine everything
            full_content = f"{nav_links}\n{title}\n\n{content}\n\n{raw_entries_section}"
            
            # Write using vault tool
            path = f"2. Time/2.2 Daily/{date.isoformat()}.md"
            result = vault_write_note(
                path=path,
                content=full_content,
                frontmatter=frontmatter,
                mode="overwrite"
            )
            
            if "Successfully wrote" in result:
                return True
            else:
                logger.error(f"[DAILY_JOURNAL] Vault write failed: {result}")
                return False
                
        except Exception as e:
            logger.error(f"[DAILY_JOURNAL] Error writing note: {e}", exc_info=True)
            return False
    
    def _build_raw_entries_section(self, journal_data: Dict[str, Any]) -> str:
        """Build the collapsible raw entries section.
        
        Args:
            journal_data: Collected journal snapshot
            
        Returns:
            Markdown for raw entries section
        """
        entries = journal_data.get("entries", [])
        
        if not entries:
            return ""
        
        entry_count = len(entries)
        
        lines = [
            "---",
            "",
            "<details>",
            f"<summary>Raw entries ({entry_count})</summary>",
            ""
        ]
        
        for entry in entries:
            timestamp = entry['timestamp'].strftime("%H:%M")
            entry_type = entry['entry_type']
            content = entry['content']
            
            # Add emoji for voice entries
            if entry_type == 'voice':
                lines.append(f"**{timestamp}** - 🎤 \"{content}\"")
            else:
                lines.append(f"**{timestamp}** - {content}")
            
            lines.append("")
        
        lines.append("</details>")
        
        return "\n".join(lines)
    
    def _generate_summary(self, journal_data: Dict[str, Any]) -> str:
        """Generate a one-line summary of the day.
        
        Args:
            journal_data: Collected journal snapshot
            
        Returns:
            One-line summary
        """
        entries = journal_data.get("entries", [])
        
        if not entries:
            return "Quiet day with no journal entries."
        
        # Get first entry as indicator of the day
        first_entry = entries[0]['content']
        
        # Truncate to reasonable length
        if len(first_entry) > 80:
            summary = first_entry[:77] + "..."
        else:
            summary = first_entry
        
        return summary
