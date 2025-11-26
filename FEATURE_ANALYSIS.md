# Friday AI - Comprehensive Feature Analysis & Roadmap

## Executive Summary

Friday AI is a **personal homelab AI assistant** with strong foundations in RAG, memory, health coaching, and automation. This analysis identifies **current capabilities**, **gaps**, and **high-impact improvements** to make it more useful.

---

## Current Features (What You Have)

### ✅ Core AI Capabilities
- **RAG (Retrieval Augmented Generation)**: Query 687 chunks from Obsidian vault
- **Two-Stage Architecture**: Intent router → Response generator (no tool pollution)
- **Memory System**: Store/retrieve personal memories as Obsidian notes
- **Web Search**: DuckDuckGo integration for fresh information
- **Conversation History**: Multi-turn conversations with context
- **Streaming Responses**: Real-time response generation

### ✅ Health & Fitness
- **Garmin Integration**: Reads from InfluxDB
  - Sleep data, training readiness, HRV, body battery
  - Running stats, activities, VO2 max
  - Recovery recommendations
- **Automated Reports**:
  - Morning report (9:00 AM): Sleep, recovery, schedule, weather
  - Evening report (11:00 PM): Activity summary, tomorrow prep
  - Weekly report (Monday 8:00 AM): 30-day running analysis
- **Health Coach**: Personalized autism-friendly insights

### ✅ Productivity & Organization
- **Calendar Integration**: Google Calendar + Nextcloud CalDAV
  - Today/tomorrow/week queries
  - Next event reminders
- **Reminders Service**: Create, list, cancel reminders
  - Time-based (minutes, hours, specific time)
  - Automatic cleanup of old reminders
- **Date/Time Tools**: Timezone-aware (UTC-3) calculations

### ✅ Automation & Infrastructure
- **File Watcher**: Auto-reindex on Obsidian changes (debounced, incremental)
- **Scheduler**: Unified task scheduler for all background jobs
- **Telegram Bot**: Chat interface via Telegram
- **Monitoring**: Homelab health monitoring with notifications
- **CLI Tool**: `friday` command for service management

### ✅ Development & Quality
- **71 Tests**: 41 unit + 30 integration tests (all passing)
- **Systemd Services**: Production-ready service management
- **Proper Logging**: Structured logging with rotation
- **Health Checks**: API health endpoints

---

## Feature Gaps & Pain Points

### 🔴 Critical Gaps

1. **No Proactive Intelligence**
   - Friday only reacts, doesn't proactively help
   - No contextual awareness of your day/schedule
   - Doesn't surface relevant information without being asked

2. **Limited Context Awareness**
   - Doesn't know what you're currently working on
   - No awareness of current location, weather impact on plans
   - Missing temporal context (morning vs evening behavior)

3. **No Task/Project Management**
   - Can't track todos, projects, or goals
   - No integration with actual task management tools
   - Reminders are basic (no recurring, no priorities)

4. **Memory Doesn't Learn**
   - Memories are static notes
   - No automatic memory formation from conversations
   - Doesn't build knowledge graph of relationships

5. **Limited Calendar Intelligence**
   - Can't create/modify events
   - No conflict detection
   - No travel time calculations
   - No meeting preparation

### 🟡 Medium Gaps

6. **No Email Integration**
   - Can't read/send emails
   - Missing important communication channel
   - No email-based reminders or summaries

7. **No Document Processing**
   - Can't summarize PDFs, documents
   - No OCR for images
   - No code analysis beyond vault

8. **Limited Health Insights**
   - Reactive only (answer questions)
   - No anomaly detection (unusual patterns)
   - No injury prevention warnings
   - No nutrition tracking

9. **No Multi-Modal Support**
   - Text only (no images, audio, video)
   - Can't analyze photos or voice notes
   - No image generation

10. **No Collaboration Features**
    - Single-user only
    - Can't share insights with wife/family
    - No delegation or task assignment

### 🟢 Nice-to-Have Gaps

11. **No Smart Home Integration**
    - Can't control lights, devices
    - No automation triggers

12. **No Financial Tracking**
    - No expense tracking
    - No budget insights

13. **No Learning Resources**
    - Can't suggest learning materials
    - No spaced repetition for memory

---

## High-Impact Feature Recommendations

### 🎯 Tier 1: Game Changers (Implement First)

#### 1. **Proactive Daily Briefing** 
**Impact**: ⭐⭐⭐⭐⭐
**Effort**: Medium

**What**: Context-aware morning briefing that adapts to your schedule
- Checks calendar → surfaces prep needed for meetings
- Checks weather → suggests workout timing
- Checks recovery → recommends activity level
- Checks recent notes → reminds you of ongoing work

**Implementation**:
```python
# New: morning_briefing.py
def generate_proactive_briefing():
    - Check calendar for day
    - For each event:
      - Search vault for related notes/context
      - Check if prep needed (meeting notes, documents)
    - Check weather impact on plans
    - Check health readiness
    - Suggest optimal schedule adjustments
```

**Example Output**:
```
☀️ Good morning! Today looks busy:

🏃 Your recovery is at 75/100 - good day for training
   → Consider morning run before weather turns

📅 Meetings today:
   • 10:00 AM: Sprint Planning
     → You have notes from last retro in "Work/Agile"
     → Action items to discuss: API refactoring
   
   • 2:00 PM: 1-on-1 with Julian  
     → He mentioned Dwarf Fortress interest
     → Follow up on AI project progress

🌤️ Weather: Rain after 3 PM
   → Run before 2 PM or skip outdoor workout

💡 Focus time: 11 AM - 1 PM clear for deep work
```

#### 2. **Automatic Memory Formation**
**Impact**: ⭐⭐⭐⭐⭐
**Effort**: Medium

**What**: Friday learns from conversations and automatically creates memories
- Extract facts, preferences, relationships from chat
- Build knowledge graph of people, projects, interests
- Auto-tag and categorize

**Implementation**:
```python
# After each conversation
async def extract_memories(conversation):
    - Use LLM to extract: facts, preferences, people, events
    - Check if new or updates existing memory
    - Auto-create Obsidian note with proper tags
    - Link to related notes
```

**Example**:
```
User: "I'm working on the new authentication system with Maria"
Friday: "Got it! I'll remember that."

[Auto-creates]:
- Person: Maria (colleague, working on auth)
- Project: Authentication System (active, high priority)
- Link: Maria ↔ Authentication System
```

#### 3. **Context-Aware Task Management**
**Impact**: ⭐⭐⭐⭐⭐
**Effort**: High

**What**: Smart task tracking that understands context
- Extract todos from conversations
- Priority inference from calendar/health
- Automatic time blocking suggestions
- Integration with calendar

**Implementation**:
```python
# New: task_manager.py
class SmartTask:
    - Deadline awareness
    - Energy level matching (high/low energy tasks)
    - Context tags (home/work/gym)
    - Auto-scheduling based on calendar gaps
    - Recurring task templates
```

**Example**:
```
User: "I need to finish the report by Friday"
Friday: "Added 'Finish report' (due Friday)
        Based on your calendar, I found:
        - Thursday 2-4 PM: 2hr focus block
        - Or today 4-6 PM if you prefer
        
        Should I block the time?"
```

#### 4. **Smart Event Creation & Management**
**Impact**: ⭐⭐⭐⭐
**Effort**: Medium

**What**: Create/modify calendar events naturally
- Parse natural language → calendar events
- Conflict detection and resolution
- Travel time calculation
- Meeting prep automation

**Implementation**:
```python
# Extend calendar_service.py
def create_event_from_natural_language(text):
    - Parse: date, time, duration, attendees, location
    - Check conflicts
    - Calculate travel time (if location)
    - Auto-create prep reminder (15 min before)
    - Search vault for related context
```

**Example**:
```
User: "Schedule coffee with Maria tomorrow at 10 AM at that café near work"
Friday: "✓ Created: Coffee with Maria
         Tomorrow 10:00 AM - 11:00 AM
         Location: Café Cultura (15 min from office)
         
         ⚠️ Conflict: Sprint Planning at 10:30
         Should I:
         1. Move coffee to 11:00 AM?
         2. Move sprint planning to 11:00 AM?
         3. Keep as is?"
```

### 🎯 Tier 2: Major Improvements

#### 5. **Email Intelligence**
**Impact**: ⭐⭐⭐⭐
**Effort**: High

**What**: Read, summarize, and respond to emails
- Morning email summary (important only)
- AI triage (urgent vs FYI)
- Draft responses
- Email-based reminders

**Implementation**:
```python
# New: email_service.py
- IMAP integration
- LLM-based importance scoring
- Auto-categorization
- Integration with memory (track conversations)
```

#### 6. **Workout Planning Intelligence**
**Impact**: ⭐⭐⭐⭐
**Effort**: Medium

**What**: Personalized training plans
- Suggest workouts based on recovery
- Adaptive training calendar
- Injury risk detection
- Progress tracking with visualizations

**Implementation**:
```python
# Extend health_coach.py
def generate_weekly_plan():
    - Analyze recent training load
    - Check recovery status
    - Consider calendar constraints
    - Generate adaptive plan
    - Adjust based on actual completion
```

#### 7. **Meeting Notes & Synthesis**
**Impact**: ⭐⭐⭐⭐
**Effort**: Medium

**What**: Automated meeting documentation
- Pre-meeting: Surface relevant context
- Post-meeting: Prompt for notes
- Auto-link to people/projects
- Action item extraction

**Implementation**:
```python
# New: meeting_assistant.py
def pre_meeting_prep(event):
    - Find related notes in vault
    - Summarize previous meetings with attendees
    - List open action items
    
def post_meeting_followup(event):
    - Remind to add notes
    - Extract action items from notes
    - Create reminders for follow-ups
```

#### 8. **Knowledge Graph Visualization**
**Impact**: ⭐⭐⭐⭐
**Effort**: High

**What**: Visual map of your knowledge
- People ↔ Projects ↔ Topics
- Discover connections
- Find knowledge gaps
- Suggest reading/learning

**Implementation**:
```python
# New: knowledge_graph.py
- Build graph from vault + memories
- Use graph DB (Neo4j or networkx)
- API endpoints for queries
- Web UI for visualization
```

### 🎯 Tier 3: Nice Enhancements

#### 9. **Voice Interface**
**Impact**: ⭐⭐⭐
**Effort**: Medium

**What**: Talk to Friday (especially useful for autism)
- Whisper for STT
- Coqui/Bark for TTS
- Hands-free interaction

#### 10. **Document Summarization**
**Impact**: ⭐⭐⭐
**Effort**: Low

**What**: Summarize PDFs, articles, long notes
- PyPDF2 for PDFs
- Readability for web pages
- Add summaries to vault

#### 11. **Spaced Repetition Learning**
**Impact**: ⭐⭐⭐
**Effort**: Medium

**What**: Help retain information
- Extract flashcards from notes
- Schedule reviews
- Track learning progress

#### 12. **Anomaly Detection**
**Impact**: ⭐⭐⭐
**Effort**: Medium

**What**: Alert on unusual patterns
- Sleep irregularities
- Training overreach
- Calendar anomalies (too many meetings)
- Stress indicators

---

## Implementation Priority

### Phase 1: Quick Wins (1-2 weeks)
1. ✅ Proactive Daily Briefing
2. ✅ Smart Event Creation
3. ✅ Document Summarization

### Phase 2: Core Features (2-4 weeks)
4. ✅ Automatic Memory Formation
5. ✅ Context-Aware Task Management
6. ✅ Meeting Notes Synthesis

### Phase 3: Advanced (1-2 months)
7. ✅ Email Intelligence
8. ✅ Workout Planning
9. ✅ Knowledge Graph

### Phase 4: Polish (Ongoing)
10. ✅ Voice Interface
11. ✅ Anomaly Detection
12. ✅ Spaced Repetition

---

## Technical Considerations

### Architecture Decisions

1. **Use Existing Patterns**
   - Intent router for new actions
   - Service layer for business logic
   - Integration tests for validation

2. **Data Storage**
   - Continue using Obsidian for human-readable data
   - Add SQLite for structured task/event data
   - Consider graph DB for knowledge graph

3. **External APIs**
   - Gmail API (email)
   - Google Calendar API (already have)
   - Weather API (already have)
   - Consider Todoist API for task sync

4. **Performance**
   - Background workers for heavy tasks
   - Cache frequently accessed data
   - Optimize LLM calls (smaller models for classification)

---

## Questions to Consider

1. **Privacy**: Are you comfortable with email access?
2. **Integrations**: Which task manager do you currently use?
3. **Voice**: Would you use voice interaction?
4. **Sharing**: Do you want to share any features with Camila?
5. **Automation**: How autonomous should Friday be in taking actions?

---

## Next Steps

**Which tier/features interest you most?** Let's prioritize based on your needs and implement the highest-impact features first!

**Quick Poll**:
- Most excited about: ____?
- Would use daily: ____?
- Skeptical about: ____?

