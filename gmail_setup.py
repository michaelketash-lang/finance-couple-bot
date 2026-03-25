import os
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# We only need read-only access to fetch the emails/attachments
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID")
TOPIC_NAME = f"projects/{PROJECT_ID}/topics/gmail-notifications"


def main():
    # 1. Validation
    if not PROJECT_ID:
        print("❌ ERROR: GOOGLE_PROJECT_ID is missing from your .env file.")
        return

    if not os.path.exists('credentials.json'):
        print("❌ ERROR: credentials.json not found in the project directory.")
        return

    creds = None
    # The file token.json stores the user's access and refresh tokens.
    # It is created automatically when the authorization flow completes for the first time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # 2. Authentication Flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json',
                                                             SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for future runs
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    # 3. Establishing the Watch
    try:
        # Build the Gmail service
        service = build('gmail', 'v1', credentials=creds)

        # Tell Gmail where to push notifications
        watch_request = {
            'labelIds': ['INBOX'],
            'topicName': TOPIC_NAME
        }

        response = service.users().watch(userId='me',
                                         body=watch_request).execute()

        print("✅ SUCCESS: Gmail Watch established!")
        print(f"⏰ Expiration (Timestamp): {response.get('expiration')}")
        print(
        "⚠️  REMINDER: You must renew this watch at least once every 7 days.")

    except Exception as error:
        print(f"❌ API ERROR: Failed to establish watch: {error}")


if __name__ == '__main__':
    main()