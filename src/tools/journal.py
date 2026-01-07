"""
Friday Journal Tools

Tools for managing daily journal threads and entries.
"""

import sys
from pathlib import Path

# Add parent directory to path to import agent
_parent_dir = Path(__file__).parent.parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

import logging
from datetime import datetime
from typing import Dict, Any, Optional

from settings import settings
from src.core.agent import agent
from src.core.database import Database

logger = logging.getLogger(__name__)


def get_brt():
    """Get BRT timezone from settings."""
    return settings.TIMEZONE


# =============================================================================
# Journal Thread Management
# =============================================================================


@agent.tool_plain
def create_daily_journal_thread() -> str:
    """Create the daily journal thread in Telegram.
    
    This should be called once per day (typically at 8:00 AM) to create
    the journal thread for the day. Users can reply to this thread with
    their journal entries throughout the day.
    
    Returns:
        Message to send to Telegram
    """
    try:
        today = datetime.now(get_brt()).strftime("%Y-%m-%d")
        weekday = datetime.now(get_brt()).strftime("%A")
        
        message = f"""📔 Daily Journal Thread - {weekday}, {today}

Good morning! This is your journal thread for today.

Reply to this message with:
• 💭 Text entries - your thoughts, reflections, notes
• 🎤 Voice messages - I'll transcribe them automatically

At the end of the day, I'll compile everything into your daily note.

Let's make today count! 🌟"""
        
        return message
        
    except Exception as e:
        logger.error(f"Error creating journal thread: {e}")
        return f"Error creating journal thread: {e}"


def save_journal_thread(date: str, message_id: int) -> bool:
    """Save journal thread message ID to database.
    
    Args:
        date: Date in YYYY-MM-DD format
        message_id: Telegram message ID
        
    Returns:
        True if saved successfully
    """
    try:
        db = Database()
        created_at = datetime.now(get_brt()).isoformat()
        
        # Use INSERT OR REPLACE to handle duplicates
        db.execute(
            'INSERT OR REPLACE INTO journal_threads (date, message_id, created_at) VALUES (:date, :message_id, :created_at)',
            {
                'date': date,
                'message_id': message_id,
                'created_at': created_at
            }
        )
        
        logger.info(f"Saved journal thread for {date}, message_id={message_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving journal thread: {e}")
        return False


def get_journal_thread_for_date(date: str) -> Optional[int]:
    """Get the journal thread message ID for a specific date.
    
    Args:
        date: Date in YYYY-MM-DD format
        
    Returns:
        Message ID if found, None otherwise
    """
    try:
        db = Database()
        result = db.fetchone(
            "SELECT message_id FROM journal_threads WHERE date = :date",
            {'date': date}
        )
        
        if result:
            return result[0]
        return None
        
    except Exception as e:
        logger.error(f"Error getting journal thread: {e}")
        return None


# =============================================================================
# Journal Entry Management
# =============================================================================


def save_journal_entry(
    content: str,
    entry_type: str = "text",
    thread_message_id: Optional[int] = None
) -> bool:
    """Save a journal entry to the database.
    
    Args:
        content: The text content (or transcribed audio)
        entry_type: Either "text" or "audio"
        thread_message_id: The thread message ID this is replying to
        
    Returns:
        True if saved successfully
    """
    try:
        db = Database()
        now = datetime.now(get_brt())
        
        db.insert('journal_entries', {
            'date': now.strftime("%Y-%m-%d"),
            'timestamp': now.isoformat(),
            'entry_type': entry_type,
            'content': content,
            'thread_message_id': thread_message_id
        })
        
        logger.info(f"Saved journal entry ({entry_type}): {content[:50]}...")
        return True
        
    except Exception as e:
        logger.error(f"Error saving journal entry: {e}")
        return False


def get_journal_entries_for_date(date: str) -> list:
    """Get all journal entries for a specific date.
    
    Args:
        date: Date in YYYY-MM-DD format
        
    Returns:
        List of journal entries
    """
    try:
        db = Database()
        results = db.fetchall(
            """SELECT id, timestamp, entry_type, content, thread_message_id 
               FROM journal_entries 
               WHERE date = :date 
               ORDER BY timestamp ASC""",
            {'date': date}
        )
        
        entries = []
        for row in results:
            entries.append({
                'id': row[0],
                'timestamp': row[1],
                'entry_type': row[2],
                'content': row[3],
                'thread_message_id': row[4]
            })
        
        return entries
        
    except Exception as e:
        logger.error(f"Error getting journal entries: {e}")
        return []


@agent.tool_plain
def get_todays_journal_entries() -> Dict[str, Any]:
    """Get all journal entries for today.
    
    Atomic data tool that returns today's journal entries.
    
    Returns:
        Dict with today's journal entries
    """
    try:
        today = datetime.now(get_brt()).strftime("%Y-%m-%d")
        entries = get_journal_entries_for_date(today)
        
        # Count by type
        text_count = len([e for e in entries if e['entry_type'] == 'text'])
        audio_count = len([e for e in entries if e['entry_type'] == 'audio'])
        
        return {
            'date': today,
            'total_entries': len(entries),
            'text_entries': text_count,
            'audio_entries': audio_count,
            'entries': entries
        }
        
    except Exception as e:
        logger.error(f"Error getting today's journal entries: {e}")
        return {'error': str(e)}

# =============================================================================
# Phase 2: Daily Note Generation (Simplified)
# =============================================================================


def _categorize_entries_with_ai(entries: list) -> dict:
    """Simple AI categorization of entries into Events/Thoughts/Reminders.
    
    Args:
        entries: List of raw journal entries
        
    Returns:
        Dict with events, thoughts, reminders, habits lists
    """
    # Format entries for AI
    formatted_entries = []
    for entry in entries:
        time = datetime.fromisoformat(entry['timestamp']).strftime("%H:%M")
        prefix = "🎤 " if entry['entry_type'] == 'audio' else ""
        formatted_entries.append(f"**{time}** - {prefix}{entry['content']}")
    
    entries_text = "\n\n".join(formatted_entries)
    
    # Enhanced prompt - understand, improve, and categorize
    prompt = f"""You are analyzing my personal journal entries (some in Portuguese). Read them carefully, understand what I'm expressing, and make them better while keeping my voice and intent.

ENTRIES:
{entries_text}

TASK:
1. Translate Portuguese to English naturally
2. Understand the context and meaning behind each entry
3. Enhance and clarify what I'm saying - make it more articulate and well-written
4. Organize into categories:
   - Events: Things that happened (actions, meetings, activities)
   - Thoughts: Reflections, feelings, concerns, ideas, opinions
   - Reminders: TODOs, action items, things to remember
5. Detect habits that were mentioned/done:
   - Read, Exercise, Quality time with wife, Quality time with pets, Play games, Meditation

Return as JSON:
{{
  "events": ["enhanced event description 1", "enhanced event 2", ...],
  "thoughts": ["enhanced thought 1", "enhanced thought 2", ...],
  "reminders": ["clear reminder 1", ...],
  "habits": ["Play games", ...]
}}

GUIDELINES:
- Keep my voice and personality - don't make it formal or corporate
- Fix grammar and clarity but maintain authenticity
- Expand on brief/unclear entries to capture full meaning
- Connect related thoughts if they flow together
- Be concise but complete
- If I mention concerns or excitement, preserve that emotion
- Empty arrays if nothing found in that category"""

    try:
        # Use structured output
        from pydantic import BaseModel
        from typing import List
        from src.core.agent import create_model
        from pydantic_ai import Agent
        
        class JournalData(BaseModel):
            events: List[str]
            thoughts: List[str]
            reminders: List[str]
            habits: List[str]
        
        model = create_model()
        simple_agent = Agent(model, model_settings={"temperature": 0.3})
        
        result = simple_agent.run_sync(prompt, output_type=JournalData)
        
        # result.output is the JournalData instance
        return {
            'events': result.output.events,
            'thoughts': result.output.thoughts,
            'reminders': result.output.reminders,
            'habits': result.output.habits
        }
        
    except Exception as e:
        logger.error(f"AI categorization failed: {e}")
        # Fallback: return basic structure
        return {
            'events': [entry for entry in formatted_entries],
            'thoughts': [],
            'reminders': [],
            'habits': []
        }


def generate_daily_note(date: str = None, dry_run: bool = False) -> str:
    """Generate daily Obsidian note from journal entries.
    
    NOTE: This is NOT an agent tool - it's for scheduler/automation only.
    
    Creates note at: brain/2. Time/2.2 Daily/YYYY-MM-DD.md
    
    Args:
        date: Date to generate (YYYY-MM-DD). Defaults to today.
        dry_run: If True, prints note content instead of writing file.
        
    Returns:
        Status message (or note content if dry_run=True)
    """
    from src.tools.weather import get_current_weather
    from src.tools.health import get_sleep_summary, get_recovery_status, get_steps, get_body_battery, get_stress
    from src.tools.calendar import get_today_schedule
    from src.tools.vault import vault_write_note
    from datetime import timedelta
    
    try:
        # Default to today
        if not date:
            date = datetime.now(get_brt()).strftime("%Y-%m-%d")
        
        logger.info(f"Generating daily note for {date}")
        
        # Get journal entries
        entries = get_journal_entries_for_date(date)
        if not entries:
            logger.info(f"No journal entries for {date}, skipping")
            return f"⏭️ No journal entries for {date}, skipped"
        
        logger.info(f"Found {len(entries)} entries")
        
        # Parse date
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        weekday = date_obj.strftime("%A")
        yesterday = (date_obj - timedelta(days=1)).strftime("%Y-%m-%d")
        tomorrow = (date_obj + timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Fetch data (with fallbacks)
        try:
            weather = get_current_weather()
            weather_desc = weather.get('description', 'unavailable')
            weather_temp = weather.get('temp', 0)  # Correct key is 'temp'
        except Exception as e:
            logger.warning(f"Weather fetch failed: {e}")
            weather_desc, weather_temp = 'unavailable', 0
        
        try:
            # Sleep should be from last night (yesterday's date)
            yesterday = (date_obj - timedelta(days=1)).strftime("%Y-%m-%d")
            sleep = get_sleep_summary(days=7)  # Get last 7 days
            sleep_nights = sleep.get('sleep_nights', [])
            # Find yesterday's sleep (last night)
            sleep_hours = 0
            sleep_score = 0
            for night in sleep_nights:
                if night.get('date') == yesterday or night.get('date') == date:
                    sleep_hours = night.get('total_hours', 0)
                    sleep_score = night.get('score', 0)
                    break
            if sleep_hours == 0 and sleep_nights:
                # Fallback to most recent
                sleep_hours = sleep_nights[0].get('total_hours', 0)
                sleep_score = sleep_nights[0].get('score', 0)
        except Exception as e:
            logger.warning(f"Sleep fetch failed: {e}")
            sleep_hours = 0
            sleep_score = 0
        
        try:
            # Get body battery from InfluxDB for the specific date
            bb_data = get_body_battery(date=date)
            bb_start = bb_data.get('start', 0)
            bb_end = bb_data.get('current', 0)
            
            # Get stress from InfluxDB for the specific date
            stress_data = get_stress(date=date)
            stress_avg = stress_data.get('average', 0)
            
            # Get training readiness
            recovery = get_recovery_status()
            tr = recovery.get('training_readiness', {})
            tr_score = tr.get('score', 0)
            tr_level = tr.get('level', 'N/A')
            hrv = recovery.get('overnight_hrv_ms', 0)
        except Exception as e:
            logger.warning(f"Recovery fetch failed: {e}")
            bb_start, bb_end, stress_avg, tr_score, tr_level, hrv = 0, 0, 0, 0, 'N/A', 0
        
        try:
            steps_data = get_steps(date=date)
            steps_today = steps_data.get('today', 0)
            steps_avg = steps_data.get('average_30d', 0)
            steps_diff = steps_data.get('vs_average', 0)
        except:
            steps_today, steps_avg, steps_diff = 0, 0, 0
        
        try:
            calendar = get_today_schedule()
            # Combine all event types
            current = calendar.get('current_events', [])
            upcoming = calendar.get('upcoming_events', [])
            completed = calendar.get('completed_events', [])
            events = current + upcoming + completed
        except Exception as e:
            logger.warning(f"Calendar fetch failed: {e}")
            events = []
        
        # AI categorization
        logger.info("Categorizing entries with AI...")
        categorized = _categorize_entries_with_ai(entries)
        
        # Extract data
        journal_events = categorized.get('events', [])
        thoughts = categorized.get('thoughts', [])
        reminders = categorized.get('reminders', [])
        detected_habits = categorized.get('habits', [])
        
        # Format journal sections
        journal_sections = ""
        
        if journal_events:
            journal_sections += "### Events\n"
            journal_sections += "\n".join([f"- {e}" for e in journal_events])
            journal_sections += "\n\n"
        
        if thoughts:
            journal_sections += "### Thoughts\n"
            journal_sections += "\n".join([f"- {t}" for t in thoughts])
            journal_sections += "\n\n"
        
        if reminders:
            journal_sections += "### Reminders\n"
            journal_sections += "\n".join([f"- [ ] {r}" for r in reminders])
            journal_sections += "\n\n"
        
        if not journal_sections:
            journal_sections = "(No entries categorized)"
        
        # Format calendar
        calendar_lines = []
        for event in events:
            try:
                if not isinstance(event, dict):
                    continue
                start = event.get('start', '')
                if 'T' in start:
                    time_str = datetime.fromisoformat(start.replace('Z', '+00:00')).astimezone(get_brt()).strftime("%H:%M")
                else:
                    time_str = "All day"
                title = event.get('title', event.get('summary', 'Event'))
                calendar_lines.append(f"{time_str} - {title}")
            except Exception as e:
                logger.warning(f"Failed to process calendar event: {e}")
                continue
        
        calendar_text = "\n".join(calendar_lines) if calendar_lines else "(No events)"
        
        # Steps insight
        steps_insight = ""
        if abs(steps_diff) > steps_avg * 0.5:
            comparison = "high" if steps_diff > 0 else "low"
            steps_insight = f"\n> Steps {comparison} ({steps_today} vs {steps_avg} avg)"
        
        # Raw entries
        raw_lines = []
        for entry in entries:
            time = datetime.fromisoformat(entry['timestamp']).strftime("%H:%M")
            prefix = "🎤 " if entry['entry_type'] == 'audio' else ""
            content = entry['content']
            raw_lines.append(f"**{time}** - {prefix}\"{content}\"")
        raw_text = "\n\n".join(raw_lines)
        
        # Check which habits were detected
        check_read = 'x' if 'Read' in detected_habits else ' '
        check_exercise = 'x' if 'Exercise' in detected_habits else ' '
        check_wife = 'x' if 'Quality time with wife' in detected_habits else ' '
        check_pets = 'x' if 'Quality time with pets' in detected_habits else ' '
        check_games = 'x' if 'Play games' in detected_habits else ' '
        check_meditation = 'x' if 'Meditation' in detected_habits else ' '
        
        # Build markdown
        markdown = f"""---
date: '{date}'
day: {weekday}
habits: {detected_habits}
sleep: {sleep_hours}h
sleep_score: {sleep_score}
tags:
  - time/daily
  - area/friday
weather: {weather_desc}, {weather_temp}°C
---
<< [[{yesterday}|Yesterday]] | [[{tomorrow}|Tomorrow]] >>

# [[{date}]]

## Weather
{weather_desc}, {weather_temp}°C

## Health
- **Sleep:** {sleep_hours:.1f}h (score: {sleep_score})
- **Body Battery:** {bb_start}%→{bb_end}%
- **Stress:** {stress_avg:.0f}
- **Training Readiness:** {tr_score} ({tr_level})
- **HRV:** {hrv}ms
- **Steps:** {steps_today}{steps_insight}

## Calendar
{calendar_text}

## Habits
- [{check_read}] Read
- [{check_exercise}] Exercise
- [{check_wife}] Quality time with wife
- [{check_pets}] Quality time with pets
- [{check_games}] Play games
- [{check_meditation}] Meditation

## Journal

{journal_sections}

---

<details>
<summary>Raw entries ({len(entries)})</summary>

{raw_text}

</details>
"""
        
        # Dry run: just return the markdown
        if dry_run:
            logger.info(f"DRY RUN: Generated note for {date} ({len(entries)} entries)")
            return markdown
        
        # Write to Obsidian (vault_write_note adds brain/ prefix)
        note_path = f"2. Time/2.2 Daily/{date}.md"
        logger.info(f"Writing to {note_path}")
        
        result = vault_write_note(note_path, markdown, mode="overwrite")
        
        if "Success" in result:
            logger.info(f"✓ Daily note generated: {len(entries)} entries")
            return f"✅ Daily note generated: {len(entries)} entries"
        else:
            logger.error(f"Failed to write: {result}")
            return f"❌ Failed: {result}"
        
    except Exception as e:
        logger.error(f"Error generating note: {e}", exc_info=True)
        return f"❌ Error: {e}"
