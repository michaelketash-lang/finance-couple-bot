"""
flask_app.py
============

Main Flask application entry point for the finance bot backend.

Sets up the Flask app, registers the ``api`` and ``bff`` Blueprints,
initializes the Telegram bot, and defines three webhook endpoints:

- ``/gmail-webhook`` — receives Gmail push notifications via Google Pub/Sub.
- ``/webhook`` — receives card transaction alerts from external apps (e.g. MacroDroid).
- ``/telegram`` — receives Telegram bot updates.
"""

import os
import base64
import json
import telebot
from flask import Flask, request, jsonify
from flask_cors import CORS
from telebot import types
from dotenv import load_dotenv
from ai_parser import parser_service
from database_manager import setup_database
from telegram_bot import send_transaction_ui, register_handlers
from api_routes import api
from bff_routes import bff
from gmail_processor import GmailProcessor

USER_EMAILS = {
    os.getenv('PAYER_1_EMAIL', 'michael.ketash@gmail.com'): os.getenv('PAYER_1', 'Michael').lower(),
    os.getenv('PAYER_2_EMAIL', 'orimac11@gmail.com'): os.getenv('PAYER_2', 'Ori').lower(),
}

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
MY_CHAT_ID = os.getenv('MY_CHAT_ID')

bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)
app = Flask(__name__)
CORS(app)
app.register_blueprint(api, url_prefix='/api')
app.register_blueprint(bff, url_prefix='/api/bff')
setup_database()
processed_emails = set()
register_handlers(bot)


def process_text_and_notify(raw_text: str, payer: str, chat_id: str = MY_CHAT_ID) -> bool:
    """Parse raw text with the AI and send a Telegram confirmation UI if an expense is detected.

    :param raw_text: Raw text from an email, PDF, or card alert to classify.
    :param payer: Name of the person who made the transaction.
    :param chat_id: Telegram chat ID to send the UI to (defaults to ``MY_CHAT_ID``).
    :returns: ``True`` if an expense was detected and the UI was sent, ``False`` otherwise.
    """
    enriched = parser_service.parse(raw_text)

    if not enriched.get('is_expense', False):
        return False

    send_transaction_ui(
        bot=bot,
        chat_id=chat_id,
        merchant=enriched['merchant'],
        amount=enriched['amount'],
        category=enriched['category'],
        payer=payer
    )
    return True


@app.route('/gmail-webhook', methods=['POST'])
def handle_gmail_push():
    """Receive and process a Gmail Pub/Sub push notification.

    Decodes the base64 message payload, identifies which user's inbox
    triggered the notification, fetches the latest email content, and
    passes it to the AI parser if it hasn't been processed already.
    """
    envelope = request.get_json()
    if not envelope: return "Bad Request", 400

    try:
        message = envelope.get('message', {})
        data_b64 = message.get('data')
        if not data_b64: return "OK", 200

        # Pub/Sub wraps the payload in base64-encoded JSON
        data_json = json.loads(base64.b64decode(data_b64).decode('utf-8'))
        email_address = data_json.get('emailAddress', '').lower()

        user_name = USER_EMAILS.get(email_address)
        if not user_name: return "OK", 200

        engine = GmailProcessor(user_name)
        pdf_results = engine.get_latest_email_pdf_content()

        if not pdf_results: return "OK", 200

        for item in pdf_results:
            msg_id = item.get('msg_id')
            if msg_id in processed_emails: continue

            if process_text_and_notify(item['text'], payer=user_name.capitalize()):
                # Track processed message IDs to avoid duplicate notifications
                processed_emails.add(msg_id)
                break

        return "OK", 200
    except Exception as e:
        print(f"Webhook Error: {e}")
        return "Internal Error", 500


@app.route('/webhook', methods=['POST'])
def handle_card_app_alert():
    """Receive a transaction alert from an external card app (e.g. MacroDroid).

    Expects a JSON body with ``merchant``, ``amount``, and ``payer`` fields.
    Passes the data through the AI parser for consistent naming and categorization.
    """
    data = request.json
    if not data:
        return jsonify({"status": "error"}), 400

    raw_merchant = data.get('merchant', 'Unknown')
    amount = data.get('amount', '0.0')
    payer = data.get('payer', 'Card_User')

    process_text_and_notify(f"{raw_merchant} {amount}", payer=payer)

    return jsonify({"status": "success"}), 200


@app.route('/telegram', methods=['POST'])
def handle_telegram_updates():
    """Receive and dispatch a Telegram bot update.

    Entry point for the Telegram webhook on PythonAnywhere.
    Rejects non-JSON requests with a 403.
    """
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    return "Unauthorized", 403


if __name__ == '__main__':
    # Used only for local debugging (PythonAnywhere uses the WSGI file)
    app.run(port=8000, debug=True)