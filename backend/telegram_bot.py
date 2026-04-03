"""
telegram_bot.py
===============

Telegram bot UI and message handlers for the finance bot.

Provides a shared/personal split decision UI sent after each detected transaction,
a ``/add`` command for manual expense entry, and a callback handler that saves
the confirmed expense to the database.
"""

import os
from telebot import types
from ai_parser import parser_service
from database_manager import add_expense

PAYER_1 = os.getenv('PAYER_1', 'Michael')
PAYER_2 = os.getenv('PAYER_2', 'Ori')


def send_transaction_ui(bot, chat_id: str | int, merchant: str, amount: float,
                        category: str, payer: str) -> None:
    """Send an inline keyboard message asking the user to choose a split type.

    Encodes transaction data into the callback payload using ``|`` as a delimiter.
    Fields are sanitized and truncated to stay within Telegram's 64-byte callback limit.

    :param bot: The ``telebot.TeleBot`` instance to send the message with.
    :param chat_id: Telegram chat ID to send the message to.
    :param merchant: Merchant name extracted by the AI parser.
    :param amount: Transaction amount in ILS.
    :param category: Expense category assigned by the AI parser.
    :param payer: Name of the person who made the transaction.
    """
    markup = types.InlineKeyboardMarkup(row_width=2)

    # Sanitize fields to prevent delimiter collisions and cap length for callback byte limit
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


def register_handlers(bot) -> None:
    """Register all Telegram message and callback handlers on the bot instance.

    :param bot: The ``telebot.TeleBot`` instance to register handlers on.
    """

    @bot.message_handler(commands=['add'])
    def handle_manual_add(message):
        """Handle the ``/add`` command for manual expense entry.

        Parses the text after ``/add`` through the AI parser and sends
        the split decision UI if a valid amount is detected.
        """
        raw_text = message.text.replace('/add', '').strip()

        if not raw_text:
            bot.reply_to(message, "❌ Please provide details. Ex: `/add 50 Aroma`")
            return

        enriched = parser_service.parse(raw_text)

        if enriched['amount'] <= 0:
            bot.reply_to(
                message,
                "⚠️ *No amount detected.*\n"
                "Please include a price so I can log it correctly.\n"
                "Ex: `/add 45 Super-Pharm`",
                parse_mode="Markdown"
            )
            return

        send_transaction_ui(
            bot=bot,
            chat_id=message.chat.id,
            merchant=enriched['merchant'],
            amount=enriched['amount'],
            category=enriched['category'],
            payer=message.from_user.first_name
        )

    @bot.callback_query_handler(func=lambda call: True)
    def handle_ui_decision(call):
        """Handle the shared/personal button press from the transaction UI.

        Parses the ``|``-delimited callback payload, saves the expense to the
        database, and updates the original message to confirm the logged entry.
        """
        try:
            print(f"[DEBUG] Button Pressed! Raw Data received: {call.data}")

            data_parts = call.data.split('|')
            print(f"[DEBUG] Split parts: {data_parts} (Count: {len(data_parts)})")

            if len(data_parts) < 5:
                print(f"[ERROR] Callback data is incomplete or corrupted: {call.data}")
                return

            action, merchant, amount, category, original_payer = data_parts
            db_split = "shared" if action == "shrd" else "personal"

            print(f"[DEBUG] Attempting to save: {merchant}, {amount}, {original_payer}, {db_split}")

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