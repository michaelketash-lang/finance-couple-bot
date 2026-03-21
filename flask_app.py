import os
import telebot
from flask import Flask, request, jsonify
from telebot import types
from dotenv import load_dotenv

# --- 1. SETUP & CONFIGURATION ---
# Load environment variables from .env file
load_dotenv()

# Get credentials from environment
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
MY_CHAT_ID = os.getenv('MY_CHAT_ID')

# Initialize Bot and Flask app
bot = telebot.TeleBot(TELEGRAM_TOKEN)
app = Flask(__name__)


# --- 2. WEBHOOK ROUTE (RECEIVER) ---
@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """
    Receives the structured data from the iOS Shortcut.
    Expected JSON: {"merchant": "...", "amount": "...", "payer": "..."}
    """
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "No JSON payload"}), 400

    # Extract data from the Shortcut request
    merchant = data.get('merchant', 'Unknown Store')
    amount = data.get('amount', '0.0')
    payer = data.get('payer', 'Michael')

    # Create the Inline Keyboard (The Buttons)
    markup = types.InlineKeyboardMarkup(row_width=2)

    # CRITICAL: Use a structured string for callback_data (max 64 bytes)
    # Format: action|merchant|amount
    cb_shared = f"btn_shrd|{merchant[:20]}|{amount}"
    cb_private = f"btn_priv|{merchant[:20]}|{amount}"

    btn_shared = types.InlineKeyboardButton("Shared 🏠", callback_data=cb_shared)
    btn_personal = types.InlineKeyboardButton("Personal 👤",
                                              callback_data=cb_private)

    markup.add(btn_shared, btn_personal)

    # Format the message text with Markdown
    message_text = (
        f"💳 *New Transaction Detected*\n\n"
        f"🏪 *Store:* `{merchant}`\n"
        f"💰 *Amount:* `₪{amount}`\n"
        f"👤 *Payer:* `{payer}`\n\n"
        f"Should we split this expense?"
    )

    # Send message to the Telegram group/chat
    bot.send_message(MY_CHAT_ID, message_text, reply_markup=markup,
                     parse_mode="Markdown")

    return jsonify({"status": "success", "received": merchant}), 200


# --- 3. CALLBACK HANDLER (INTERACTION) ---
@bot.callback_query_handler(func=lambda call: True)
def handle_button_click(call):
    """
    Triggers when a user clicks 'Shared' or 'Personal'.
    Unpacks the merchant and amount from the callback_data.
    """
    try:
        # Unpack the data string: "action|merchant|amount"
        parts = call.data.split('|')
        action = parts[0]  # "btn_shrd" or "btn_priv"
        merchant = parts[1]
        amount = parts[2]

        # Determine the decision label
        if action == "btn_shrd":
            result_label = "Shared 🏠"
        else:
            result_label = "Personal 👤"

        # Update the UI: Reconstruct the message to confirm the choice
        final_text = (
            f"✅ *Transaction Finalized*\n\n"
            f"🏪 *Store:* {merchant}\n"
            f"💰 *Amount:* ₪{amount}\n\n"
            f"📍 *Decision:* {result_label}\n"
            f"_(Not saved to DB yet)_"
        )

        # Edit the original message to remove the buttons and show the result
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=final_text,
            parse_mode="Markdown"
        )

        # Answer the callback to remove the "loading" spinner on the button
        bot.answer_callback_query(call.id, f"Logged as {result_label}")

    except Exception as e:
        print(f"Error in callback: {e}")
        bot.answer_callback_query(call.id, "Error processing selection.")

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
    # Local development server (port 8000)
    app.run(port=8000, debug=True)
