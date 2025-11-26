import os
from dotenv import load_dotenv
import requests

load_dotenv()
token = os.getenv("TELEGRAM_BOT_TOKEN")

# Get recent updates
response = requests.get(f"https://api.telegram.org/bot{token}/getUpdates")
data = response.json()

if data['ok'] and data['result']:
    for update in data['result'][-5:]:  # Last 5 updates
        if 'message' in update:
            msg = update['message']
            user = msg['from']
            print(f"User: {user['first_name']} (@{user.get('username', 'no username')})")
            print(f"User ID: {user['id']}")
            print(f"Message: {msg.get('text', 'N/A')}")
            print("-" * 50)
else:
    print("No recent messages found")
