#!/usr/bin/env python3
"""
Google Calendar OAuth helper.

Run this script to authenticate with Google Calendar.
Uses localhost redirect - requires port forwarding if running on remote server.

For remote server:
    1. SSH with port forwarding: ssh -L 8090:localhost:8090 user@server
    2. Run this script
    3. Open the URL in your local browser

Usage:
    python scripts/google_auth.py
"""

import pickle
import socket
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

DATA_DIR = Path(__file__).parent.parent / "data"
GOOGLE_CREDENTIALS_FILE = DATA_DIR / "google_credentials.json"
GOOGLE_TOKEN_FILE = DATA_DIR / "google_token.pickle"

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
PORT = 8090

# Store the auth code
auth_code = None

class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        query = urlparse(self.path).query
        params = parse_qs(query)
        
        if 'code' in params:
            auth_code = params['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"""
                <html><body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
                <h1>Authorization successful!</h1>
                <p>You can close this window and return to the terminal.</p>
                </body></html>
            """)
        else:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Error: No code received</h1></body></html>")
    
    def log_message(self, format, *args):
        pass  # Suppress logging


def main():
    global auth_code
    creds = None
    
    if GOOGLE_TOKEN_FILE.exists():
        with open(GOOGLE_TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
        print("Existing token found.")
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired token...")
            creds.refresh(Request())
        else:
            print(f"Starting OAuth flow...")
            print(f"Using credentials: {GOOGLE_CREDENTIALS_FILE}\n")
            
            redirect_uri = f'http://localhost:{PORT}'
            
            flow = Flow.from_client_secrets_file(
                str(GOOGLE_CREDENTIALS_FILE),
                scopes=SCOPES,
                redirect_uri=redirect_uri
            )
            
            auth_url, _ = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'
            )
            
            print("=" * 60)
            print("If on remote server, make sure you SSH'd with:")
            print(f"  ssh -L {PORT}:localhost:{PORT} user@server")
            print("=" * 60)
            print(f"\nOpen this URL in your browser:\n")
            print(auth_url)
            print("\n" + "=" * 60)
            print(f"\nWaiting for authorization on port {PORT}...")
            
            # Start local server to catch the redirect
            server = HTTPServer(('localhost', PORT), OAuthHandler)
            server.handle_request()  # Handle single request
            
            if auth_code:
                print("\nReceived authorization code!")
                flow.fetch_token(code=auth_code)
                creds = flow.credentials
            else:
                print("Error: No authorization code received")
                return
        
        with open(GOOGLE_TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
        print(f"\n✅ Token saved to {GOOGLE_TOKEN_FILE}")
    else:
        print("Token is valid.")
    
    # Test it
    print("\nTesting connection...")
    service = build('calendar', 'v3', credentials=creds)
    calendars = service.calendarList().list().execute()
    print("\n✅ Available calendars:")
    for cal in calendars.get('items', []):
        print(f"  - {cal['summary']} ({cal['id']})")

if __name__ == "__main__":
    main()
