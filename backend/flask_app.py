import os
import telebot
from flask import Flask, request, jsonify
from flask_cors import CORS
from telebot import types
from dotenv import load_dotenv
from ai_parser import parser_service
from database_manager import setup_database, add_expense, get_shared_monthly_totals
from gmail_processor import gmail_engine
from api_routes import api
import datetime

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

def send_transaction_ui(chat_id, merchant, amount, category, payer):
    markup = types.InlineKeyboardMarkup(row_width=2)

    m_safe = str(merchant).replace('|', '').strip()[:10]
    p_safe = str(payer).replace('|', '').strip()[:10]
    a_safe = str(amount)
    c_safe = str(category).replace('|', '').strip()

    cb_shared = f"shrd|{m_safe}|{a_safe}|{c_safe}|{p_safe}"
    cb_priv = f"priv|{m_safe}|{a_safe}|{c_safe}|{p_safe}"

    print(f"[DEBUG] Callback Length: {len(cb_shared.encode('utf-8'))} bytes")

    markup.add(
        types.InlineKeyboardButton("Shared 🏠", callback_data=cb_shared),
        types.InlineKeyboardButton("Personal 👤", callback_data=cb_priv)
    )
    message_text = (
        f"💳 *New Transaction*\n\n"
        f"🏪 *Store:* `{merchant}`\n"
        f"💰 *Amount:* `₪{amount}`\n"
        f"📂 *Category:* `{category}`\n"
        f"👤 *Payer:* `{payer}`\n\n"
        f"*Split?*"
    )
    bot.send_message(chat_id, message_text, reply_markup=markup, parse_mode="Markdown")

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
        chat_id=chat_id,
        merchant=enriched['merchant'],
        amount=enriched['amount'],
        category=enriched['category'],
        payer=payer
    )
    return True


# --- FLASK ROUTES (WEBHOOKS) ---

@app.route('/gmail-webhook', methods=['POST'])
def handle_gmail_push():
    envelope = request.get_json()
    if not envelope: return "Bad Request", 400

    try:
        pdf_results = gmail_engine.get_latest_email_pdf_content()
        if not pdf_results: return "OK", 200

        # We only want to process the FIRST valid expense PDF per email ID
        # to avoid double messages (e.g., one for Receipt and one for Tax Invoice)
        for item in pdf_results:
            msg_id = item.get('msg_id')

            if msg_id in processed_emails:
                continue

            # If we successfully parsed and notified ONE PDF from this email...
            if process_text_and_notify(item['text'], payer="Michael"):
                processed_emails.add(msg_id)

                if len(processed_emails) > 100:
                    processed_emails.pop()

                # CRITICAL: Stop searching other PDFs in the same email
                break

        return "OK", 200

    except Exception as e:
        print(f"Error in Gmail Webhook route: {e}")
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

@bot.message_handler(commands=['add'])
def handle_manual_add(message):
    raw_text = message.text.replace('/add', '').strip()

    if not raw_text:
        bot.reply_to(message, "❌ Please provide details. Ex: `/add 50 Aroma`")
        return

    # 1. The AI Brain extracts data. If no number is found, it returns 0.0
    enriched = parser_service.parse(raw_text)

    # 2. Verification: Check if the amount is missing or zero
    if enriched['amount'] <= 0:
        bot.reply_to(
            message,
            "⚠️ *No amount detected.*\n"
            "Please include a price so I can log it correctly.\n"
            "Ex: `/add 45 Super-Pharm`",
            parse_mode="Markdown"
        )
        return

    # 3. Proceed only if verification passes
    send_transaction_ui(
        chat_id=message.chat.id,
        merchant=enriched['merchant'],
        amount=enriched['amount'],
        category=enriched['category'],
        payer=message.from_user.first_name
    )


@bot.callback_query_handler(func=lambda call: True)
def handle_ui_decision(call):
    try:
        print(f"[DEBUG] Button Pressed! Raw Data received: {call.data}")

        data_parts = call.data.split('|')
        print(f"[DEBUG] Split parts: {data_parts} (Count: {len(data_parts)})")

        if len(data_parts) < 5:
            print(
                f"[ERROR] Callback data is incomplete or corrupted: {call.data}")
            return

        action, merchant, amount, category, original_payer = data_parts
        db_split = "shared" if action == "shrd" else "personal"

        print(
            f"[DEBUG] Attempting to save: {merchant}, {amount}, {original_payer}, {db_split}")

        success = add_expense(
            merchant=merchant,
            amount=float(amount),
            payer=original_payer,
            split=db_split,
            category=category
        )

        if success:
            print(f"[SUCCESS] Transaction saved to database.")
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"✅ *Logged for {original_payer}*\n🏪 {merchant}... | ₪{amount} | {db_split}",
                parse_mode="Markdown"
            )
        else:
            print(f"[ERROR] database_manager.add_expense returned False.")

        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"[CRITICAL ERROR] In handle_ui_decision: {str(e)}")
        bot.answer_callback_query(call.id, "System Error. Check Logs.")

if __name__ == '__main__':
    # Used only for local debugging (PythonAnywhere uses the WSGI file)
    app.run(port=8000, debug=True)
