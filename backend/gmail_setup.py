"""
gmail_setup.py
==============

One-time CLI script for setting up Gmail OAuth credentials and registering
a Pub/Sub push notification watch for a given user.

Run this locally for each user (michael or ori) to generate their
``token_{username}.json`` file and activate Gmail push notifications.
The watch expires every 7 days and must be renewed via ``/api/gmail/renew-watch``.
"""

import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

# Read-only scope is sufficient for fetching emails and attachments
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID")
TOPIC_NAME = f"projects/{PROJECT_ID}/topics/gmail-notifications"


def main() -> None:
    """Authenticate a user with Gmail and register a Pub/Sub inbox watch.

    Prompts for a username, handles OAuth token creation or refresh,
    and calls the Gmail watch API to enable push notifications.
    """
    if not PROJECT_ID:
        print("❌ ERROR: GOOGLE_PROJECT_ID is missing from your .env file.")
        return

    if not os.path.exists('credentials.json'):
        print("❌ ERROR: credentials.json not found in the project directory.")
        return

    user_name = input("Enter the user's name (michael or ori): ").strip().lower()
    token_filename = f'token_{user_name}.json'

    creds = None
    if os.path.exists(token_filename):
        creds = Credentials.from_authorized_user_file(token_filename, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Launch a local browser flow to obtain a fresh token
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_filename, 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('gmail', 'v1', credentials=creds)

        watch_request = {
            'labelIds': ['INBOX'],
            'topicName': TOPIC_NAME
        }

        response = service.users().watch(userId='me', body=watch_request).execute()

        print(f"✅ SUCCESS: Gmail Watch established for {user_name}!")
        print(f"⏰ Expiration (Timestamp): {response.get('expiration')}")
        print("⚠️  REMINDER: You must renew this watch at least once every 7 days.")

    except Exception as error:
        print(f"❌ API ERROR: Failed to establish watch: {error}")


if __name__ == '__main__':
    main()
