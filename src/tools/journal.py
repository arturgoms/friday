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
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from settings import settings
from src.core.agent import agent
from src.core.database import Database

logger = logging.getLogger(__name__)


def get_brt():
    """Get BRT timezone from settings."""
    return settings.TIMEZONE


def _format_sleep_duration(hours: float) -> str:
    """Convert decimal hours to hours:minutes format.
    
    Args:
        hours: Sleep duration in decimal hours (e.g., 7.5)
        
    Returns:
        Formatted string like "7:30" (hours:minutes)
    """
    if hours <= 0:
        return "0:00"
    h = int(hours)
    m = int((hours - h) * 60)
    return f"{h}:{m:02d}"


def _infer_weather_description(cloud_cover: float, precipitation: float) -> str:
    """Infer weather description from historical metrics.

    Args:
        cloud_cover: Cloud cover percentage (0-100)
        precipitation: Precipitation in mm

    Returns:
        Natural weather description string
    """
    # Base description from cloud cover
    if cloud_cover < 20:
        desc = "clear sky"
    elif cloud_cover < 40:
        desc = "few clouds"
    elif cloud_cover < 60:
        desc = "partly cloudy"
    elif cloud_cover < 85:
        desc = "mostly cloudy"
    else:
        desc = "overcast"

    # Add precipitation if significant
    if precipitation > 20:
        desc = f"heavy rain, {desc}"
    elif precipitation > 5:
        desc = f"rain, {desc}"
    elif precipitation > 0.5:
        desc = f"light rain, {desc}"

    return desc


# =============================================================================
# Journal Thread Management
# =============================================================================


def create_starter_note(date: str = None) -> str:
    """Create a starter note for the day with weather and empty journal sections.

    NOTE: This is NOT an agent tool - it's for scheduler/automation only.

    Args:
        date: Date in YYYY-MM-DD format. Defaults to today.

    Returns:
        Status message
    """
    try:
        from src.tools.weather import get_weather
        from src.tools.vault import vault_write_note

        # Default to today
        if not date:
            date = datetime.now(get_brt()).strftime("%Y-%m-%d")

        date_obj = datetime.strptime(date, "%Y-%m-%d")
        weekday = date_obj.strftime("%A")

        logger.info(f"Creating starter note for {date}")

        # Get weather for today
        weather = get_weather(date=date)
        if weather.get('error'):
            weather_desc = 'unavailable'
            weather_temp = 0
        else:
            weather_desc = weather.get('description', 'unavailable')
            weather_temp = weather.get('temp', 0)

        # Build starter note
        markdown = f"""---
date: '{date}'
day: {weekday}
---

# [[{date}]]

## Weather
{weather_desc}, {weather_temp}°C

## Journal

### Notes
-

### Reminder
"""

        # Write to vault (check if exists first)
        note_path = f"2. Time/2.2 Daily/{date}.md"

        # Check if note already exists
        from pathlib import Path
        vault_path = settings.VAULT_PATH / note_path
        if vault_path.exists():
            logger.info(f"Starter note already exists for {date}")
            return f"ℹ️ Starter note already exists for {date}"

        result = vault_write_note(note_path, markdown, mode="overwrite")

        if "Success" in result:
            logger.info(f"✓ Starter note created for {date}")
            return f"✅ Starter note created for {date}"
        elif "already exists" in result:
            logger.info(f"Starter note already exists for {date}")
            return f"ℹ️ Starter note already exists for {date}"
        else:
            logger.error(f"Failed to create starter note: {result}")
            return f"❌ Failed to create starter note: {result}"

    except Exception as e:
        logger.error(f"Error creating starter note: {e}")
        return f"❌ Error creating starter note: {e}"


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
    thread_message_id: Optional[int] = None,
    date: Optional[str] = None,
    time: Optional[str] = None
) -> bool:
    """Save a journal entry to the database.
    
    Args:
        content: The text content (or transcribed audio)
        entry_type: Either "text" or "audio"
        thread_message_id: The thread message ID this is replying to
        date: Optional date in YYYY-MM-DD format (defaults to today)
        time: Optional time in HH:MM format (defaults to current time)
        
    Returns:
        True if saved successfully
    """
    try:
        db = Database()
        now = datetime.now(get_brt())
        
        # Use provided date or today
        entry_date = date or now.strftime("%Y-%m-%d")
        
        # Build timestamp
        if date and time:
            # User provided both date and time
            timestamp_str = f"{date}T{time}:00"
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S")
            timestamp = timestamp.replace(tzinfo=get_brt())
        elif date:
            # User provided date but no time - use noon as default
            timestamp_str = f"{date}T12:00:00"
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S")
            timestamp = timestamp.replace(tzinfo=get_brt())
        else:
            # Use current timestamp
            timestamp = now
        
        db.insert('journal_entries', {
            'date': entry_date,
            'timestamp': timestamp.isoformat(),
            'entry_type': entry_type,
            'content': content,
            'thread_message_id': thread_message_id
        })
        
        logger.info(f"Saved journal entry ({entry_type}) for {entry_date}: {content[:50]}...")
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
# Manual Content Extraction
# =============================================================================


def _extract_manual_content(date: str) -> dict[str, list[str]]:
    """Extract manual notes and reminders from existing daily note.

    Args:
        date: Date in YYYY-MM-DD format

    Returns:
        Dict with:
        - notes: List of note items (strings)
        - reminders: List of reminder items with checkboxes (strings)
    """
    try:
        from src.tools.vault import vault_read_note

        # Read existing note
        note_path = f"2. Time/2.2 Daily/{date}.md"
        content = vault_read_note(note_path)

        if not content or "error" in content.lower():
            logger.info(f"No existing note found for {date}")
            return {"notes": [], "reminders": []}

        # Parse the note to extract manual content
        lines = content.split('\n')
        notes = []
        reminders = []

        current_section = None
        in_journal = False

        for line in lines:
            # Check for Journal section
            if line.strip() == "## Journal":
                in_journal = True
                current_section = None
                continue

            # Check for end of Journal section (next ## heading)
            if in_journal and line.strip().startswith("## ") and line.strip() != "## Journal":
                break

            # Check for Notes subsection
            if in_journal and line.strip() == "### Notes":
                current_section = "notes"
                continue

            # Check for Reminder subsection
            if in_journal and line.strip() == "### Reminder":
                current_section = "reminders"
                continue

            # Check for other subsections (Events, Thoughts) - stop collecting
            if in_journal and line.strip().startswith("### ") and line.strip() not in ["### Notes", "### Reminder"]:
                current_section = None
                continue

            # Collect content based on current section
            if current_section == "notes" and line.strip():
                # Skip placeholder lines
                if line.strip() not in ["-", "(Add notes here throughout the day)"]:
                    notes.append(line.strip())

            elif current_section == "reminders" and line.strip():
                # Skip placeholder lines
                if line.strip() not in ["- [ ]", "(Add todos here)"]:
                    reminders.append(line.strip())

        logger.info(f"Extracted {len(notes)} notes and {len(reminders)} reminders from existing note")
        return {"notes": notes, "reminders": reminders}

    except Exception as e:
        logger.warning(f"Could not extract manual content: {e}")
        return {"notes": [], "reminders": []}


# =============================================================================
# Phase 2: Daily Note Generation (Simplified)
# =============================================================================


def _get_garmin_activities_for_date(date: str) -> list[dict[str, Any]]:
    """Get Garmin activities for specific date.

    Args:
        date: Date in YYYY-MM-DD format

    Returns:
        List of activities with name, duration, distance
    """
    try:
        # Query InfluxDB directly for activities on this date
        from src.core.influxdb import query as _query

        # Date range for the query
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        start = date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

        # Query activities
        activities_data = _query(f"""
            SELECT activityName, activityType, movingDuration, distance
            FROM ActivitySummary
            WHERE time >= '{start.strftime('%Y-%m-%dT%H:%M:%SZ')}'
              AND time < '{end.strftime('%Y-%m-%dT%H:%M:%SZ')}'
        """)

        formatted = []
        for activity in activities_data:
            name = activity.get('activityName', 'Activity')
            duration_sec = activity.get('movingDuration', 0) or 0
            distance_m = activity.get('distance', 0) or 0

            formatted.append({
                'name': name,
                'type': activity.get('activityType', 'unknown'),
                'duration_min': int(duration_sec / 60),
                'distance_km': distance_m / 1000
            })

        return formatted
    except Exception as e:
        logger.warning(f"Could not fetch Garmin activities: {e}")
        return []


def _get_habit_relevant_calendar_events(date: str) -> list[str]:
    """Get calendar events that might indicate habits.

    Args:
        date: Date in YYYY-MM-DD format

    Returns:
        List of event titles suggesting habits
    """
    try:
        from src.tools.calendar import get_schedule

        calendar = get_schedule(date=date)

        # Extract events
        if 'events' in calendar:
            events = calendar.get('events', [])
        else:
            current = calendar.get('current_events', [])
            upcoming = calendar.get('upcoming_events', [])
            completed = calendar.get('completed_events', [])
            events = current + upcoming + completed

        # Filter for habit-related keywords
        habit_keywords = [
            'meditation', 'book', 'read', 'club', 'exercise',
            'yoga', 'run', 'walk', 'pets', 'dog', 'date', 'wife',
            'game', 'gaming', 'family time', 'workout', 'gym',
            'pilates', 'cycling', 'swim', 'library', 'journal'
        ]

        relevant_events = []
        for event in events:
            if not isinstance(event, dict):
                continue
            title = event.get('title', '').lower()
            if any(keyword in title for keyword in habit_keywords):
                relevant_events.append(event.get('title', ''))

        return relevant_events
    except Exception as e:
        logger.warning(f"Could not fetch calendar events: {e}")
        return []


async def _categorize_entries_with_ai(entries: list, date: str, manual_notes: list[str] = None) -> dict:
    """Enhanced categorization with multi-source habit detection.

    Args:
        entries: List of raw journal entries from Telegram
        date: Date in YYYY-MM-DD format
        manual_notes: List of manual notes from the daily note file

    Returns:
        Dict with events, thoughts, reminders, habits lists (with metadata)
    """
    # Format Telegram entries for AI
    formatted_entries = []
    for entry in entries:
        time = datetime.fromisoformat(entry['timestamp']).strftime("%H:%M")
        prefix = "🎤 " if entry['entry_type'] == 'audio' else ""
        formatted_entries.append(f"**{time}** - {prefix}{entry['content']}")

    # Add manual notes to formatted entries
    if manual_notes:
        for note in manual_notes:
            # Clean up markdown list formatting
            note_clean = note.lstrip('- ').strip()
            if note_clean:
                formatted_entries.append(f"**Manual** - {note_clean}")

    entries_text = "\n\n".join(formatted_entries) if formatted_entries else "No journal entries"

    # Get Garmin activities
    garmin_activities = _get_garmin_activities_for_date(date)
    if garmin_activities:
        garmin_lines = []
        for activity in garmin_activities:
            name = activity['name']
            duration = activity['duration_min']
            distance = activity.get('distance_km', 0)
            if distance > 0:
                garmin_lines.append(f"- {name}: {distance:.1f}km in {duration}min")
            else:
                garmin_lines.append(f"- {name}: {duration}min")
        garmin_text = "\n".join(garmin_lines)
    else:
        garmin_text = "No activities recorded"

    # Get calendar events
    calendar_events = _get_habit_relevant_calendar_events(date)
    calendar_text = "\n".join([f"- {event}" for event in calendar_events]) if calendar_events else "No relevant events"

    # Enhanced prompt with multi-source detection
    prompt = f"""You are analyzing my day from ALL sources (some in Portuguese). Detect habits and categorize journal entries.

JOURNAL ENTRIES:
{entries_text}

GARMIN ACTIVITIES:
{garmin_text}

CALENDAR EVENTS:
{calendar_text}

TASK:
1. Translate Portuguese to English naturally
2. Enhance and clarify journal entries
3. Organize journal into categories:
   - Events: Things that happened (past tense, completed actions)
   - Thoughts: Reflections, feelings, ideas, dreams, wishes
   - Reminders: ONLY explicit future TODOs (NOT past events, NOT dreams, NOT thoughts)
4. Detect ALL habits from ANY source:
   - Be INCLUSIVE: detect any activities (exercise, reading, hobbies, social time)
   - **CRITICAL**: Detect the SAME habit only ONCE even if it appears in multiple sources
   - When the same activity appears in Garmin AND Calendar, create only ONE habit entry (prefer Garmin as source since it's confirmed)
   - Extract the actual activity from calendar titles:
     • "Exercise time: Pilates" → Extract "Pilates"
     • "Morning Routine" → Extract relevant activity if clear
     • "Book club meeting" → Extract "Reading"
   - Normalize similar activities:
     • Running, jogging, run → Running
     • Cycling, bike ride → Cycling
     • Reading, book club, library → Reading
     • Wife time, date night, time with wife → Quality time - wife
     • Dog walk, pet care, time with dog → Quality time - pets
     • Gaming, played games, video games → Gaming
     • Meditation, mindfulness → Meditation
     • Pilates, pilates class → Pilates
     • Yoga, yoga class → Yoga
   - For each habit provide:
     * name: Normalized habit name (extract from calendar titles)
     * confidence: 1.0 (Garmin/explicit), 0.9 (calendar/strong), 0.7 (implied)
     * source: "garmin", "calendar", or "journal" (prefer "garmin" if activity is in both Garmin and Calendar)
     * evidence: Brief quote or reference

Return as JSON:
{{
  "events": ["event 1", ...],
  "thoughts": ["thought 1", ...],
  "reminders": ["reminder 1", ...],
  "habits": [
    {{"name": "Running", "confidence": 1.0, "source": "garmin", "evidence": "5.2km run"}},
    {{"name": "Reading", "confidence": 0.9, "source": "journal", "evidence": "finished chapter 5"}},
    ...
  ]
}}

EXAMPLES:
- Garmin shows "Pilates: 44min" + Calendar shows "Exercise time: Pilates"
  → ONE habit: {{"name": "Pilates", "confidence": 1.0, "source": "garmin", "evidence": "Pilates: 44min"}}
- Calendar shows "Book club meeting"
  → {{"name": "Reading", "confidence": 0.9, "source": "calendar", "evidence": "Book club meeting"}}

CONFIDENCE RULES:
- Garmin activities: always 1.0 (confirmed data)
- Calendar habit events: 0.9 (scheduled activity)
- Journal explicit ("went running", "read a book"): 0.9
- Journal implicit ("caught up on Dune"): 0.7
- Empty arrays if nothing found

REMINDER RULES (CRITICAL):
Reminders are ONLY explicit future action items. Do NOT create reminders from:
- Past events: "indo comprar pão" (going to buy bread) → Event, NOT reminder (already happening/done)
- Dreams: "my phone exploded in dream" → Thought, NOT reminder (not real)
- Implicit wishes: "I want to tell therapist" → Thought, NOT reminder (unless explicitly stated as TODO)
- Ongoing actions: "preparing for meetings" → Event, NOT reminder (already doing it)
- Past discussions: "discussed getting dog" → Event, NOT reminder (already happened)

ONLY create reminders for:
- Explicit TODOs: "I need to call the doctor tomorrow"
- Clear action items: "Remember to buy milk"
- Stated intentions: "I should schedule dentist appointment"

If no explicit future TODOs exist, return empty reminders array: "reminders": []

GUIDELINES:
- Keep my voice and personality in events/thoughts
- Fix grammar but maintain authenticity
- Be concise but complete
- Preserve emotions"""

    try:
        # Use structured output
        from pydantic import BaseModel
        from typing import List
        from src.core.agent import create_model
        from pydantic_ai import Agent

        class HabitDetection(BaseModel):
            name: str
            confidence: float
            source: str
            evidence: str

        class JournalData(BaseModel):
            events: List[str]
            thoughts: List[str]
            reminders: List[str]
            habits: List[HabitDetection]

        model = create_model()
        simple_agent = Agent(model, model_settings={"temperature": 0.3})

        # Use async run() instead of run_sync() to work within existing event loop
        result = await simple_agent.run(prompt, output_type=JournalData)

        # result.output is the JournalData instance
        return {
            'events': result.output.events,
            'thoughts': result.output.thoughts,
            'reminders': result.output.reminders,
            'habits': [h.dict() for h in result.output.habits]  # Convert to dicts
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


async def _generate_ai_insight(note_data: dict) -> str:
    """Generate a creative AI insight based on the day's data.
    
    Args:
        note_data: Dict containing all the day's data (health, calendar, journal, etc.)
        
    Returns:
        A creative insight string
    """
    # Build context from note data
    context_parts = []
    
    # Date info
    context_parts.append(f"Date: {note_data['date']} ({note_data['weekday']})")
    
    # Health metrics
    context_parts.append(f"Sleep: {note_data['sleep_duration']} (score: {note_data['sleep_score']})")
    if note_data.get('nap_detected') and note_data.get('nap_duration_minutes', 0) > 0:
        nap_mins = note_data['nap_duration_minutes']
        nap_h, nap_m = nap_mins // 60, nap_mins % 60
        context_parts.append(f"Nap: {nap_h}h {nap_m}m" if nap_h > 0 else f"Nap: {nap_m}m")
    context_parts.append(f"Body Battery: sleep recharged +{note_data['bb_sleep_recharge']}% (to {note_data['bb_start']}%), day activities drained -{note_data['bb_day_drain']}% (to {note_data['bb_end']}%)")
    context_parts.append(f"Stress: {note_data['stress_rest_hours']:.1f}h rest, {note_data['stress_stress_hours']:.1f}h stress ({note_data['stress_rest_pct']}% rest)")
    context_parts.append(f"Training Readiness: {note_data['tr_score']} ({note_data['tr_level']})")
    context_parts.append(f"HRV: {note_data['hrv']}ms")
    context_parts.append(f"Steps: {note_data['steps_today']} (30-day avg: {note_data['steps_avg']})")
    
    # Weather
    context_parts.append(f"Weather: {note_data['weather_desc']}, {note_data['weather_temp']}°C")
    
    # Calendar
    if note_data['calendar_events']:
        context_parts.append(f"Calendar events: {', '.join(note_data['calendar_events'][:5])}")
    
    # Journal content
    if note_data['journal_events']:
        context_parts.append(f"What happened: {'; '.join(note_data['journal_events'][:3])}")
    if note_data['thoughts']:
        context_parts.append(f"Thoughts/feelings: {'; '.join(note_data['thoughts'][:3])}")
    
    # Habits (with sources)
    if note_data['detected_habits']:
        habit_summary = []
        for habit in note_data['detected_habits']:
            if isinstance(habit, dict):
                name = habit.get('name', '')
                source = habit.get('source', 'unknown')
                habit_summary.append(f"{name} ({source})")
            else:
                # Fallback for old format (just strings)
                habit_summary.append(str(habit))
        context_parts.append(f"Habits detected: {', '.join(habit_summary)}")
    
    context = "\n".join(context_parts)
    
    prompt = f"""You are Friday, Artur's personal AI assistant. Based on this day's data, write a brief, insightful reflection (2-4 sentences).

DATA:
{context}

GUIDELINES:
- Be conversational and warm, like a thoughtful friend
- Find interesting patterns or connections in the data
- You can be creative - notice correlations, give encouragement, gentle suggestions, or interesting observations
- If sleep/stress/energy data tells a story, mention it
- If there's a mismatch (e.g., busy day but low steps, or high stress but good sleep), note it
- Keep it personal and relevant to Artur's day
- Don't just list facts - interpret them
- If data is sparse, focus on what IS there
- Write in first person as if talking to Artur directly
- No need for greetings or sign-offs, just the insight itself

Write the insight:"""

    try:
        from src.core.agent import create_model
        from pydantic_ai import Agent
        
        model = create_model()
        simple_agent = Agent(model, model_settings={"temperature": 0.7})
        
        result = await simple_agent.run(prompt)
        return result.output.strip()
        
    except Exception as e:
        logger.error(f"AI insight generation failed: {e}")
        return ""


def _render_habits_section(habits: list[dict[str, Any]]) -> str:
    """Render habits with clean markdown formatting (no emojis).

    Groups duplicate habits by name and merges their sources and evidence.

    Args:
        habits: List of habit dicts with name, confidence, source, evidence

    Returns:
        Formatted markdown section or empty string
    """
    if not habits:
        return ""

    # Filter by confidence
    high_confidence = [h for h in habits if h['confidence'] >= 0.8]
    medium_confidence = [h for h in habits if 0.6 <= h['confidence'] < 0.8]

    if not high_confidence and not medium_confidence:
        return ""

    lines = ["## Habits\n"]

    # High confidence habits - group by name (case-insensitive)
    if high_confidence:
        grouped = {}
        for habit in high_confidence:
            name = habit['name']
            name_key = name.lower()

            if name_key not in grouped:
                grouped[name_key] = {
                    'display_name': name,  # Use first occurrence for display
                    'sources': [],
                    'evidence': []
                }

            # Add source (avoid duplicates)
            source_title = habit['source'].title()
            if source_title not in grouped[name_key]['sources']:
                grouped[name_key]['sources'].append(source_title)

            # Add evidence if present
            if habit.get('evidence'):
                grouped[name_key]['evidence'].append(habit['evidence'])

        # Render grouped habits
        for habit_data in grouped.values():
            name = habit_data['display_name']
            sources = ", ".join(habit_data['sources'])

            # Format: - **Name** (Source1, Source2)
            lines.append(f"- **{name}** ({sources})")

            # All evidence as italic sub-bullets
            for evidence in habit_data['evidence']:
                lines.append(f"  - _{evidence}_")

        lines.append("")

    # Medium confidence (collapsed) - also deduplicate
    if medium_confidence:
        lines.append("<details>")
        lines.append("<summary>Possible habits (lower confidence)</summary>")
        lines.append("")

        # Group medium confidence habits too
        grouped_medium = {}
        for habit in medium_confidence:
            name = habit['name']
            name_key = name.lower()

            if name_key not in grouped_medium:
                grouped_medium[name_key] = {
                    'display_name': name,
                    'max_confidence': habit['confidence']
                }
            else:
                # Keep highest confidence
                if habit['confidence'] > grouped_medium[name_key]['max_confidence']:
                    grouped_medium[name_key]['max_confidence'] = habit['confidence']

        for habit_data in grouped_medium.values():
            name = habit_data['display_name']
            confidence_pct = int(habit_data['max_confidence'] * 100)
            lines.append(f"- {name} ({confidence_pct}%)")

        lines.append("</details>")
        lines.append("")

    return "\n".join(lines)


async def generate_daily_note(date: str = None, dry_run: bool = False) -> str:
    """Generate daily Obsidian note from journal entries.
    
    NOTE: This is NOT an agent tool - it's for scheduler/automation only.
    
    Creates note at: brain/2. Time/2.2 Daily/YYYY-MM-DD.md
    
    Args:
        date: Date to generate (YYYY-MM-DD). Defaults to today.
        dry_run: If True, prints note content instead of writing file.
        
    Returns:
        Status message (or note content if dry_run=True)
    """
    from src.tools.weather import get_weather
    from src.tools.health import get_sleep_summary, get_recovery_status, get_steps, get_body_battery, get_stress
    from src.tools.calendar import get_schedule
    from src.tools.vault import vault_write_note
    from datetime import timedelta
    
    try:
        # Default to today
        if not date:
            date = datetime.now(get_brt()).strftime("%Y-%m-%d")
        
        logger.info(f"Generating daily note for {date}")

        # Extract manual content from existing note (if exists)
        manual_content = _extract_manual_content(date)
        manual_notes = manual_content["notes"]
        manual_reminders = manual_content["reminders"]
        logger.info(f"Found {len(manual_notes)} manual notes and {len(manual_reminders)} manual reminders")

        # Get journal entries (may be empty - that's OK)
        entries = get_journal_entries_for_date(date)
        logger.info(f"Found {len(entries)} Telegram entries for {date}")

        # Parse date
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        weekday = date_obj.strftime("%A")
        yesterday = (date_obj - timedelta(days=1)).strftime("%Y-%m-%d")
        tomorrow = (date_obj + timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Fetch data (with fallbacks)
        try:
            weather = get_weather(date=date)
            if weather.get('error'):
                weather_desc = 'unavailable'
                weather_temp = 0
            elif weather.get('source') == 'onecall_day_summary':
                # Historical data - infer description from metrics
                cloud_cover = weather.get('cloud_cover', 0)
                precipitation = weather.get('precipitation', 0)
                weather_desc = _infer_weather_description(cloud_cover, precipitation)
                weather_temp = weather.get('temp', 0)
            else:
                weather_desc = weather.get('description', 'unavailable')
                weather_temp = weather.get('temp', 0)
        except Exception as e:
            logger.warning(f"Weather fetch failed: {e}")
            weather_desc, weather_temp = 'unavailable', 0
        
        try:
            # Sleep should be from last night (yesterday's date)
            yesterday = (date_obj - timedelta(days=1)).strftime("%Y-%m-%d")
            sleep = get_sleep_summary(days=7, date=date)  # Get last 7 days + nap info for this date
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
            # Format sleep duration as h:mm
            sleep_duration = _format_sleep_duration(sleep_hours)
            
            # Get nap info for this date
            nap_info = sleep.get('nap_info', {})
            nap_detected = nap_info.get('nap_detected', False)
            nap_duration_minutes = nap_info.get('nap_duration_minutes', 0)
            nap_start = nap_info.get('nap_start', '')
            nap_end = nap_info.get('nap_end', '')
            nap_battery_gain = nap_info.get('battery_gain', 0)
        except Exception as e:
            logger.warning(f"Sleep fetch failed: {e}")
            sleep_hours = 0
            sleep_score = 0
            sleep_duration = "0:00"
            nap_detected = False
            nap_duration_minutes = 0
            nap_start = ''
            nap_end = ''
            nap_battery_gain = 0
        
        try:
            # Get body battery from InfluxDB for the specific date
            bb_data = get_body_battery(date=date)
            bb_start = bb_data.get('start', 0)
            bb_end = bb_data.get('end', bb_data.get('current', 0))
            bb_max = bb_data.get('max', 0)  # Peak after sleep recovery
            
            # Calculate sleep recharge (start -> max) and day drain (max -> end)
            bb_sleep_recharge = bb_max - bb_start
            bb_day_drain = bb_max - bb_end
            
            # Get stress from InfluxDB for the specific date
            stress_data = get_stress(date=date)
            stress_avg = stress_data.get('average', 0)
            stress_rest_hours = stress_data.get('rest_hours', 0)
            stress_stress_hours = stress_data.get('stress_hours', 0)
            stress_rest_pct = stress_data.get('rest_pct', 0)
            
            # Get training readiness
            recovery = get_recovery_status()
            tr = recovery.get('training_readiness', {})
            tr_score = tr.get('score', 0)
            tr_level = tr.get('level', 'N/A')
            hrv = recovery.get('overnight_hrv_ms', 0)
        except Exception as e:
            logger.warning(f"Recovery fetch failed: {e}")
            bb_start, bb_end, bb_max, bb_sleep_recharge, bb_day_drain, stress_avg, stress_rest_hours, stress_stress_hours, stress_rest_pct, tr_score, tr_level, hrv = 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 'N/A', 0
        
        try:
            steps_data = get_steps(date=date)
            steps_today = steps_data.get('today', 0)
            steps_avg = steps_data.get('average_30d', 0)
            steps_diff = steps_data.get('vs_average', 0)
        except Exception as e:
            logger.debug(f"Could not get steps data: {e}")
            steps_today, steps_avg, steps_diff = 0, 0, 0
        
        try:
            calendar = get_schedule(date=date)
            # Handle both today's format (categorized) and other dates format (flat list)
            if 'events' in calendar:
                # Other dates: flat list
                events = calendar.get('events', [])
            else:
                # Today: categorized by status
                current = calendar.get('current_events', [])
                upcoming = calendar.get('upcoming_events', [])
                completed = calendar.get('completed_events', [])
                events = current + upcoming + completed
        except Exception as e:
            logger.warning(f"Calendar fetch failed: {e}")
            events = []
        
        # AI categorization (with multi-source habit detection + manual notes)
        if entries or manual_notes:
            try:
                logger.info("Categorizing entries with AI (including manual notes)...")
                categorized = await _categorize_entries_with_ai(entries, date, manual_notes)
                journal_events = categorized.get('events', [])
                thoughts = categorized.get('thoughts', [])
                ai_reminders = categorized.get('reminders', [])  # AI-generated reminders
                detected_habits = categorized.get('habits', [])
            except Exception as e:
                logger.warning(f"AI categorization unavailable (vLLM offline): {e}")
                # Fallback: no categorization, just raw entries in events
                journal_events = [f"{entry['content']}" for entry in entries] if entries else []
                journal_events.extend(manual_notes)  # Add manual notes too
                thoughts = []
                ai_reminders = []
                detected_habits = []
        else:
            try:
                logger.info("No entries or manual notes to categorize")
                categorized = await _categorize_entries_with_ai([], date, [])  # Still detect Garmin/calendar habits
                journal_events, thoughts, ai_reminders = [], [], []
                detected_habits = categorized.get('habits', [])
            except Exception as e:
                logger.warning(f"AI habit detection unavailable (vLLM offline): {e}")
                journal_events, thoughts, ai_reminders = [], [], []
                detected_habits = []
        
        # Format journal sections
        journal_sections = ""

        # Notes section (preserved from manual edits)
        if manual_notes:
            journal_sections += "### Notes\n\n"
            journal_sections += "\n".join(manual_notes)
            journal_sections += "\n\n"
        else:
            journal_sections += "### Notes\n\n-\n\n"

        # Reminders section (merged: manual + AI-generated)
        all_reminders = []
        # Add manual reminders first (preserve exactly as written)
        if manual_reminders:
            all_reminders.extend(manual_reminders)
        # Add AI-generated reminders
        if ai_reminders:
            for r in ai_reminders:
                # Format as checkbox if not already
                if not r.strip().startswith('- [ ]'):
                    all_reminders.append(f"- [ ] {r}")
                else:
                    all_reminders.append(r)

        if all_reminders:
            journal_sections += "### Reminder\n\n"
            journal_sections += "\n".join(all_reminders)
            journal_sections += "\n\n"
        else:
            journal_sections += "### Reminder\n\n- [ ]\n\n"

        # Events (AI categorized)
        if journal_events:
            journal_sections += "### Events\n\n"
            journal_sections += "\n".join([f"- {e}" for e in journal_events])
            journal_sections += "\n\n"

        # Thoughts (AI categorized)
        if thoughts:
            journal_sections += "### Thoughts\n\n"
            journal_sections += "\n".join([f"- {t}" for t in thoughts])
            journal_sections += "\n\n"
        
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
        
        # Raw entries (only if there are entries)
        raw_text = ""
        if entries:
            raw_lines = []
            for entry in entries:
                time = datetime.fromisoformat(entry['timestamp']).strftime("%H:%M")
                prefix = "🎤 " if entry['entry_type'] == 'audio' else ""
                content = entry['content']
                raw_lines.append(f"**{time}** - {prefix}\"{content}\"")
            raw_text = "\n\n".join(raw_lines)
        
        # Render habits section (badge format, no emojis)
        habits_section = _render_habits_section(detected_habits)

        # Extract habit names for frontmatter (high confidence only)
        # Deduplicate by converting to set, then back to list (case-insensitive deduplication)
        habit_names_raw = [h['name'] for h in detected_habits if h['confidence'] >= 0.8]
        # Use dict to preserve first occurrence while deduplicating case-insensitively
        seen = {}
        for name in habit_names_raw:
            name_key = name.lower()
            if name_key not in seen:
                seen[name_key] = name
        habit_names = list(seen.values())
        # Always include habits key (even if empty) for Dataview queries
        habits_frontmatter = habit_names if habit_names else []
        
        # Build raw entries section (only if entries exist)
        raw_entries_section = ""
        if entries:
            raw_entries_section = f"""
---

<details>
<summary>Raw entries ({len(entries)})</summary>

{raw_text}

</details>
"""
        
        # Generate AI insight
        logger.info("Generating AI insight...")
        note_data = {
            'date': date,
            'weekday': weekday,
            'sleep_duration': sleep_duration,
            'sleep_score': sleep_score,
            'nap_detected': nap_detected,
            'nap_duration_minutes': nap_duration_minutes,
            'bb_start': bb_start,
            'bb_end': bb_end,
            'bb_sleep_recharge': bb_sleep_recharge,
            'bb_day_drain': bb_day_drain,
            'stress_avg': stress_avg,
            'stress_rest_hours': stress_rest_hours,
            'stress_stress_hours': stress_stress_hours,
            'stress_rest_pct': stress_rest_pct,
            'tr_score': tr_score,
            'tr_level': tr_level,
            'hrv': hrv,
            'steps_today': steps_today,
            'steps_avg': steps_avg,
            'weather_desc': weather_desc,
            'weather_temp': weather_temp,
            'calendar_events': calendar_lines,
            'journal_events': journal_events,
            'thoughts': thoughts,
            'detected_habits': detected_habits,
        }
        try:
            ai_insight = await _generate_ai_insight(note_data)
        except Exception as e:
            logger.warning(f"AI insight generation unavailable (vLLM offline): {e}")
            ai_insight = ""  # Skip AI insight if offline
        
        # Format AI insight section
        ai_insight_section = ""
        if ai_insight:
            ai_insight_section = f"""
## AI Insight

> {ai_insight}
"""
        
        # Format nap duration for frontmatter (float hours)
        nap_hours = nap_duration_minutes // 60
        nap_mins = nap_duration_minutes % 60
        nap_duration_hours = nap_duration_minutes / 60  # Float for frontmatter
        
        # Format nap line for Health section (only if nap detected)
        nap_line = ""
        if nap_detected and nap_duration_minutes > 0:
            nap_display = f"{nap_hours}h {nap_mins}m" if nap_hours > 0 else f"{nap_mins}m"
            nap_line = f"\n- **Nap:** {nap_display} ({nap_start}-{nap_end}, recharged {nap_battery_gain}%)"
        
        # Build markdown
        markdown = f"""---
date: '{date}'
day: {weekday}
habits: {habits_frontmatter}
sleep_duration: {sleep_hours:.2f}
sleep_score: {sleep_score}
nap_duration: {nap_duration_hours:.2f}
tags:
  - time/daily
  - area/friday
temperature: {weather_temp}
---
<< [[{yesterday}|Yesterday]] | [[{tomorrow}|Tomorrow]] >>

# [[{date}]]

## Weather
{weather_desc}, {weather_temp}°C

## Health
- **Sleep:** {sleep_duration} (score: {sleep_score}, +{bb_sleep_recharge}% battery){nap_line}
- **Body Battery:** {bb_max}%→{bb_end}% (-{bb_day_drain}% today)
- **Stress:** {stress_rest_hours:.1f}h rest / {stress_stress_hours:.1f}h stress ({stress_rest_pct}% rest)
- **Training Readiness:** {tr_score} ({tr_level})
- **HRV:** {hrv}ms
- **Steps:** {steps_today}{steps_insight}

## Calendar
{calendar_text}

{habits_section}

## Journal

{journal_sections}
{ai_insight_section}
{raw_entries_section}"""
        
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
