# Bug Fix: Reminders/Health Data Leaking into Memory

## Issue
Ephemeral data (reminders, health queries, time queries) was being incorrectly extracted and saved as "permanent memories", causing the LLM to return stale/incorrect information.

### Example
1. User sets reminder: "remind me about pilates at 16:50"
2. User asks: "when was my latest pilates session?"
3. Assistant responds with Garmin data: "Your latest Pilates session was at 16:50 PM today"
4. Memory extraction LLM incorrectly identifies this as a "permanent fact"
5. Memory saved: "Latest Pilates session was at 16:50 PM today"
6. Future queries return wrong information from memory

## Root Cause
The `extract_memory()` function had two problems:

1. **Insufficient skip keywords**: Didn't skip health/activity queries
2. **LLM misclassification**: The extraction LLM couldn't distinguish between:
   - Permanent facts: "I work at Google", "My favorite color is blue"
   - Ephemeral states: "Latest session was today", "Current time is 3pm"

## Fix Applied

### 1. Expanded Skip Keywords (Line 472-483)
Added keywords to skip memory extraction:
- Health: `pilates`, `run`, `workout`, `sleep`, `activity`, `session`
- Time queries: `latest`, `last`, `recent`, `when was`, `how many`, `how much`
- Calendar: `calendar`, `event`, `meeting`, `appointment`, `schedule`

### 2. Improved Extraction Prompt (Line 488-501)
Made the LLM extraction more explicit about what NOT to extract:
- Time-based queries (when was, latest, last, recent)
- Health/activity data (changes daily)
- Questions being asked (only extract statements)
- Answers to queries about current state

### 3. Post-Extraction Validation (Line 518-527)
Added defensive check to reject extractions containing:
- Time indicators: `pm`, `am`, `:`, `o'clock`, `minutes`, `hours`
- Temporal words: `latest`, `last`, `recent`, `today`, `yesterday`, `tomorrow`
- Activity words: `session`, `was at`, `was on`
- Calendar words: `event`, `meeting`, `appointment`

### 4. Enhanced Logging (Line 470, 477, 617, 620)
Added debug logging to trace memory extraction:
- Log when skip keywords match
- Log when post-validation rejects
- Log when memory is successfully extracted
- Log when no memory is extracted

## Testing
```bash
# Test that health queries don't create memories
curl -H "X-API-Key: $KEY" http://localhost:8080/chat -X POST -d '{
  "message": "when was my latest pilates session?",
  "use_memory": false,
  "save_memory": true
}'

# Check logs - should see: "Skipped memory extraction (matched keywords: ['latest', 'pilates', 'session'])"
tail -f /home/artur/friday/logs/friday.log | grep "memory extraction"
```

## Prevention
This bug is now prevented by **three layers of defense**:
1. Pre-extraction skip keywords (fastest, catches most cases)
2. LLM extraction prompt (handles edge cases)
3. Post-extraction validation (safety net)

## Related Files
- `src/app/services/chat.py` - Lines 470-527, 614-620
- `data/chroma_db/` - Cleaned up bad memories
- `logs/friday.log` - Now logs memory extraction decisions

## Date Fixed
2025-11-24
