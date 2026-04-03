"""
gmail_processor.py
==================

Gmail client for fetching and extracting content from the latest financial emails.

Authenticates via per-user OAuth token files, filters emails by financial keywords
in the subject line, and extracts plain text bodies and PDF attachments for
downstream AI parsing.
"""

import base64
import os
import pdfplumber
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


class GmailProcessor:
    """Fetch and extract content from the latest financial email for a given user."""

    def __init__(self, username: str) -> None:
        """Initialize the processor and authenticate with the Gmail API.

        :param username: Lowercase username (e.g. ``'michael'``), used to locate
                         the OAuth token file (``token_{username}.json``).
        :raises FileNotFoundError: If the token file for the user does not exist.
        """
        self.username = username
        self.creds = self._load_credentials()
        self.service = build('gmail', 'v1', credentials=self.creds)

        # Hebrew and English keywords that indicate a financial email
        self.finance_keywords = [
            'חשבונית', 'קבלה', 'אישור תשלום', 'אישור הזמנה', 'הזמנתך', 'תשלום',
            'חיוב', 'עסקה', 'פרטי הזמנה', 'מסמך ממוחשב', 'חשבונית מס', 'חשבון',
            'הזמנה', 'ארנונה', 'חשמל', 'גיחון', 'מים', 'הוט', 'hot', 'סלקום',
            'פלאפון', 'פרטנר', 'בזק', 'yes', 'מנורה', 'הראל', 'ביטוח',
            'invoice', 'receipt', 'reciept', 'order confirmation', 'payment',
            'billing', 'e-ticket', 'transaction', 'statement', 'tax invoice',
            'purchased', 'wolt', 'apple', 'google', 'subscription', 'amazon'
        ]

    def _load_credentials(self) -> Credentials:
        """Load OAuth credentials from the user's token file.

        :returns: A ``Credentials`` object for the Gmail API.
        :raises FileNotFoundError: If ``token_{username}.json`` is missing.
        """
        token_filename = f'token_{self.username}.json'
        if os.path.exists(token_filename):
            return Credentials.from_authorized_user_file(token_filename, SCOPES)
        else:
            raise FileNotFoundError(f"{token_filename} missing.")

    def _get_latest_message_meta(self) -> dict | None:
        """Fetch the metadata of the most recent message in the inbox.

        :returns: A message metadata dict with at least an ``id`` key,
                  or ``None`` if the inbox is empty.
        """
        results = self.service.users().messages().list(userId='me', maxResults=1).execute()
        messages = results.get('messages', [])
        return messages[0] if messages else None

    def _extract_email_body(self, payload: dict) -> str:
        """Recursively extract the plain text body from an email payload.

        Handles both simple and multi-part MIME messages.

        :param payload: The ``payload`` field from a Gmail message object.
        :returns: Plain text body string, or an empty string if none is found.
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

    def _is_financial_subject(self, payload: dict) -> bool:
        """Check whether the email subject contains a financial keyword.

        :param payload: The ``payload`` field from a Gmail message object.
        :returns: ``True`` if a keyword matches, ``False`` otherwise.
        """
        headers = payload.get('headers', [])
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "").lower()

        is_match = any(word.lower() in subject for word in self.finance_keywords)
        if not is_match:
            print(f"DEBUG: Skipping email. Subject '{subject}' is not financial.")
        return is_match

    def _extract_text_from_pdf_file(self, file_path: str) -> str:
        """Extract all text from a PDF file using pdfplumber.

        :param file_path: Path to the PDF file on disk.
        :returns: Concatenated text from all pages, or an empty string on failure.
        """
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

    def _download_and_parse_attachment(self, msg_id: str, part: dict) -> dict:
        """Download a PDF attachment, save it temporarily, and extract its text.

        :param msg_id: Gmail message ID containing the attachment.
        :param part: The MIME part dict describing the attachment.
        :returns: A dict with ``filename`` and ``text`` keys.
        """
        filename = part.get('filename')
        att_id = part['body'].get('attachmentId')

        attachment = self.service.users().messages().attachments().get(
            userId='me', messageId=msg_id, id=att_id).execute()

        file_data = base64.urlsafe_b64decode(attachment['data'].encode('UTF-8'))

        # Write to a temp file so pdfplumber can open it from disk
        temp_filename = f"temp_{filename}"
        with open(temp_filename, 'wb') as f:
            f.write(file_data)

        content = self._extract_text_from_pdf_file(temp_filename)
        os.remove(temp_filename)

        return {"filename": filename, "text": content}

    def get_latest_email_pdf_content(self) -> list[dict]:
        """Fetch, filter, and extract content from the latest email.

        1. Retrieves the most recent inbox message.
        2. Skips it if the subject does not match financial keywords.
        3. Extracts the plain text body and all PDF attachments.
        4. Combines body and PDF text into a single delimited string per attachment.

        :returns: A list of dicts, each with ``msg_id``, ``filename``, and ``text``
                  (combined email body + PDF content). Returns ``[]`` if no
                  financial content is found.
        """
        message_meta = self._get_latest_message_meta()
        if not message_meta:
            return []

        msg_id = message_meta['id']
        message = self.service.users().messages().get(userId='me', id=msg_id).execute()
        payload = message.get('payload', {})

        # Layer 1 Filter: skip non-financial emails before downloading attachments
        if not self._is_financial_subject(payload):
            return []

        email_body = self._extract_email_body(payload)

        parts = payload.get('parts', [])
        extracted_results = []

        for part in parts:
            if part.get('filename') and part.get('filename').lower().endswith('.pdf'):
                result = self._download_and_parse_attachment(msg_id, part)

                if result["text"]:
                    # Delimiters help the AI distinguish email context from invoice data
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