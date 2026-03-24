import os
import telebot
from flask import Flask, request, jsonify
from telebot import types
from dotenv import load_dotenv

# Internal module imports
from ai_parser import parser_service
from database_manager import add_expense
from gmail_processor import gmail_engine

# Load environment configuration
load_dotenv()

# Global configuration from environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
MY_CHAT_ID = os.getenv('MY_CHAT_ID')

# Initialize Flask app and Telegram bot
app = Flask(__name__)
bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)

# In-memory set to prevent double-processing of the same Gmail notification
processed_emails = set()


# --- HELPER FUNCTIONS ---

def send_transaction_ui(chat_id, merchant, amount, category, payer):
    """
    Constructs and sends an interactive Telegram message with action buttons.
    This ensures a consistent UI for manual, email, and card entries.
    """
    markup = types.InlineKeyboardMarkup(row_width=2)

    # Callback data protocol: action|merchant|amount|category
    # Note: Telegram limits callback data to 64 bytes
    cb_shared = f"shrd|{merchant[:15]}|{amount}|{category}"
    cb_priv = f"priv|{merchant[:15]}|{amount}|{category}"

    markup.add(
        types.InlineKeyboardButton("Shared 🏠", callback_data=cb_shared),
        types.InlineKeyboardButton("Personal 👤", callback_data=cb_priv)
    )

    message_text = (
        f"💳 *New Transaction Detected*\n\n"
        f"🏪 *Store:* `{merchant}`\n"
        f"💰 *Amount:* `₪{amount}`\n"
        f"📂 *Category:* `{category}`\n"
        f"👤 *Payer:* `{payer}`\n\n"
        f"Should we split this expense?"
    )

    bot.send_message(chat_id, message_text, reply_markup=markup,
                     parse_mode="Markdown")


def process_text_and_notify(raw_text, payer, chat_id=MY_CHAT_ID):
    """
    Orchestrates the AI parsing and Telegram notification logic.
    Returns True if an expense was detected and notified, False otherwise.
    """
    # Layer 2 Filter: AI Classification
    enriched = parser_service.parse(raw_text)

    if not enriched.get('is_expense', False):
        print(f"DEBUG: AI determined content is NOT an expense. Skipping.")
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


# --- TELEGRAM BOT HANDLERS ---

@bot.message_handler(commands=['add'])
def handle_manual_entry(message):
    """
    Processes manual text entries from the user via the /add command.
    Example: /add 150 Grocery Store
    """
    user_text = message.text.replace('/add', '').strip()
    if not user_text:
        bot.reply_to(message,
                     "❌ Please provide details. Example: `/add 50 Aroma`")
        return

    process_text_and_notify(user_text, payer=message.from_user.first_name,
                            chat_id=message.chat.id)


@bot.callback_query_handler(func=lambda call: True)
def handle_ui_decision(call):
    """
    Processes the user's click on 'Shared' or 'Personal' buttons.
    Saves the finalized transaction to the database.
    """
    try:
        # Unpack callback data (action|merchant|amount|category)
        data_parts = call.data.split('|')
        action, merchant, amount, category = data_parts[0], data_parts[1], \
        data_parts[2], data_parts[3]

        # Map UI action to DB split type
        db_split = "shared" if action == "shrd" else "personal"

        # Persistence layer: Save to SQL database
        success = add_expense(
            merchant=merchant,
            amount=float(amount),
            payer=call.from_user.first_name,
            split=db_split,
            category=category
        )

        if success:
            result_tag = "Shared 🏠" if db_split == "shared" else "Personal 👤"
            final_confirmation = (
                f"✅ *Transaction Logged*\n\n"
                f"🏪 *Store:* {merchant}\n"
                f"💰 *Amount:* ₪{amount}\n"
                f"📂 *Category:* {category}\n"
                f"📍 *Type:* {result_tag}"
            )
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=final_confirmation,
                parse_mode="Markdown"
            )

        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"Error handling button click: {e}")
        bot.answer_callback_query(call.id, "Error saving transaction.")


if __name__ == '__main__':
    # Used only for local debugging (PythonAnywhere uses the WSGI file)
    app.run(port=8000, debug=True)