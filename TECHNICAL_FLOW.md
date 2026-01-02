# Friday 3.0 - Technical Message Flow Documentation

This document explains when and how Friday sends messages, how sensors and collectors work, and the complete data flow through the system.

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Main Insights Loop](#main-insights-loop)
3. [Data Collection Flow](#data-collection-flow)
4. [Analysis & Insight Generation](#analysis--insight-generation)
5. [Decision Engine](#decision-engine)
6. [Message Delivery](#message-delivery)
7. [Scheduled Reports](#scheduled-reports)
8. [Code Examples](#code-examples)

---

## System Architecture

Friday consists of 4 services running independently:

```
┌─────────────────┐
│  friday-vllm    │  Port 8000 - Local LLM inference
└─────────────────┘

┌─────────────────┐
│  friday-core    │  Port 8080 - FastAPI brain (chat, tools, RAG)
└─────────────────┘

┌─────────────────┐
│friday-awareness │  Insights engine (this doc focuses here)
└─────────────────┘

┌─────────────────┐
│friday-telegram  │  Telegram bot interface
└─────────────────┘
```

**Awareness Service** is the autonomous monitoring and notification system that:
- Collects data from various sources (health, calendar, homelab)
- Analyzes data to generate insights
- Decides when and how to notify you
- Sends scheduled reports (morning, evening, weekly)

---

## Main Insights Loop

**File**: `src/insights/engine.py`

The engine runs a continuous loop every **10 seconds**:

```python
async def run(self, check_interval: float = 10.0):
    """Run the insights engine main loop."""
    self._running = True
    
    while self._running:
        try:
            # 1. Run collectors that are due
            collected_data = await self._run_collectors()
            
            # 2. Run analyzers if we have data
            if collected_data:
                insights = self._run_analyzers(collected_data)
                
                # 3. Process and deliver insights
                if insights:
                    self.delivery.process_insights(insights)
            
            # 4. Run periodic analyzers
            periodic_insights = self._run_periodic_analyzers()
            if periodic_insights:
                self.delivery.process_insights(periodic_insights)
            
            # 5. Check scheduled reports
            await self._check_scheduled_reports()
            
        except Exception as e:
            logger.error(f"Error in main cycle: {e}")
        
        await asyncio.sleep(check_interval)
```

### Cycle Breakdown

Every 10 seconds, the engine:
1. ✅ **Checks** if any collectors need to run (based on their intervals)
2. ✅ **Collects** data if interval has elapsed
3. ✅ **Saves** snapshot to database for historical analysis
4. ✅ **Runs** real-time analyzers on fresh data
5. ✅ **Runs** periodic analyzers (less frequently)
6. ✅ **Decides** what to do with each insight
7. ✅ **Delivers** insights via Telegram if approved
8. ✅ **Checks** if it's time for scheduled reports

---

## Data Collection Flow

### Collectors

**File**: `src/insights/collectors/`

Each collector gathers data from a specific source:

| Collector | Source | Interval | Data |
|-----------|--------|----------|------|
| **HealthCollector** | InfluxDB (Garmin data) | 5 min | Heart rate, sleep, stress, body battery, steps |
| **CalendarCollector** | Google Calendar + Nextcloud | 5 min | Events, meetings, conflicts |
| **HomelabCollector** | Service URLs + Glances API | 5 min | Service status (17 services), hardware stats |
| **WeatherCollector** | OpenWeatherMap API | 30 min | Current weather, forecast |

### Collection Logic

**File**: `src/insights/engine.py:177`

```python
async def _run_collectors(self) -> Dict[str, Any]:
    """Run collectors that are due based on their intervals."""
    now = time_module.time()
    collected_data = {}
    
    for name, collector in self._collectors.items():
        # Check if enabled
        coll_config = self.config.collectors.get(name)
        if coll_config and not coll_config.enabled:
            continue
        
        # Get interval from config
        interval = coll_config.interval_seconds if coll_config else 300
        
        # Check if due (time since last run >= interval)
        last_run = self._last_collection.get(name, 0)
        if now - last_run >= interval:
            try:
                # Collect data
                data = collector.collect()
                if data:
                    collected_data[name] = data
                    
                    # Save snapshot for historical analysis
                    snapshot = Snapshot(
                        collector=name,
                        timestamp=datetime.now(BRT),
                        data=data
                    )
                    self.store.save_snapshot(snapshot)
                    
                self._last_collection[name] = now
                logger.debug(f"Collected from {name}")
                
            except Exception as e:
                logger.error(f"Collector {name} error: {e}")
    
    return collected_data
```

### Example: Health Collector

**File**: `src/insights/collectors/health.py:48`

```python
def collect(self) -> Optional[Dict[str, Any]]:
    """Collect current health metrics."""
    if not self._initialized:
        if not self.initialize():
            return None
    
    now = datetime.now(BRT)
    today_str = now.strftime("%Y-%m-%d")
    
    data = {
        "collected_at": now.isoformat(),
        "sync_status": self._get_sync_status(),      # Check if Garmin data is fresh
        "stress": self._get_stress(),                # Current stress level
        "body_battery": self._get_body_battery(),    # Current energy level
        "heart_rate": self._get_heart_rate(),        # Current HR
        "sleep": self._get_sleep(),                  # Last night's sleep
        "training_readiness": self._get_training_readiness(),
        "daily_stats": self._get_daily_stats(today_str),  # Steps, calories
    }
    
    return data

def _get_sync_status(self) -> Dict[str, Any]:
    """Check Garmin sync freshness."""
    points = self._query('SELECT last("HeartRate") FROM "HeartRateIntraday"')
    
    if not points:
        return {"status": "unknown", "hours_ago": None}
    
    last_time_str = points[0].get("time", "")
    if not last_time_str:
        return {"status": "unknown", "hours_ago": None}
    
    # Calculate time since last sync
    last_time = datetime.fromisoformat(last_time_str.replace("Z", "+00:00"))
    now_utc = datetime.now(timezone.utc)
    hours_ago = (now_utc - last_time).total_seconds() / 3600
    
    # Determine freshness status
    if hours_ago < 1:
        status = "current"     # Very fresh (< 1h)
    elif hours_ago < 6:
        status = "recent"      # Fresh enough (1-6h)
    elif hours_ago < 12:
        status = "stale"       # Getting old (6-12h)
    else:
        status = "very_stale"  # Too old (>12h)
    
    return {
        "status": status,
        "hours_ago": hours_ago,
        "last_sync": last_time.isoformat()
    }
```

### Snapshot Storage

Every time a collector runs, its data is saved as a **Snapshot** to SQLite:

```python
snapshot = Snapshot(
    collector="health",
    timestamp=datetime.now(BRT),
    data={
        "stress": {"current": 30, "average": 35},
        "body_battery": {"current": 84},
        "sleep": {"score": 83, "total_hours": 8.3},
        ...
    }
)
self.store.save_snapshot(snapshot)
```

Snapshots enable:
- ✅ Historical analysis (trends over time)
- ✅ Correlation detection (sleep vs stress)
- ✅ Weekly/monthly reports
- ✅ Pattern recognition

Retention: **30 days** (configurable in `config/insights.json`)

---

## Analysis & Insight Generation

### Analyzer Types

**File**: `src/insights/analyzers/`

Three types of analyzers:

#### 1. Real-Time Analyzers (Run Every Cycle)

Run on every collection cycle when new data arrives:

| Analyzer | Purpose | Triggers On |
|----------|---------|-------------|
| **ThresholdAnalyzer** | Check if metrics exceed thresholds | Health, homelab metrics |
| **StressAnalyzer** | Monitor sustained high stress | Stress > 70 for 2+ hours |
| **CalendarAnalyzer** | Check for meeting conflicts | Calendar data |

#### 2. Periodic Analyzers (Run on Schedule)

Run less frequently, analyze historical data:

| Analyzer | Frequency | Purpose |
|----------|-----------|---------|
| **SleepCorrelationAnalyzer** | Daily | Correlate sleep quality with stress |
| **ResourceTrendAnalyzer** | Hourly | Detect homelab resource trends |

#### 3. Scheduled Analyzers (Run at Specific Times)

Run at exact times for specific tasks:

| Analyzer | Schedule | Purpose |
|----------|----------|---------|
| **DailyJournalAnalyzer** | 23:59 daily | Generate daily note from journal entries |

### Example: Threshold Analyzer

**File**: `src/insights/analyzers/thresholds.py`

```python
class ThresholdAnalyzer(RealTimeAnalyzer):
    """Check if metrics exceed configured thresholds."""
    
    def analyze(self, data: dict) -> list[Insight]:
        """Analyze collected data against thresholds."""
        insights = []
        
        # Check health thresholds
        if "health" in data:
            health = data["health"]
            
            # Stress threshold
            stress = health.get("stress", {}).get("current")
            if stress and stress > self.config.threshold_stress:
                insights.append(Insight(
                    title="High Stress Detected",
                    message=f"Your stress level is {stress} (threshold: {self.config.threshold_stress})",
                    priority=Priority.HIGH,
                    category=Category.HEALTH,
                    dedupe_key=f"stress_high_{datetime.now(BRT).strftime('%Y-%m-%d-%H')}",
                    expires_at=datetime.now(BRT) + timedelta(hours=2)
                ))
            
            # Body battery threshold
            bb = health.get("body_battery", {}).get("current")
            if bb and bb < self.config.threshold_body_battery:
                insights.append(Insight(
                    title="Low Body Battery",
                    message=f"Your body battery is at {bb}% - consider resting",
                    priority=Priority.MEDIUM,
                    category=Category.HEALTH,
                    dedupe_key=f"bb_low_{datetime.now(BRT).strftime('%Y-%m-%d-%H')}",
                ))
        
        # Check homelab thresholds
        if "homelab" in data:
            homelab = data["homelab"]
            services = homelab.get("services", {})
            down_services = services.get("down_services", [])
            
            if down_services:
                insights.append(Insight(
                    title=f"Services Down: {len(down_services)}",
                    message=f"Services offline: {', '.join(down_services)}",
                    priority=Priority.HIGH if len(down_services) > 2 else Priority.MEDIUM,
                    category=Category.SYSTEM,
                    dedupe_key=f"services_down_{'_'.join(sorted(down_services))}",
                    data={"down_services": down_services}
                ))
        
        return insights
```

### Analyzer Execution

**File**: `src/insights/engine.py:219`

```python
def _run_analyzers(self, data: Dict[str, Any]) -> List[Insight]:
    """Run all analyzers and collect insights."""
    all_insights: List[Insight] = []
    
    for name, analyzer in self._analyzers.items():
        # Check if enabled in config
        if not analyzer.is_enabled():
            continue
        
        try:
            # Run analyzer with collected data
            result = analyzer.run(data)
            
            # Collect insights if successful
            if result.success and result.insights:
                all_insights.extend(result.insights)
                logger.debug(f"Analyzer {name}: {len(result.insights)} insights")
        except Exception as e:
            logger.error(f"Analyzer {name} error: {e}")
    
    return all_insights
```

---

## Decision Engine

**File**: `src/insights/decision/engine.py`

The Decision Engine decides what to do with each insight based on:
- Priority level
- Current time (quiet hours?)
- Budget remaining (max 5 reach-outs/day)
- Duplicate detection

### Decision Logic

```python
class DeliveryAction(Enum):
    """What to do with an insight."""
    DELIVER_NOW = "deliver_now"      # Send immediately via Telegram
    BATCH_REPORT = "batch_report"    # Add to next morning/evening report
    QUEUE_LATER = "queue_later"      # Wait (quiet hours, budget exhausted)
    SKIP = "skip"                    # Don't deliver (duplicate, expired)

def _decide(self, insight: Insight) -> Tuple[DeliveryAction, str]:
    """Decide what to do with a single insight."""
    
    # 1. Check if expired
    if insight.is_expired():
        return DeliveryAction.SKIP, "expired"
    
    # 2. Check for duplicates (same insight within cooldown period)
    if insight.dedupe_key and self.store.check_duplicate(
        insight.dedupe_key, 
        hours=int(self.config.decision.cooldown_minutes / 60) or 1
    ):
        return DeliveryAction.SKIP, "duplicate"
    
    # 3. Route based on priority
    if insight.priority == Priority.URGENT:
        # URGENT: Always deliver immediately, ignore quiet hours & budget
        return DeliveryAction.DELIVER_NOW, "urgent_priority"
    
    elif insight.priority == Priority.HIGH:
        # HIGH: Deliver if allowed, otherwise queue
        if self.budget.can_deliver(insight):
            return DeliveryAction.DELIVER_NOW, "high_priority"
        elif self.budget.is_quiet_hours():
            return DeliveryAction.QUEUE_LATER, "quiet_hours"
        else:
            return DeliveryAction.BATCH_REPORT, "budget_exhausted"
    
    elif insight.priority == Priority.MEDIUM:
        # MEDIUM: Deliver if budget allows, otherwise batch for report
        if self.budget.is_quiet_hours():
            return DeliveryAction.BATCH_REPORT, "quiet_hours"
        elif self.budget.has_budget():
            return DeliveryAction.DELIVER_NOW, "medium_with_budget"
        else:
            return DeliveryAction.BATCH_REPORT, "budget_exhausted"
    
    else:  # LOW
        # LOW: Always batch for next report
        return DeliveryAction.BATCH_REPORT, "low_priority"
```

### Budget Manager

**File**: `src/insights/decision/budget.py`

Prevents notification fatigue by limiting reach-outs:

```python
class BudgetManager:
    """Manages delivery budget to prevent notification spam."""
    
    def __init__(self, config: InsightsConfig, store: InsightsStore):
        self.config = config
        self.store = store
        self.max_daily = config.decision.max_reach_outs_per_day  # 5
        self.quiet_start = config.decision.quiet_hours_start     # 22:00
        self.quiet_end = config.decision.quiet_hours_end         # 08:00
    
    def is_quiet_hours(self) -> bool:
        """Check if we're in quiet hours (22:00-08:00 BRT)."""
        now = datetime.now(BRT)
        current_hour = now.hour
        
        # Handle overnight range (22:00 to 08:00)
        if self.quiet_start > self.quiet_end:
            return current_hour >= self.quiet_start or current_hour < self.quiet_end
        else:
            return self.quiet_start <= current_hour < self.quiet_end
    
    def has_budget(self) -> bool:
        """Check if we have budget remaining for today."""
        today = datetime.now(BRT).date()
        count = self.store.count_deliveries_today(today)
        return count < self.max_daily
    
    def can_deliver(self, insight: Insight) -> bool:
        """Check if we can deliver this insight now."""
        # URGENT always gets through
        if insight.priority == Priority.URGENT:
            return True
        
        # Check quiet hours
        if self.is_quiet_hours():
            return False
        
        # Check budget
        return self.has_budget()
    
    def consume_budget(self, insight_id: str):
        """Mark that we've used one delivery slot."""
        # Budget is automatically consumed when delivery is recorded
        pass
```

---

## Message Delivery

**File**: `src/insights/delivery/manager.py`

### Delivery Flow

```python
def process_insights(self, insights: List[Insight]) -> Dict[str, int]:
    """Process a batch of insights from analyzers."""
    stats = {"delivered": 0, "batched": 0, "queued": 0, "skipped": 0}
    
    # 1. Run through decision engine
    decisions = self.decision.process(insights)
    
    # 2. Process each decision
    for insight in decisions[DeliveryAction.DELIVER_NOW]:
        success = self._deliver_immediate(insight)
        if success:
            stats["delivered"] += 1
        else:
            stats["queued"] += 1
    
    for insight in decisions[DeliveryAction.BATCH_REPORT]:
        self._batch_for_report(insight)
        stats["batched"] += 1
    
    for insight in decisions[DeliveryAction.QUEUE_LATER]:
        self._queue_for_later(insight)
        stats["queued"] += 1
    
    stats["skipped"] = len(decisions[DeliveryAction.SKIP])
    
    logger.info(f"[DELIVERY] Processed {len(insights)} insights: "
                f"delivered={stats['delivered']}, batched={stats['batched']}, "
                f"queued={stats['queued']}, skipped={stats['skipped']}")
    return stats

def _deliver_immediate(self, insight: Insight) -> bool:
    """Deliver an insight immediately via Telegram."""
    try:
        success = self.telegram.send_insight_sync(insight)
        if success:
            # Record delivery in database
            self.decision.record_delivery(insight, DeliveryChannel.TELEGRAM)
        return success
    except Exception as e:
        logger.error(f"Failed to deliver insight '{insight.title}': {e}")
        return False
```

### Telegram Sender

**File**: `src/insights/delivery/telegram.py`

```python
class TelegramSender:
    """Send insights and reports via Telegram."""
    
    def send_insight_sync(self, insight: Insight) -> bool:
        """Send a single insight notification."""
        # Format message with emoji based on priority
        emoji = {
            Priority.URGENT: "🚨",
            Priority.HIGH: "⚠️",
            Priority.MEDIUM: "ℹ️",
            Priority.LOW: "💡"
        }.get(insight.priority, "📌")
        
        # Build message
        message = f"{emoji} *{insight.title}*\n\n{insight.message}"
        
        # Add context if available
        if insight.context:
            message += f"\n\n_{insight.context}_"
        
        # Send to Friday API which forwards to Telegram
        try:
            client = FridayAPIClient()
            response = client.send_alert(
                source=f"insights_{insight.category.value}",
                level=insight.priority.value.lower(),
                message=message
            )
            
            logger.info(f"Sent insight to Telegram: {insight.title}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send to Telegram: {e}")
            return False
```

---

## Scheduled Reports

**File**: `src/insights/engine.py:275`

Reports are sent at specific times daily/weekly:

### Report Schedule

| Report | Time | Day | Content |
|--------|------|-----|---------|
| **Morning** | 10:00 BRT | Daily | Weather, calendar, health status, homelab |
| **Evening** | 21:00 BRT | Daily | Health recap, tomorrow preview |
| **Weekly** | 20:00 BRT | Sunday | Health trends, calendar summary, system health |
| **Daily Journal Note** | 23:59 BRT | Daily | Generated Obsidian note from journal entries |

### Report Check Logic

```python
async def _check_scheduled_reports(self):
    """Check if any scheduled reports are due and send them."""
    now = datetime.now(BRT)
    today = now.strftime("%Y-%m-%d")
    
    # Morning report (10:00 BRT)
    if self.config.delivery.morning_report_enabled:
        if self._is_report_due("morning", today, now):
            logger.info("Sending morning report...")
            success = self.delivery.send_morning_report()
            if success:
                self._mark_report_sent("morning", today)
    
    # Evening report (21:00 BRT)
    if self.config.delivery.evening_report_enabled:
        if self._is_report_due("evening", today, now):
            logger.info("Sending evening report...")
            success = self.delivery.send_evening_report()
            if success:
                self._mark_report_sent("evening", today)
    
    # Weekly report (Sunday 20:00 BRT)
    if self.config.delivery.weekly_report_enabled:
        day_name = now.strftime("%A").lower()
        if day_name == self.config.delivery.weekly_report_day:
            week_key = now.strftime("%Y-W%W")
            if self._is_report_due("weekly", week_key, now, is_weekly=True):
                logger.info("Sending weekly report...")
                success = self.delivery.send_weekly_report()
                if success:
                    self._mark_report_sent("weekly", week_key)

def _is_report_due(
    self, 
    report_type: str, 
    date_key: str, 
    now: datetime,
    is_weekly: bool = False
) -> bool:
    """Check if a report is due."""
    
    # 1. Check if already sent today/this week
    state_key = f"{report_type}_report"
    if self._report_state.get(state_key) == date_key:
        return False  # Already sent
    
    # 2. Get target time from config
    if report_type == "morning":
        target = self.config.delivery.morning_report_time  # 10:00
    elif report_type == "evening":
        target = self.config.delivery.evening_report_time  # 21:00
    else:
        target = self.config.delivery.weekly_report_time   # 20:00
    
    # 3. Check if within 2-minute window of target time
    current_minutes = now.hour * 60 + now.minute
    target_minutes = target.hour * 60 + target.minute
    
    return abs(current_minutes - target_minutes) <= 2
```

### Morning Report Generation

**File**: `src/insights/delivery/reports.py:43`

```python
def generate_morning_report(self) -> str:
    """Generate morning briefing report."""
    now = datetime.now(BRT)
    sections = []
    
    # Header
    sections.append(f"Good morning! Here's your briefing for {now.strftime('%A, %b %d')}")
    sections.append("")
    
    # 1. Weather (from WeatherCollector)
    weather_section = self._generate_weather_section()
    if weather_section:
        sections.append(weather_section)
        sections.append("")
    
    # 2. Calendar (from CalendarCollector)
    calendar_section = self._generate_calendar_section()
    if calendar_section:
        sections.append(calendar_section)
        sections.append("")
    
    # 3. Health status (from HealthCollector)
    health_section = self._generate_health_section()
    if health_section:
        sections.append(health_section)
        sections.append("")
    
    # 4. Homelab status (from HomelabCollector)
    homelab_section = self._generate_homelab_brief()
    if homelab_section:
        sections.append(homelab_section)
    
    return "\n".join(sections)

def _generate_health_section(self) -> Optional[str]:
    """Generate health section for morning report."""
    try:
        # Collect fresh health data
        data = self.health.collect()
        if not data:
            return None
        
        # Check sync status
        sync = data.get("sync_status", {})
        if sync.get("status") not in ["current", "recent"]:
            hours_ago = sync.get("hours_ago", 0)
            return f"Health\nGarmin data stale ({hours_ago:.0f}h ago)"
        
        lines = ["Health"]
        
        # Sleep score and duration
        sleep = data.get("sleep", {})
        sleep_score = sleep.get("score")
        sleep_dur = sleep.get("total_hours")
        if sleep_score:
            lines.append(f"Sleep: {sleep_score} ({sleep_dur:.1f}h)")
        
        # Body battery percentage
        bb = data.get("body_battery", {}).get("current")
        if bb:
            lines.append(f"Body battery: {bb}%")
        
        # Current stress level
        stress = data.get("stress", {}).get("current")
        if stress and stress > 0:
            lines.append(f"Stress: {stress}")
        
        return "\n".join(lines) if len(lines) > 1 else None
        
    except Exception as e:
        logger.error(f"Health section error: {e}")
        return None
```

---

## Code Examples

### Complete Flow: High Stress Detection

Let's trace a high stress alert from detection to delivery:

#### 1. Collection (Every 5 minutes)

```python
# src/insights/collectors/health.py
data = health_collector.collect()
# Returns:
{
    "stress": {
        "current": 85,  # High!
        "average": 45,
        "max": 90
    },
    "body_battery": {"current": 30},  # Low!
    ...
}
```

#### 2. Analysis (Every cycle if data collected)

```python
# src/insights/analyzers/thresholds.py
stress = data["health"]["stress"]["current"]  # 85

if stress > self.config.threshold_stress:  # threshold = 70
    insight = Insight(
        title="High Stress Detected",
        message=f"Your stress level is {stress} (threshold: 70)",
        priority=Priority.HIGH,
        category=Category.HEALTH,
        dedupe_key=f"stress_high_{now.strftime('%Y-%m-%d-%H')}",  # Prevents duplicates within same hour
        expires_at=now + timedelta(hours=2)  # Insight only relevant for 2 hours
    )
    return [insight]
```

#### 3. Decision (Immediate)

```python
# src/insights/decision/engine.py
def _decide(self, insight):
    # Check expiration
    if insight.is_expired():  # False (just created)
        return SKIP
    
    # Check duplicate
    if self.store.check_duplicate("stress_high_2026-01-02-13", hours=1):  # False (first time this hour)
        return SKIP
    
    # Route by priority
    if insight.priority == Priority.HIGH:
        if self.budget.can_deliver(insight):  # True (not quiet hours, budget available)
            return DELIVER_NOW, "high_priority"
    
    return DELIVER_NOW, "high_priority"
```

#### 4. Delivery (Via Telegram)

```python
# src/insights/delivery/telegram.py
message = "⚠️ *High Stress Detected*\n\nYour stress level is 85 (threshold: 70)"

# Send to Friday API
client.send_alert(
    source="insights_health",
    level="high",
    message=message
)

# Record delivery
self.decision.record_delivery(insight, DeliveryChannel.TELEGRAM)
self.budget.consume_budget(insight.id)  # Uses 1 of 5 daily slots
```

#### 5. User Receives

```
Telegram notification:
⚠️ High Stress Detected

Your stress level is 85 (threshold: 70)
```

---

### Example: Service Down Detection

#### 1. Collection

```python
# src/insights/collectors/homelab.py
services_data = homelab_collector.collect()
# Returns:
{
    "services": {
        "total": 17,
        "up": 15,
        "down": 2,
        "down_services": ["Prometheus", "Grafana"]
    }
}
```

#### 2. Analysis

```python
# src/insights/analyzers/thresholds.py
down_services = data["homelab"]["services"]["down_services"]  # ["Prometheus", "Grafana"]

if down_services:
    insight = Insight(
        title=f"Services Down: {len(down_services)}",
        message=f"Services offline: Prometheus, Grafana",
        priority=Priority.MEDIUM,  # 2 services = MEDIUM, >2 = HIGH
        category=Category.SYSTEM,
        dedupe_key=f"services_down_Grafana_Prometheus",  # Sorted to prevent different order = different key
        data={"down_services": down_services}
    )
```

#### 3. Decision

```python
# Priority.MEDIUM during daytime with budget
if not is_quiet_hours() and has_budget():
    return DELIVER_NOW, "medium_with_budget"
```

#### 4. Delivery

```
Telegram:
ℹ️ Services Down: 2

Services offline: Prometheus, Grafana
```

---

## Summary: When Friday Sends Messages

### Real-Time Alerts (As Events Happen)

Sent immediately when thresholds are crossed:
- 🚨 **URGENT**: Critical system issues (always sent)
- ⚠️ **HIGH**: High stress (>70), services down (>2), meeting conflicts
- ℹ️ **MEDIUM**: Moderate issues during daytime with budget
- 💡 **LOW**: Always batched for reports

**Constraints**:
- ❌ No messages during quiet hours (22:00-08:00) except URGENT
- ❌ Max 5 reach-outs per day
- ❌ Duplicate detection (same issue within cooldown period)

### Scheduled Reports

Sent at exact times:
- 🌅 **Morning Report** (10:00 BRT): Weather, calendar, health, homelab
- 🌙 **Evening Report** (21:00 BRT): Day summary, tomorrow preview
- 📊 **Weekly Report** (Sunday 20:00 BRT): Trends and patterns
- 📝 **Daily Note** (23:59 BRT): Obsidian note from journal entries

---

## Configuration

**File**: `config/insights.json`

```json
{
  "collectors": {
    "health": {
      "enabled": true,
      "interval_seconds": 300
    },
    "calendar": {
      "enabled": true,
      "interval_seconds": 300
    },
    "homelab": {
      "enabled": true,
      "interval_seconds": 300
    },
    "weather": {
      "enabled": true,
      "interval_seconds": 1800
    }
  },
  "delivery": {
    "morning_report_enabled": true,
    "morning_report_time": "10:00",
    "evening_report_enabled": true,
    "evening_report_time": "21:00",
    "weekly_report_enabled": true,
    "weekly_report_day": "sunday",
    "weekly_report_time": "20:00",
    "daily_note_enabled": true
  },
  "decision": {
    "max_reach_outs_per_day": 5,
    "quiet_hours_start": 22,
    "quiet_hours_end": 8,
    "cooldown_minutes": 60
  },
  "thresholds": {
    "stress": 70,
    "body_battery": 20,
    "disk_usage_percent": 85
  }
}
```

---

## Database Schema

**File**: `data/insights.db` (SQLite)

### Tables

```sql
-- Snapshots: Historical data from collectors
CREATE TABLE snapshots (
    id TEXT PRIMARY KEY,
    collector TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    data TEXT NOT NULL  -- JSON
);

-- Insights: Generated alerts/notifications
CREATE TABLE insights (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    priority TEXT NOT NULL,
    category TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    expires_at DATETIME,
    dedupe_key TEXT,
    delivered BOOLEAN DEFAULT 0,
    data TEXT  -- JSON
);

-- Deliveries: Track when insights were sent
CREATE TABLE deliveries (
    id TEXT PRIMARY KEY,
    insight_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    delivered_at DATETIME NOT NULL,
    FOREIGN KEY (insight_id) REFERENCES insights(id)
);
```

---

## Logging

All components log to `/home/artur/friday/logs/friday-awareness.log`:

```
2026-01-02 10:00:00 - src.insights.engine - INFO - [INSIGHTS] Engine started
2026-01-02 10:00:10 - src.insights.engine - DEBUG - Collected from health
2026-01-02 10:00:10 - src.insights.analyzers.thresholds - DEBUG - Analyzer threshold: 1 insights
2026-01-02 10:00:10 - src.insights.decision.engine - DEBUG - Decision for 'High Stress Detected': deliver_now (high_priority)
2026-01-02 10:00:11 - src.insights.delivery.telegram - INFO - Sent insight to Telegram: High Stress Detected
2026-01-02 10:00:11 - src.insights.delivery.manager - INFO - [DELIVERY] Processed 1 insights: delivered=1, batched=0, queued=0, skipped=0
2026-01-02 10:58:00 - src.insights.engine - INFO - Sending morning report...
2026-01-02 10:58:03 - src.insights.delivery.telegram - INFO - Sent morning report to Telegram
2026-01-02 10:58:03 - src.insights.delivery.manager - INFO - [DELIVERY] Morning report sent successfully
```

---

## Testing

Test individual components:

```bash
# Test health collector
pipenv run python -c "
from src.insights.collectors.health import HealthCollector
collector = HealthCollector()
collector.initialize()
data = collector.collect()
print(data)
"

# Test morning report
pipenv run python -c "
from src.insights.config import InsightsConfig
from src.insights.store import InsightsStore
from src.insights.delivery.reports import ReportGenerator

config = InsightsConfig.load()
store = InsightsStore()
gen = ReportGenerator(config, store)
print(gen.generate_morning_report())
"

# Check service logs
./friday logs friday-awareness -n 100
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                       INSIGHTS ENGINE                            │
│                   (friday-awareness service)                     │
└─────────────────────────────────────────────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │   Main Loop (10s)       │
                    └────────────┬────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
        ▼                        ▼                        ▼
┌──────────────┐         ┌──────────────┐        ┌──────────────┐
│  COLLECTORS  │         │  ANALYZERS   │        │   REPORTS    │
├──────────────┤         ├──────────────┤        ├──────────────┤
│ Health (5m)  │────────▶│ Thresholds   │        │ Morning 10am │
│ Calendar(5m) │         │ Stress       │        │ Evening 9pm  │
│ Homelab (5m) │         │ Calendar     │        │ Weekly Sun   │
│ Weather(30m) │         │ Correlation  │        │ Daily Note   │
└──────────────┘         └──────────────┘        └──────────────┘
        │                        │                        │
        │                        ▼                        │
        │                ┌──────────────┐                │
        │                │   INSIGHTS   │                │
        │                │  (Generated) │                │
        │                └──────────────┘                │
        │                        │                        │
        │                        ▼                        │
        │                ┌──────────────┐                │
        │                │   DECISION   │                │
        │                │    ENGINE    │                │
        │                ├──────────────┤                │
        │                │ Priority?    │                │
        │                │ Budget?      │                │
        │                │ Quiet hours? │                │
        │                │ Duplicate?   │                │
        │                └──────────────┘                │
        │                        │                        │
        └────────────────────────┼────────────────────────┘
                                 │
                                 ▼
                        ┌──────────────┐
                        │   DELIVERY   │
                        │   MANAGER    │
                        └──────────────┘
                                 │
                    ┌────────────┴────────────┐
                    ▼                         ▼
            ┌──────────────┐        ┌──────────────┐
            │   TELEGRAM   │        │   DATABASE   │
            │   (via API)  │        │  (SQLite)    │
            └──────────────┘        └──────────────┘
                    │                         │
                    ▼                         ▼
            ┌──────────────┐        ┌──────────────┐
            │     USER     │        │  SNAPSHOTS   │
            │  (You! 📱)   │        │  INSIGHTS    │
            └──────────────┘        │  DELIVERIES  │
                                    └──────────────┘
```

---

**Last Updated**: 2026-01-02  
**Author**: Friday 3.0 Insights Engine
