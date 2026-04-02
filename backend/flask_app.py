import os
import telebot
from flask import Flask, request, jsonify
from flask_cors import CORS
from telebot import types
from dotenv import load_dotenv
from ai_parser import parser_service
from database_manager import setup_database
from telegram_bot import send_transaction_ui, register_handlers
from api_routes import api
import base64
import json
from gmail_processor import GmailProcessor

USER_EMAILS = {
    os.getenv('PAYER_1_EMAIL', 'michael.ketash@gmail.com'): os.getenv('PAYER_1', 'Michael').lower(),
    os.getenv('PAYER_2_EMAIL', 'orimac11@gmail.com'): os.getenv('PAYER_2', 'Ori').lower(),
}
# Load environment variables from .env file
load_dotenv()

# Get credentials from environment
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
MY_CHAT_ID = os.getenv('MY_CHAT_ID')

# Initialize Bot and Flask app
bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)
app = Flask(__name__)
CORS(app)
app.register_blueprint(api, url_prefix='/api')
setup_database()
processed_emails = set()
register_handlers(bot)

def process_text_and_notify(raw_text, payer, chat_id=MY_CHAT_ID):
    """
    Orchestrates the AI parsing and Telegram notification logic.
    Returns True if an expense was detected and notified, False otherwise.
    """
    # Layer 2 Filter: AI Classification
    enriched = parser_service.parse(raw_text)

    if not enriched.get('is_expense', False):
        return False

    # Send the UI to the user for approval/categorization
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
    envelope = request.get_json()
    if not envelope: return "Bad Request", 400

    try:
        # 1. Find out whose email triggered the webhook
        message = envelope.get('message', {})
        data_b64 = message.get('data')
        if not data_b64: return "OK", 200

        data_json = json.loads(base64.b64decode(data_b64).decode('utf-8'))
        email_address = data_json.get('emailAddress', '').lower()

        # 2. Match the email to Michael or Ori
        user_name = USER_EMAILS.get(email_address)
        if not user_name: return "OK", 200  # Ignore emails not in our dict

        # 3. Fire up the processor for that specific user
        engine = GmailProcessor(user_name)
        pdf_results = engine.get_latest_email_pdf_content()

        if not pdf_results: return "OK", 200

        for item in pdf_results:
            msg_id = item.get('msg_id')
            if msg_id in processed_emails: continue

            # Pass the user_name to your AI parser so the DB knows who paid
            if process_text_and_notify(item['text'],
                                       payer=user_name.capitalize()):
                processed_emails.add(msg_id)
                break

        return "OK", 200
    except Exception as e:
        print(f"Webhook Error: {e}")
        return "Internal Error", 500

@app.route('/webhook', methods=['POST'])
def handle_card_app_alert():
    """
    Handles incoming transaction data from external card apps (e.g., MacroDroid).
    """
    data = request.json
    if not data:
        return jsonify({"status": "error"}), 400

    raw_merchant = data.get('merchant', 'Unknown')
    amount = data.get('amount', '0.0')
    payer = data.get('payer', 'Card_User')

    # Re-run through AI to ensure consistent naming and categorization
    process_text_and_notify(f"{raw_merchant} {amount}", payer=payer)

    return jsonify({"status": "success"}), 200


@app.route('/telegram', methods=['POST'])
def handle_telegram_updates():
    """
    Essential entry point for Telegram bot updates on PythonAnywhere.
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
