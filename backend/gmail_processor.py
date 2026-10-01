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
import httplib2
import pdfplumber
import requests as req_lib
from google.auth.transport.requests import Request
import google_auth_httplib2
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
        _proxy = httplib2.ProxyInfo(httplib2.socks.PROXY_TYPE_HTTP, 'proxy.server', 3128)
        _http = google_auth_httplib2.AuthorizedHttp(self.creds, http=httplib2.Http(proxy_info=_proxy))
        self.service = build('gmail', 'v1', http=_http)

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
        """Load OAuth credentials from the user's token file, refreshing if expired.

        :returns: A ``Credentials`` object for the Gmail API.
        :raises FileNotFoundError: If ``token_{username}.json`` is missing.
        """
        token_filename = f'token_{self.username}.json'
        if not os.path.exists(token_filename):
            raise FileNotFoundError(f"{token_filename} missing.")

        creds = Credentials.from_authorized_user_file(token_filename, SCOPES)
        if not creds.valid and creds.expired and creds.refresh_token:
            _session = req_lib.Session()
            _session.proxies = {'https': 'http://proxy.server:3128'}
            creds.refresh(Request(session=_session))
            with open(token_filename, 'w') as f:
                f.write(creds.to_json())
        return creds

    def _get_recent_message_metas(self, count: int = 5) -> list[dict]:
        """Fetch metadata for the most recent messages in the inbox.

        :param count: Number of recent messages to fetch (default 5).
        :returns: List of message metadata dicts, each with at least an ``id`` key.
        """
        results = self.service.users().messages().list(userId='me', maxResults=count).execute()
        return results.get('messages', [])

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

    def _extract_single_email(self, msg_id: str) -> list[dict]:
        """Fetch and extract content from a single email by ID.

        :param msg_id: Gmail message ID to process.
        :returns: List of dicts with ``msg_id``, ``filename``, and ``text``, or ``[]``
                  if the email is not financial or has no extractable content.
        """
        message = self.service.users().messages().get(userId='me', id=msg_id).execute()
        payload = message.get('payload', {})

        if not self._is_financial_subject(payload):
            return []

        email_body = self._extract_email_body(payload)
        parts = payload.get('parts', [])
        results = []

        for part in parts:
            if part.get('filename') and part.get('filename').lower().endswith('.pdf'):
                result = self._download_and_parse_attachment(msg_id, part)
                if result["text"]:
                    combined_context = (
                        f"--- EMAIL BODY START ---\n{email_body}\n--- EMAIL BODY END ---\n\n"
                        f"--- PDF CONTENT START ---\n{result['text']}\n--- PDF CONTENT END ---"
                    )
                    results.append({
                        "msg_id": msg_id,
                        "filename": result["filename"],
                        "text": combined_context
                    })

        # Fallback: plain-text receipts with no PDF attachments (Wolt, Apple, Netflix, etc.)
        if not results and email_body.strip():
            results.append({
                "msg_id": msg_id,
                "filename": None,
                "text": f"--- EMAIL BODY START ---\n{email_body}\n--- EMAIL BODY END ---"
            })

        return results

    def get_latest_email_pdf_content(self) -> list[dict]:
        """Fetch, filter, and extract content from the 5 most recent emails.

        Iterates over the last 5 inbox messages so that receipts arriving
        close together between two Pub/Sub pushes are not missed.

        :returns: A flat list of dicts, each with ``msg_id``, ``filename``, and ``text``.
                  Returns ``[]`` if no financial content is found.
        """
        metas = self._get_recent_message_metas(count=5)
        extracted_results = []
        for meta in metas:
            extracted_results.extend(self._extract_single_email(meta['id']))
        return extracted_results