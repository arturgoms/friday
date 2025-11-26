"""Test health coach service"""
import sys
sys.path.insert(0, '/home/artur/friday/src')

from app.services.health_coach import get_health_coach

coach = get_health_coach()

print("=" * 60)
print("FRIDAY AI - RUNNING & HEALTH COACH")
print("=" * 60)

print("\n📊 Running Summary (Last 7 Days)")
print("-" * 60)
summary = coach.get_running_summary(days=7)
for key, value in summary.items():
    print(f"{key}: {value}")

print("\n🏃 Recent Activities")
print("-" * 60)
activities = coach.get_recent_activities(limit=3)
if "activities" in activities:
    for i, act in enumerate(activities["activities"], 1):
        print(f"\n{i}. {act['name']} ({act['type']})")
        print(f"   📏 {act['distance_km']} km | ⏱️ {act['duration_min']} min | "
              f"⚡ {act['pace_min_km']} min/km | ❤️ {act['avg_hr']} bpm")

print("\n📈 Weekly Mileage (Last 4 Weeks)")
print("-" * 60)
mileage = coach.get_weekly_mileage(weeks=4)
if "weeks" in mileage:
    for week in mileage["weeks"]:
        print(f"{week['week_start']}: {week['distance_km']} km ({week['run_count']} runs)")

print("\n❤️ Heart Rate Analysis")
print("-" * 60)
hr_analysis = coach.get_heart_rate_analysis(days=7)
for key, value in hr_analysis.items():
    if key != "training_zones":
        print(f"{key}: {value}")

print("\n💤 Recovery Status")
print("-" * 60)
recovery = coach.get_recovery_status()
for key, value in recovery.items():
    print(f"{key}: {value}")

print("\n🏆 VO2 Max")
print("-" * 60)
vo2 = coach.get_vo2_max()
for key, value in vo2.items():
    if key != "trend":
        print(f"{key}: {value}")

print("\n" + "=" * 60)
print("✅ Test complete!")
print("=" * 60)
