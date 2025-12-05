# Awareness Engine Design Document

## 1. Overview

This document outlines the design for the **Awareness Engine**, a major upgrade to Friday's proactive monitoring capabilities. The goal is to evolve the existing `ProactiveMonitor` into a more sophisticated system that can synthesize information from multiple domains (health, calendar, notes, tasks) to provide highly contextual and actionable insights.

The Awareness Engine will make Friday a more intelligent and proactive partner, capable of anticipating needs and offering timely advice based on a deep understanding of the user's life patterns.

## 2. Core Principles

-   **Contextual Fusion**: The engine will combine data from different sources to generate insights that are more than the sum of their parts.
-   **Pattern Recognition**: It will identify and learn the user's habits and routines to provide personalized and relevant alerts.
-   **Actionable Recommendations**: Alerts will be paired with concrete, helpful suggestions.
-   **User-Centric**: The engine will always prioritize the user's well-being and avoid being intrusive, building on the principles of the `ReachOutBudget`.

## 3. Proposed Architecture

The `ProactiveMonitor` will be refactored into the `AwarenessEngine`. This new class will orchestrate a series of "fusion checks," each designed to analyze the interplay between different data sources.

### 3.1. Fusion Checks

We will implement a series of new methods within the `AwarenessEngine`, each responsible for a specific cross-domain analysis:

#### a. Health + Calendar Fusion

-   **`check_workout_readiness()`**: Before a calendar event that looks like a workout (e.g., "Leg Day," "Gym"), this check will query the `HealthCoach` for Training Readiness and Body Battery. If metrics are low, it will suggest rescheduling or a lighter alternative.
-   **`check_post_workout_recovery()`**: After a workout, it will monitor recovery time and suggest optimal times for the next session.

#### b. Notes + Calendar Fusion

-   **`check_meeting_preparedness()`**: For upcoming meetings, this check will search Obsidian notes for the names of attendees. It will then generate a brief summary of past discussions and key points to help with preparation.

#### c. Tasks + Location/Calendar Fusion

-   **`check_errand_opportunities()`**: This check will be triggered by calendar events that involve leaving the house (e.g., "Appointment at dentist"). It will then scan the task list for errands and suggest completing them if they are geographically convenient.

### 3.2. Behavioral Pattern Recognition

The engine will maintain a simple, persistent state to track patterns over time.

-   **`track_sleep_consistency()`**: This will monitor bedtime and wake-up times, alerting the user to significant deviations from their baseline.
-   **`track_workout_frequency()`**: It will learn the user's typical workout cadence and provide gentle reminders if a pattern is broken.

## 4. Implementation Steps

1.  **Rename and Refactor**:
    -   Rename `proactive_monitor.py` to `awareness_engine.py`.
    -   Rename the `ProactiveMonitor` class to `AwarenessEngine`.

2.  **Implement Fusion Checks**:
    -   Add the new fusion check methods to the `AwarenessEngine` class.
    -   These methods will require access to the `HealthCoach`, `UnifiedCalendarService`, `ObsidianService`, and `TaskManager`.

3.  **Develop Pattern Recognition**:
    -   Create a simple JSON-based store to persist pattern data (e.g., average bedtime, weekly workout count).
    -   Implement the pattern tracking methods.

4.  **Integrate into Main Loop**:
    -   Update the `run_all_checks` method to include the new fusion and pattern checks.

5.  **Refine Alert Messages**:
    -   Craft new, more insightful alert messages that reflect the deeper context available to the engine.

6.  **Model Evaluation & Selection**:
    -   **Establish Benchmark**: Create a set of test cases that cover the key capabilities of the Awareness Engine (e.g., complex reasoning, instruction following, contextual understanding).
    -   **Comparative Testing**: Run these benchmarks on both the current `Qwen2.5-14B` and other potential models like `Llama-3-8B-Instruct`.
    -   **Selection**: Based on the results, make an informed decision on which model to use for the long term.


### 3.3. System & Infrastructure Monitoring

Friday must be aware of its own health and the infrastructure it relies on. The Awareness Engine will take on the role of a vigilant sysadmin for your homelab.

#### a. Friday's Own Health

-   **`check_service_heartbeat()`**: This will monitor the status of Friday's core services (e.g., `telegram_bot.py`, `vllm.service`). If a service becomes unresponsive, it will trigger an alert.
-   **`check_error_rate()`**: It will track the rate of errors in the logs. A sudden spike in errors will generate an alert, helping to catch bugs early.

#### b. Infrastructure Health

-   **`check_server_metrics()`**: Leveraging the existing `homelab-monitor.service` and its InfluxDB integration, this will monitor key server metrics like CPU temperature, memory usage, and disk space.
-   **`check_nas_status()`**: It will check the health of your NAS, alerting you to any disk failures or other issues.
-   **`check_self_hosted_services()`**: It will perform regular health checks on your other self-hosted services to ensure they are running correctly.

### 3.4. Anticipatory Intelligence

The engine must not only be aware of the present but also anticipate future needs and potential problems. This moves Friday from a reactive assistant to a strategic advisor.

#### a. Predictive Infrastructure Monitoring

-   **`predict_resource_exhaustion()`**: Instead of just reporting low disk space, the engine will analyze usage trends to predict *when* resources will become critical (e.g., "Warning: At the current rate, the main disk will be full in approximately 7 days").

#### b. Proactive Meeting Preparation

-   **`generate_meeting_briefing()`**: The engine will identify "important" upcoming meetings based on attendees or keywords. Days in advance, it will create a "briefing document" by pulling relevant notes and past decisions, and then prompt the user to prepare.

#### c. Memory Validation & Enrichment

-   **`validate_and_enrich_memories()`**: The engine will periodically review memories for important but unverified facts. It will then proactively seek to confirm this information, either by cross-referencing other notes, searching the web, or asking the user for clarification.

#### d. Personalized News & Opportunity Monitoring

-   **`generate_intelligence_briefing()`**: The engine will monitor external news sources for topics relevant to the user's interests and career. It will alert the user to significant events that might affect them, turning raw information into personalized intelligence.

This new architecture will transform Friday from a system that simply reports data to one that truly understands and anticipates the user's needs.

