import os
import telebot
from flask import Flask, request, jsonify
from telebot import types
from dotenv import load_dotenv
from ai_parser import parser_service
from database_manager import add_expense

# Load environment variables from .env file
load_dotenv()

# Get credentials from environment
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
MY_CHAT_ID = os.getenv('MY_CHAT_ID')

# Initialize Bot and Flask app
bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)
app = Flask(__name__)


def send_transaction_ui(chat_id, merchant, amount, category, payer):
    """
    Unified function to generate the UI.
    It ensures the message looks identical whether it came from a shortcut or manual entry.
    """
    markup = types.InlineKeyboardMarkup(row_width=2)

    # IMPORTANT: We add the 'category' to the callback data string.
    # Protocol: action|merchant|amount|category (Max 64 bytes)
    cb_shared = f"shrd|{merchant[:15]}|{amount}|{category}"
    cb_priv = f"priv|{merchant[:15]}|{amount}|{category}"

    markup.add(
        types.InlineKeyboardButton("Shared 🏠", callback_data=cb_shared),
        types.InlineKeyboardButton("Personal 👤", callback_data=cb_priv)
    )

    message_text = (
        f"💳 *New Transaction Detected*\n\n"
        f"🏪 *Store:* `{merchant}`\n"
        f"💰 *Amount:* `{amount}`\n"
        f"📂 *Category:* `{category}`\n"
        f"👤 *Payer:* `{payer}`\n\n"
        f"Should we split this expense?"
    )

    bot.send_message(chat_id, message_text, reply_markup=markup,
                     parse_mode="Markdown")


@app.route('/webhook', methods=['POST'])
def handle_webhook():
    data = request.json
    if not data: return jsonify({"status": "error"}), 400

    raw_merchant = data.get('merchant', 'Unknown')
    amount = data.get('amount', '0.0')
    payer = data.get('payer', 'Michael')

    # Data Enrichment: Use AI to clean the name and get a category
    enriched = parser_service.parse(raw_merchant)

    send_transaction_ui(
        chat_id=MY_CHAT_ID,
        merchant=enriched['merchant'],
        amount=amount,  # Use exact amount from the card
        category=enriched['category'],
        payer=payer
    )

    return jsonify({"status": "success"}), 200


@app.route('/telegram', methods=['POST'])
def telegram_webhook_entry():
    """
    Essential route for PythonAnywhere.
    Listens to incoming Telegram updates and forwards them to the bot handlers.
    """
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    return jsonify({"error": "Unauthorized"}), 403


@bot.message_handler(commands=['add'])
def handle_manual_add(message):
    raw_text = message.text.replace('/add', '').strip()

    if not raw_text:
        bot.reply_to(message, "❌ Please provide details. Ex: `/add 50 Aroma`")
        return

    # The AI Brain does the heavy lifting of extracting amount and merchant
    enriched = parser_service.parse(raw_text)

    send_transaction_ui(
        chat_id=message.chat.id,
        merchant=enriched['merchant'],
        amount=enriched['amount'],
        category=enriched['category'],
        payer=message.from_user.first_name
    )


@bot.callback_query_handler(func=lambda call: True)
def handle_button_click(call):
    try:
        # 1. Unpack the parameters from the callback string
        parts = call.data.split('|')
        action, merchant, amount, category = parts[0], parts[1], parts[2], parts[3]

        # 2. Map actions to your database 'CHECK' constraints
        # Your DB expects 'shared' or 'personal'
        db_split = "shared" if action == "shrd" else "personal"

        # 3. Get the Payer (The user who clicked the button)
        payer = call.from_user.first_name

        # 4. Attempt to save to the database
        success = add_expense(
            merchant=merchant,
            amount=float(amount),
            payer=payer,
            split=db_split,
            category=category
        )

        # 5. Update UI based on success or failure
        if success:
            result_label = "Shared 🏠" if db_split == "shared" else "Personal 👤"
            final_text = (
                f"✅ *Transaction Saved*\n\n"
                f"🏪 *Store:* {merchant}\n"
                f"💰 *Amount: ₪* {amount}\n"
                f"📂 *Category:* {category}\n"
                f"📍 *Decision:* {result_label}"
            )
        else:
            final_text = "❌ *Database Error*\nCould not save to expenses.db."

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=final_text,
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id, f"Logged as {result_label}")

    except Exception as e:
        print(f"Error: {e}")
        bot.answer_callback_query(call.id, "Error processing selection.")

if __name__ == '__main__':
    app.run(port=8000, debug=True)
