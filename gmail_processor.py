import base64
import os
import pdfplumber
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Scopes required for the application
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


class GmailProcessor:
    def __init__(self):
        self.creds = self._load_credentials()
        self.service = build('gmail', 'v1', credentials=self.creds)

        # Comprehensive list of financial keywords to detect invoices and utility bills
        self.finance_keywords = [
            'חשבונית', 'קבלה', 'אישור תשלום', 'אישור הזמנה', 'הזמנתך', 'תשלום',
            'חיוב', 'עסקה', 'פרטי הזמנה', 'מסמך ממוחשב', 'חשבונית מס', 'חשבון',
            'הזמנה', 'ארנונה', 'חשמל', 'גיחון', 'מים', 'הוט', 'hot', 'סלקום',
            'פלאפון', 'פרטנר', 'בזק', 'yes', 'מנורה', 'הראל', 'ביטוח',
            'invoice', 'receipt', 'reciept', 'order confirmation', 'payment',
            'billing', 'e-ticket', 'transaction', 'statement', 'tax invoice',
            'purchased', 'wolt', 'apple', 'google', 'subscription', 'amazon'
        ]

    def _load_credentials(self):
        """Loads user credentials from the local token file."""
        if os.path.exists('token.json'):
            return Credentials.from_authorized_user_file('token.json', SCOPES)
        else:
            raise FileNotFoundError(
                "token.json not found. Run gmail_setup.py first.")

    def _get_latest_message_meta(self):
        """Fetches the ID of the most recent message in the inbox."""
        results = self.service.users().messages().list(userId='me',
                                                       maxResults=1).execute()
        messages = results.get('messages', [])
        return messages[0] if messages else None

    def _extract_email_body(self, payload):
        """
        Recursively extracts the plain text body from the email payload.
        Handles both simple and multi-part messages.
        """
        body = ""
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data')
                    if data:
                        body = base64.urlsafe_b64decode(data).decode('utf-8')
                        break
                # Handle nested multi-parts
                elif 'parts' in part:
                    body = self._extract_email_body(part)
                    if body:
                        break
        else:
            data = payload.get('body', {}).get('data')
            if data:
                body = base64.urlsafe_b64decode(data).decode('utf-8')
        return body

    def _is_financial_subject(self, payload):
        """Checks if the email subject contains financial keywords (Case-insensitive)."""
        headers = payload.get('headers', [])
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'),
                       "").lower()

        # Check against the master list defined in __init__
        is_match = any(
            word.lower() in subject for word in self.finance_keywords)
        if not is_match:
            print(
                f"DEBUG: Skipping email. Subject '{subject}' is not financial.")
        return is_match

    def _extract_text_from_pdf_file(self, file_path):
        """Opens a PDF file and extracts its text content using pdfplumber."""
        text = ""
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            print(f"Error processing PDF {file_path}: {e}")
        return text

    def _download_and_parse_attachment(self, msg_id, part):
        """Downloads a PDF attachment, saves it temporarily, and extracts its text."""
        filename = part.get('filename')
        att_id = part['body'].get('attachmentId')

        attachment = self.service.users().messages().attachments().get(
            userId='me', messageId=msg_id, id=att_id).execute()

        file_data = base64.urlsafe_b64decode(attachment['data'].encode('UTF-8'))

        # Temporary disk storage for processing
        temp_filename = f"temp_{filename}"
        with open(temp_filename, 'wb') as f:
            f.write(file_data)

        content = self._extract_text_from_pdf_file(temp_filename)
        os.remove(temp_filename)

        return {"filename": filename, "text": content}

    def get_latest_email_pdf_content(self):
        """
        Orchestration method:
        1. Fetches the latest email.
        2. Validates the subject.
        3. Extracts the email body and all PDF attachments.
        4. Combines them into a single context for AI analysis.
        """
        message_meta = self._get_latest_message_meta()
        if not message_meta:
            return []

        msg_id = message_meta['id']
        message = self.service.users().messages().get(userId='me',
                                                      id=msg_id).execute()
        payload = message.get('payload', {})

        # Layer 1 Filter: Subject check
        if not self._is_financial_subject(payload):
            return []

        # Extract the Email Body to provide context for the AI (e.g., "Thanks for buying at...")
        email_body = self._extract_email_body(payload)

        parts = payload.get('parts', [])
        extracted_results = []

        # Find and process PDF attachments
        for part in parts:
            if part.get('filename') and part.get('filename').lower().endswith(
                    '.pdf'):
                result = self._download_and_parse_attachment(msg_id, part)

                if result["text"]:
                    # Combine body and PDF text using clear delimiters
                    combined_context = (
                        f"--- EMAIL BODY START ---\n{email_body}\n--- EMAIL BODY END ---\n\n"
                        f"--- PDF CONTENT START ---\n{result['text']}\n--- PDF CONTENT END ---"
                    )

                    extracted_results.append({
                        "msg_id": msg_id,
                        "filename": result["filename"],
                        "text": combined_context
                    })

        return extracted_results


# Singleton instance for the application
gmail_engine = GmailProcessor()