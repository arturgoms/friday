"""Test InfluxDB connection and explore data"""
from influxdb import InfluxDBClient

client = InfluxDBClient(
    host="192.168.1.16",
    port=8088,
    username="friday",
    password="eQQenqw6JDcYiEr4sLT3WYtvLCs",
    database="GarminStats"
)

print("Testing InfluxDB connection...")

# Test connection
try:
    version = client.ping()
    print(f"✅ Connected to InfluxDB: {version}")
except Exception as e:
    print(f"❌ Connection failed: {e}")
    exit(1)

# List measurements
print("\n📊 Available measurements:")
try:
    result = client.query("SHOW MEASUREMENTS")
    measurements = [item['name'] for item in result.get_points()]
    for m in measurements:
        print(f"  - {m}")
except Exception as e:
    print(f"Error: {e}")

# Show field keys for each measurement
print("\n🔑 Field keys per measurement:")
for measurement in measurements[:5]:  # Limit to first 5
    try:
        result = client.query(f"SHOW FIELD KEYS FROM {measurement}")
        fields = [f"{item['fieldKey']} ({item['fieldType']})" for item in result.get_points()]
        print(f"\n{measurement}:")
        for field in fields[:10]:  # Show first 10 fields
            print(f"    {field}")
    except Exception as e:
        print(f"  Error: {e}")

# Sample recent data
print("\n📅 Sample recent data:")
try:
    result = client.query("SELECT * FROM activities ORDER BY time DESC LIMIT 3")
    for point in result.get_points():
        print(f"\n  Activity:")
        for key, value in list(point.items())[:10]:  # Show first 10 fields
            print(f"    {key}: {value}")
except Exception as e:
    print(f"  Error querying activities: {e}")
    # Try different measurement
    try:
        result = client.query("SHOW MEASUREMENTS LIMIT 1")
        first_measurement = list(result.get_points())[0]['name']
        print(f"\n  Trying {first_measurement}:")
        result = client.query(f"SELECT * FROM {first_measurement} ORDER BY time DESC LIMIT 1")
        for point in result.get_points():
            for key, value in list(point.items())[:10]:
                print(f"    {key}: {value}")
    except Exception as e2:
        print(f"  Error: {e2}")

print("\n✅ Done!")
