# Friday AI - Your Personal Running & Health Coach

## Overview
Friday now automatically analyzes your Garmin health data and provides personalized coaching insights!

## Features

### 1. Automatic Health Data Integration
When you ask Friday about health/running topics, it automatically queries your InfluxDB Garmin data.

**Trigger Keywords:**
- Running: run, running, race, marathon, jog, pace, distance
- Exercise: workout, exercise, training, fitness, cardio
- Health: heart rate, calories, sleep, recovery, tired
- Metrics: vo2, endurance, performance, progress
- General: health, wellness, activity, garmin, coach

### 2. Smart Context
Friday provides relevant data based on your question:

**Example Questions:**
```
"How was my running this month?"
→ Shows 30-day summary with distance, pace, HR

"What did I do yesterday?"
→ Shows recent activities

"Am I recovered enough to run today?"
→ Shows recovery metrics (training readiness, body battery, sleep)

"How's my progress?"
→ Analyzes trends and improvements
```

### 3. Scheduled Reports

**Daily Report (7:00 AM):**
- Recovery status (training readiness, body battery, sleep)
- Yesterday's activity summary
- Week's progress
- Personalized coaching advice for the day

**Weekly Report (Monday 8:00 AM):**
- 30-day comprehensive summary
- Performance analysis
- Trend identification
- Goals for next week

## Data Sources

Friday accesses your Garmin data from InfluxDB:
- **ActivitySummary**: Runs, workouts, activities
- **TrainingReadiness**: Recovery score
- **BodyBatteryIntraday**: Energy levels
- **SleepSummary**: Sleep quality and duration
- **VO2_Max**: Fitness level (if available)

## Usage Examples

### Via Telegram

**Check your stats:**
```
"How much did I run this week?"
"What's my average pace?"
"Show me my recent workouts"
```

**Get coaching:**
```
"Should I run today?"
"Am I training too hard?"
"How can I improve my pace?"
```

**Recovery check:**
```
"Am I recovered?"
"Did I sleep well?"
"What's my training readiness?"
```

### Response Indicators

After Friday answers, you'll see source indicators:
- 🏃 **Health Data** - Used your Garmin data
- 📚 **Notes** - Used your vault
- 💭 **Memory** - Used saved memories
- 🌐 **Web** - Used web search

## Configuration

### Report Schedule
Edit `src/app/services/coaching_scheduler.py`:

```python
# Daily report time (24h format)
CronTrigger(hour=7, minute=0)  # 7:00 AM

# Weekly report (day and time)
CronTrigger(day_of_week='mon', hour=8, minute=0)  # Monday 8:00 AM
```

### InfluxDB Connection
Edit `config/influxdb_mcp.json`:
```json
{
  "host": "192.168.1.16",
  "port": 8088,
  "database": "GarminStats"
}
```

## Coaching Insights

Friday provides intelligent coaching based on your data:

**Recovery-Based:**
- Low training readiness → Suggests rest or easy day
- High recovery → Encourages intensity
- Poor sleep → Emphasizes recovery

**Volume-Based:**
- Low frequency → Suggests consistency
- High volume → Warns about overtraining
- Good balance → Encourages maintenance

**Performance:**
- Fast pace → Celebrates progress
- Slower pace → Suggests form work
- Improvements → Tracks and motivates

## Testing

**Test health data lookup:**
```bash
cd friday
source venv/bin/activate
python -c "
import sys
sys.path.insert(0, 'src')
from app.services.health_coach import get_health_coach
coach = get_health_coach()
print(coach.generate_coaching_summary())
"
```

**Test daily report (manual):**
```bash
python -c "
import sys
sys.path.insert(0, 'src')
from app.services.coaching_scheduler import coaching_scheduler
coaching_scheduler.send_daily_report()
"
```

## Restart Services

After updating:
```bash
sudo systemctl restart friday.service
```

Check logs:
```bash
./friday logs friday | grep -i "coach\|health"
```

## Troubleshooting

**Health data not showing:**
1. Check InfluxDB connection: `config/influxdb_mcp.json`
2. Verify Garmin data exists: Run test script above
3. Check Friday logs for errors

**Reports not sending:**
1. Check scheduler started: Look for "Coaching scheduler started" in logs
2. Verify Telegram bot is running
3. Check time zone settings

**Wrong data returned:**
1. Activity type filter (currently: 'running')
2. Date range (default: 30 days)
3. Field names in InfluxDB

## Privacy & Security

- Health data stays local (InfluxDB on your network)
- No data sent to external services
- Telegram messages encrypted in transit
- InfluxDB credentials stored securely

## Future Enhancements

Possible additions:
- [ ] Training plan generator
- [ ] Injury risk prediction
- [ ] Race preparation advisor
- [ ] Nutrition tracking integration
- [ ] Weather-based recommendations
- [ ] Social comparison (Strava integration)
- [ ] Goal setting and tracking
- [ ] Custom coaching rules

---

**Features:** Automatic health data integration, Daily & weekly reports
**Status:** Active
**Reports:** Daily 7AM, Weekly Mon 8AM
