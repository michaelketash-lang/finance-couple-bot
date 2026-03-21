import os
import telebot
from flask import Flask, request, jsonify
from telebot import types
from dotenv import load_dotenv

# Note: We are NOT importing database.py or ai_parser.py yet for this test
load_dotenv()

# Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
MY_CHAT_ID = os.getenv('MY_CHAT_ID')

bot = telebot.TeleBot(TELEGRAM_TOKEN)
app = Flask(__name__)


@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """
    Receives the 'tap' from your iPhone.
    Expected JSON: {"text": "...", "payer": "..."}
    """
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "No JSON"}), 400

    content = data.get('text', 'Test Transaction')
    payer = data.get('payer', 'Mike')

    # 1. Create the Inline Keyboard (The Buttons)
    markup = types.InlineKeyboardMarkup(row_width=2)

    # callback_data is the hidden string sent back to the server when clicked
    btn_shared = types.InlineKeyboardButton("Shared 🏠",
                                            callback_data="choice_shared")
    btn_personal = types.InlineKeyboardButton("Personal 👤",
                                              callback_data="choice_personal")

    markup.add(btn_shared, btn_personal)

    # 2. Send the message with buttons
    message_text = (
        f"💳 *Transaction Received*\n\n"
        f"👤 *Payer:* {payer}\n"
        f"📝 *Details:* {content}\n\n"
        f"How should we log this?"
    )

    bot.send_message(MY_CHAT_ID, message_text, reply_markup=markup,
                     parse_mode="Markdown")

    return jsonify({"status": "ui_triggered"}), 200


@bot.callback_query_handler(func=lambda call: True)
def handle_button_click(call):
    """
    This function runs when you tap 'Shared' or 'Personal' in Telegram.
    """
    # Identify which button was pressed
    if call.data == "choice_shared":
        result_label = "Shared ✅"
    else:
        result_label = "Personal 👤"

    # 3. Update the existing message to show the choice (UX improvement)
    # This replaces the buttons with a confirmation text
    final_text = f"{call.message.text}\n\n📍 *Decision:* {result_label}\n(Not saved to DB yet)"

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=final_text,
        parse_mode="Markdown"
    )

    # 4. Show a small "Toast" notification at the top of Telegram
    bot.answer_callback_query(call.id, f"Selection: {result_label}")

@app.route('/telegram', methods=['POST'])
def telegram_input():
    # 1. Grab the raw data
    json_string = request.get_data().decode('utf-8')

    # 2. THE TRIPWIRE: Force the raw payload into the PythonAnywhere error log
    app.logger.error(f"RAW TELEGRAM DATA: {json_string}")

    # 3. Process the update
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return jsonify({"status": "ok"}), 200

# 3. The Telegram Route
@bot.message_handler(commands=['add'])
def handle_manual_add(message):
    """
    Fires when you type: /add 50 Aroma
    """
    # 1. Strip out the command itself
    raw_text = message.text.replace('/add', '').strip()

    # 2. Check if they typed anything at all
    if not raw_text:
        bot.reply_to(message, "❌ Please provide details. Example: /add 50 Aroma")
        return

    # 3. Take it apart: Split the text into exactly two pieces (Amount and Merchant)
    # maxsplit=1 ensures that "50 Aroma Tel Aviv" splits into "50" and "Aroma Tel Aviv"
    parts = raw_text.split(maxsplit=1)

    if len(parts) < 2:
        bot.reply_to(message, "❌ Please include both an amount and a merchant. Example: /add 50 Aroma")
        return

    amount = parts[0]
    merchant = parts[1]

    # Optional but highly recommended: Verify the amount is actually a number
    try:
        float(amount)
    except ValueError:
        bot.reply_to(message, "❌ The amount must be a number. Example: /add 50 Aroma")
        return

    # 4. Create the buttons using your pipe format: action|merchant|amount
    markup = types.InlineKeyboardMarkup(row_width=2)

    # Slice merchant to 20 chars to guarantee we stay under Telegram's 64-byte limit
    safe_merchant = merchant[:20]

    cb_shared = f"btn_shrd|{safe_merchant}|{amount}"
    cb_personal = f"btn_priv|{safe_merchant}|{amount}"

    btn_shared = types.InlineKeyboardButton("Shared 🏠", callback_data=cb_shared)
    btn_personal = types.InlineKeyboardButton("Personal 👤", callback_data=cb_personal)
    markup.add(btn_shared, btn_personal)

    # 5. Build and send the response
    message_text = (
        f"📝 *Manual Entry Received*\n\n"
        f"👤 *Payer:* {message.from_user.first_name}\n"
        f"💰 *Amount:* ₪{amount}\n"
        f"🏪 *Merchant:* {merchant}\n\n"
        f"How should we log this?"
    )

    bot.send_message(
        message.chat.id,
        message_text,
        reply_markup=markup,
        parse_mode="Markdown"
    )
if __name__ == '__main__':
    app.run(port=8000, debug=True)
