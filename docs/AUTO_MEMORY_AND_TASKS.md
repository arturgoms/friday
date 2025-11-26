# Automatic Memory Formation & Context-Aware Task Management

## Overview

Friday now automatically learns from your conversations and manages your tasks intelligently!

## Features Implemented

### 1. Automatic Memory Formation

**What it does:**
- Extracts facts, preferences, people, projects, and events from conversations
- Automatically creates Obsidian notes with proper tags and links
- Builds knowledge graph of relationships
- Only saves high-confidence extractions (no noise)

**Memory Types:**
- **Facts**: "I work at Counterpart", "My birthday is March 30"
- **Preferences**: "I prefer running in the morning", "I love pizza"
- **People**: "Maria (colleague)", "Julian (friend from work)"
- **Projects**: "Working on authentication system"
- **Events**: "Meeting tomorrow at 10 AM"

**Example:**
```
User: "I'm working on the new auth system with Maria from the backend team"

Friday: [Auto-creates two notes]
1. Person: Maria
   - Role: Backend team colleague
   - Projects: [[Authentication System]]
   
2. Project: Authentication System
   - Status: Active
   - Team: [[Maria]]
```

### 2. Context-Aware Task Management

**What it does:**
- Extracts tasks from natural conversation
- Understands priority from context
- Parses due dates naturally
- Stores in SQLite for fast queries
- Links tasks to projects and people

**Task Properties:**
- **Priority**: Low, Medium, High, Urgent (auto-inferred)
- **Context**: Home, Work, Gym, Errands
- **Energy Level**: Low, Medium, High (for matching to your state)
- **Estimated Time**: Duration in minutes
- **Due Date**: Parsed from natural language
- **Related**: Projects, people, tags

**Example:**
```
User: "I need to finish the auth report by Friday"

Friday: ✓ Created task
  Title: Finish auth report
  Priority: Medium
  Due: Friday 11:59 PM
  Tags: auto-extracted
  Related: [[Authentication System]]
```

## How It Works

### Architecture

```
User Message
     ↓
Chat Service
     ↓
Post-Chat Processor (runs after response)
     ├─→ Memory Extractor (LLM-based)
     │   ├─ Extract facts/people/projects
     │   ├─ Filter by confidence (>0.7)
     │   └─ Create Obsidian notes
     │
     └─→ Task Extractor (Pattern-based)
         ├─ Find task indicators
         ├─ Parse due dates
         ├─ Infer priority
         └─ Create in database
```

### Memory Extraction Process

1. **Analysis**: LLM analyzes conversation for memorable info
2. **Extraction**: Returns JSON with type, content, entities, confidence
3. **Filtering**: Only keeps high-confidence (≥0.7) extractions
4. **Formatting**: Creates Obsidian note with frontmatter
5. **Saving**: Writes to `data/memory/` with timestamp
6. **Indexing**: Adds to vector store for RAG

### Task Extraction Process

1. **Pattern Matching**: Looks for task indicators
   - "I need to...", "I have to...", "Finish..."
   - "Remind me to...", "TODO:", "Task:"
2. **Due Date Parsing**: Natural language → datetime
   - "by Friday", "tomorrow", "next week"
3. **Priority Inference**: Keywords → priority level
   - "urgent", "asap" → Urgent
   - "important", "critical" → High
4. **Creation**: Saves to SQLite database

## Files Created

```
src/app/services/
├── memory_extractor.py      # LLM-based memory extraction
├── task_manager.py           # SQLite-based task management
└── post_chat_processor.py   # Orchestrates both systems
```

## Database Schema

**Tasks Table:**
```sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    priority TEXT,           -- LOW, MEDIUM, HIGH, URGENT
    status TEXT,             -- todo, in_progress, blocked, done, cancelled
    context TEXT,            -- home, work, gym, errands, any
    energy_level TEXT,       -- LOW, MEDIUM, HIGH
    estimated_minutes INTEGER,
    due_date TEXT,
    scheduled_for TEXT,
    tags TEXT,               -- JSON array
    related_project TEXT,
    related_people TEXT,     -- JSON array
    created_at TEXT,
    completed_at TEXT
)
```

## API Endpoints (Coming Soon)

```bash
# List tasks
GET /tasks?status=todo&context=work

# Create task
POST /tasks
{
  "title": "Finish report",
  "priority": "HIGH",
  "due_date": "2025-11-30",
  "context": "work"
}

# Update task status
PATCH /tasks/{id}
{
  "status": "done"
}

# Get today's tasks
GET /tasks/today

# List memories
GET /memories?type=person

# Search memories
GET /memories/search?q=authentication
```

## Configuration

**Enable/Disable Auto-Extraction:**
```python
# In chat request
{
  "message": "...",
  "save_memory": true,  # Enable auto-memory (default)
  "extract_tasks": true  # Enable auto-tasks (default)
}
```

**Confidence Threshold:**
```python
# In memory_extractor.py
def should_save_extraction(extraction):
    return extraction.confidence >= 0.7  # Adjust threshold
```

## Usage Examples

### Memory Formation

```
You: "My colleague Julian loves Dwarf Fortress"
Friday: "That's interesting about Julian!"
[Auto-creates note: Julian (colleague, enjoys Dwarf Fortress)]

You: "I'm learning Rust for the backend rewrite"
Friday: "Rust is great for backend work!"
[Auto-creates: Project: Backend Rewrite (language: Rust)]
```

### Task Management

```
You: "Remind me to call mom tomorrow"
Friday: "I'll remind you!"
[Creates task: "Call mom" due tomorrow]

You: "I must finish this urgent report by Friday"
Friday: "Got it, I'll help track that."
[Creates task: "Finish urgent report" - Priority: URGENT, Due: Friday]
```

## Benefits

### For Memory:
- **No manual note-taking**: Friday learns automatically
- **Consistent structure**: All notes follow same format
- **Linked knowledge**: Entities are connected via wiki-links
- **Searchable**: Indexed in vector store for RAG
- **Timestamped**: Know when you learned something

### For Tasks:
- **Natural creation**: No special syntax needed
- **Smart prioritization**: Auto-infers importance
- **Context-aware**: Match tasks to your situation
- **Energy-based**: Do high-energy tasks when fresh
- **Calendar integration**: (Coming soon) Auto-schedule

## Next Steps

### Phase 1 (Current):
- ✅ Memory extraction working
- ✅ Task extraction working
- ✅ Database storage
- ✅ Obsidian integration

### Phase 2 (In Progress):
- [ ] API endpoints for tasks
- [ ] Task list in morning report
- [ ] Calendar integration (auto-scheduling)
- [ ] Task completion tracking

### Phase 3 (Future):
- [ ] Knowledge graph visualization
- [ ] Smart task suggestions
- [ ] Recurring tasks
- [ ] Task dependencies
- [ ] Time blocking
- [ ] Progress analytics

## Testing

Run tests for new features:
```bash
pytest tests/unit/test_memory_extractor.py -v
pytest tests/unit/test_task_manager.py -v
pytest tests/integration/test_auto_extraction.py -v
```

## Privacy Note

- All data stored locally
- No external APIs for extraction
- Uses your own LLM instance
- Complete control over what's saved

---

**Status**: Implemented, ready for integration testing
**Next**: Integrate into chat service and add API endpoints
