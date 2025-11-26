# Two-Stage LLM Architecture

## Problem
The original single-LLM architecture suffered from "tool instruction pollution":
- System prompt included instructions for ALL tools (time, calendar, reminders)  
- LLM would hallucinate tool tags for unrelated queries
- Example: "when is stranger things?" → `<REMINDER_LIST/>` (wrong!)

## Solution: Two-Stage Architecture

### Stage 1: Intent Router (Planning LLM)
**Purpose:** Analyze user query and determine what to do

**Input:** User message
**Output:** JSON intent object
```json
{
  "action": "web_search" | "health_query" | "time_query" | "calendar_query" | "reminder_query" | "reminder_create" | "general",
  "use_rag": true/false,
  "use_memory": true/false,
  "tool": "current_time" | "calendar_today" | etc. | null
}
```

**Benefits:**
- Focused task: classification only
- No confusion about how to respond
- Easy to debug (see exactly what was decided)

### Stage 2: Response Generator (Clean LLM)
**Purpose:** Generate the actual response using fetched data

**Input:** 
- User message
- Context (from RAG/web/health/etc based on intent)
- Clean system prompt (NO tool instructions)

**Output:** Natural language response

**Benefits:**
- No tool instruction pollution
- Focused on response generation only
- Better quality responses

## Architecture Flow

```
User: "when is stranger things season 5?"
    ↓
┌───────────────────────────────────────────┐
│  STAGE 1: Intent Router                   │
│  ├─ Analyzes query                        │
│  └─ Returns: {"action": "web_search"}     │
└───────────────────────────────────────────┘
    ↓
┌───────────────────────────────────────────┐
│  STAGE 2: Context Fetcher                 │
│  ├─ Calls web_search_service.search()    │
│  └─ Returns web results                   │
└───────────────────────────────────────────┘
    ↓
┌───────────────────────────────────────────┐
│  STAGE 3: Response Generator              │
│  ├─ System: "Use web results to answer"  │
│  ├─ User: "Question + Web results"        │
│  └─ Generates clean answer                │
└───────────────────────────────────────────┘
    ↓
Answer: "Stranger Things Season 5 is releasing..."
```

## Implementation

### Files Created:
- `src/app/services/intent/router.py` - Intent Router LLM
- `src/app/services/chat_v2.py` - New two-stage chat service

### Files Modified:
- `src/app/api/routes.py` - Updated to use `chat_service_v2`

### Files Backed Up:
- `src/app/services/chat_old.py` - Original single-stage service

## Advantages

1. **Separation of Concerns**
   - Intent detection isolated from response generation
   - Each LLM has one clear job

2. **No Tool Pollution**
   - Response LLM never sees tool instructions
   - Cleaner, more focused prompts

3. **Better Reliability**
   - Intent router is simpler, more predictable
   - Easier to debug when things go wrong

4. **Extensibility**
   - Easy to add new actions/tools
   - Just update intent router logic

5. **Performance**
   - Can optimize each stage independently
   - Intent router could be smaller/faster model

## Testing

```bash
# Test web search (should NOT return reminders)
curl -H "X-API-Key: $KEY" http://localhost:8080/chat -X POST -d '{
  "message": "when is stranger things season 5?",
  "use_web": true
}'

# Test health query
curl -H "X-API-Key: $KEY" http://localhost:8080/chat -X POST -d '{
  "message": "when was my latest pilates session?"
}'

# Test tool query
curl -H "X-API-Key: $KEY" http://localhost:8080/chat -X POST -d '{
  "message": "what time is it?"
}'
```

## Rollback

If issues arise, revert to old service:
```python
# In src/app/api/routes.py
from app.services.chat import chat_service  # Old service
```

## Date Implemented
2025-11-24
