# Feedback & Learning System Design Document

## 1. Overview

The current feedback system collects thumbs up/down ratings and alert acknowledgments, but it doesn't actively use this data to improve Friday's behavior. This document outlines a plan to evolve the feedback system into a true learning loop, enabling Friday to adapt to user preferences and self-correct over time.

The goal is to make Friday an AI that genuinely learns from its mistakes and becomes more helpful with every interaction.

## 2. Current State

### 2.1. What We Have

-   **`FeedbackStore`**: SQLite database storing feedback with context (user message, AI response, intent, thumbs up/down).
-   **Telegram Integration**: 👍/👎 buttons on responses, "Acknowledge" button on proactive alerts.
-   **`ReachOutBudget`**: Self-regulation system that reduces proactive messages when the user is ignoring them.
-   **Feedback Stats**: Basic statistics on approval rates by intent and context type.

### 2.2. Limitations

-   Feedback is stored but not acted upon.
-   No mechanism to understand *why* a response was bad.
-   No automatic adjustment of behavior based on feedback patterns.
-   Alert acknowledgments don't influence future alert quality.

## 3. Proposed Architecture

### 3.1. Correction Flow

When the user gives negative feedback (👎), the system will initiate a correction flow:

1.  **Prompt for Correction**: After a 👎, Friday will reply: "Thanks for the feedback. What should I have done differently?"
2.  **Store Correction**: The user's text response will be stored in a new `corrections` table, linked to the original feedback record.
3.  **Graceful Fallback**: If the user doesn't respond within a reasonable time or sends a new unrelated message, the correction flow will be abandoned.

**Database Schema Addition:**

```sql
CREATE TABLE corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feedback_id INTEGER NOT NULL,
    correction_text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    processed BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (feedback_id) REFERENCES feedback(id)
);
```

### 3.2. Correction Synthesis Service

A new service, `LearningService`, will be responsible for analyzing feedback and corrections to generate actionable insights.

**Key Functions:**

-   **`synthesize_learnings()`**: Periodically (e.g., weekly or on-demand) analyzes all unprocessed corrections. Uses the LLM to identify patterns and generate "learning statements."
-   **`generate_prompt_adjustments()`**: Based on the learning statements, generates suggestions for adjusting Friday's system prompts.
-   **`apply_learnings()`**: Stores the new learnings in a persistent `learnings` store (e.g., a JSON or Markdown file in the Brain).

**Example Learning Statement:**

```json
{
  "id": "learning_001",
  "created_at": "2025-12-05T10:00:00",
  "source_corrections": [12, 15, 18],
  "pattern": "User prefers concise answers",
  "prompt_adjustment": "Keep responses brief and to the point. Avoid lengthy explanations unless the user explicitly asks for more detail.",
  "confidence": 0.85
}
```

### 3.3. Dynamic System Prompt

Friday's system prompts will be refactored to include a dynamic section that is populated from the `learnings` store.

**Example:**

```python
def get_system_prompt():
    base_prompt = "You are Friday, a personal AI assistant..."
    
    # Load dynamic learnings
    learnings = load_learnings()
    learnings_section = "\n".join([
        f"- {l['prompt_adjustment']}" for l in learnings if l['confidence'] > 0.7
    ])
    
    if learnings_section:
        base_prompt += f"\n\n**User Preferences (Learned):**\n{learnings_section}"
    
    return base_prompt
```

### 3.4. Enhanced Alert Feedback

The `ReachOutBudget` will be enhanced to incorporate feedback on proactive alerts.

**New Metrics:**

-   **`alert_thumbs_up`**: Count of proactive alerts that received positive feedback.
-   **`alert_thumbs_down`**: Count of proactive alerts that received negative feedback.
-   **`alert_quality_score`**: A rolling score based on feedback, used to adjust the budget.

**Logic:**

-   High `alert_quality_score` -> Increase daily budget slightly.
-   Low `alert_quality_score` -> Decrease daily budget.
-   Specific alert *types* with consistently negative feedback will be deprioritized or disabled.

## 4. Implementation Steps

1.  **Update `FeedbackStore`**:
    -   Add `corrections` table.
    -   Add methods: `add_correction()`, `get_unprocessed_corrections()`, `mark_corrections_processed()`.

2.  **Update `telegram_bot.py`**:
    -   Modify `handle_feedback_callback` to initiate the correction flow on 👎.
    -   Add a new handler to capture the correction text.
    -   Add feedback buttons (👍/👎) to proactive alerts in addition to the "Ack" button.

3.  **Create `LearningService`**:
    -   Implement `synthesize_learnings()`.
    -   Implement `generate_prompt_adjustments()`.
    -   Implement `apply_learnings()`.
    -   Create a persistent store for learnings (`data/learnings.json` or `Brain/5. Friday/5.6 Learnings/`).

4.  **Update `ChatService` / `ChatOrchestrator`**:
    -   Refactor system prompt generation to include dynamic learnings.

5.  **Enhance `ReachOutBudget`**:
    -   Add alert feedback tracking.
    -   Implement `alert_quality_score` calculation.
    -   Adjust budget logic based on the new score.

## 5. User Experience

### 5.1. Correction Flow Example

```
User: What's on my calendar tomorrow?
Friday: [Incorrect or unhelpful response]
User: 👎
Friday: Thanks for the feedback. What should I have done differently?
User: You forgot to mention my dentist appointment.
Friday: Got it! I'll make sure to include all appointments next time. Thanks for helping me improve!
```

### 5.2. Learning Application Example

After several corrections about missing calendar events, the `LearningService` synthesizes:

```
Learning: User wants all calendar events mentioned, even minor ones.
Prompt Adjustment: "When asked about calendar events, list ALL events for the requested period, including minor appointments."
```

This adjustment is automatically applied to Friday's system prompt, improving future responses.

## 6. Privacy and Control

-   All learnings will be stored locally on the user's server.
-   A new command, `/learnings`, will allow the user to view, edit, or delete any learned behaviors.
-   The user can manually add learnings (e.g., "I prefer formal language").

This system will make Friday a truly adaptive assistant that gets better with every interaction.

## 7. Testing Strategy

The learning system is sensitive—bad learnings could degrade Friday's performance. Testing must ensure the system learns correctly and safely.

### 7.1. Unit Tests

Create new test files in `tests/unit/`:

-   **`test_feedback_store.py`**: Test the feedback and corrections storage.
    -   Test adding feedback records.
    -   Test adding corrections linked to feedback.
    -   Test retrieval of unprocessed corrections.
    -   Test marking corrections as processed.
-   **`test_learning_service.py`**: Test the learning synthesis system.
    -   Test pattern detection from corrections.
    -   Test learning statement generation.
    -   Test confidence scoring.
    -   Test prompt adjustment generation.
-   **`test_dynamic_prompts.py`**: Test dynamic system prompt generation.
    -   Test that learnings are correctly injected into prompts.
    -   Test filtering by confidence threshold.
    -   Test handling of empty learnings store.

### 7.2. Integration Tests

Create/update test files in `tests/integration/`:

-   **`test_feedback_integration.py`**: End-to-end tests for the feedback flow.
    -   Test full correction flow (👎 -> prompt -> correction -> storage).
    -   Test learning synthesis with real LLM.
    -   Test that applied learnings affect future responses.

### 7.3. Safety Tests

Special tests to ensure the learning system doesn't cause harm:

```python
@pytest.mark.safety
def test_learning_does_not_override_core_behavior():
    """Ensure learnings can't override critical system instructions."""
    ...

@pytest.mark.safety
def test_low_confidence_learnings_not_applied():
    """Ensure learnings below threshold are not used."""
    ...

@pytest.mark.safety
def test_conflicting_learnings_handled():
    """Ensure conflicting learnings are detected and resolved."""
    ...
```

## 8. CLI (`friday` script) Updates

The `friday` CLI will be extended to provide full control over the feedback and learning system.

### 8.1. New Commands

```bash
# Show feedback statistics
friday feedback stats
# Output:
#   Last 30 days:
#   - Total responses rated: 150
#   - Thumbs up: 120 (80%)
#   - Thumbs down: 30 (20%)
#   
#   By Intent:
#   - calendar_query: 95% approval
#   - memory_save: 85% approval
#   - health_query: 70% approval

# List recent negative feedback
friday feedback negative
# Output: Lists recent thumbs-down with user messages and AI responses

# List pending corrections (not yet processed)
friday feedback corrections
# Output: Lists corrections awaiting synthesis

# Run learning synthesis manually
friday learn synthesize
# Output:
#   Analyzing 15 unprocessed corrections...
#   Generated 3 new learnings:
#   - [0.85] User prefers concise answers
#   - [0.72] Always include event times
#   - [0.68] Mention source of health data (below threshold, not applied)

# List all active learnings
friday learn list
# Output:
#   ID          Confidence  Pattern
#   learn_001   0.85        User prefers concise answers
#   learn_002   0.72        Always include event times

# Show details of a specific learning
friday learn show <learning_id>

# Manually add a learning
friday learn add "Always respond in Portuguese when I write in Portuguese"

# Remove a learning
friday learn remove <learning_id>

# Temporarily disable all learnings (for debugging)
friday learn disable
friday learn enable
```

### 8.2. Implementation

Add new cases to the `friday` script:

```bash
feedback)
    ACTION="${2:-stats}"
    case "$ACTION" in
        stats)
            # Show feedback statistics
            ;;
        negative)
            # List recent negative feedback
            ;;
        corrections)
            # List pending corrections
            ;;
        *)
            echo "Usage: friday feedback [stats|negative|corrections]"
            ;;
    esac
    ;;

learn)
    ACTION="${2:-list}"
    case "$ACTION" in
        synthesize)
            # Run learning synthesis
            ;;
        list)
            # List active learnings
            ;;
        show)
            LEARNING_ID="$3"
            # Show learning details
            ;;
        add)
            shift 2
            LEARNING="$*"
            # Add manual learning
            ;;
        remove)
            LEARNING_ID="$3"
            # Remove learning
            ;;
        disable|enable)
            # Toggle learnings
            ;;
        *)
            echo "Usage: friday learn [synthesize|list|show|add|remove|disable|enable]"
            ;;
    esac
    ;;
```
