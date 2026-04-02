from telebot import types
from ai_parser import parser_service
from database_manager import add_expense


def send_transaction_ui(bot, chat_id, merchant, amount, category, payer):
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


def register_handlers(bot):
    @bot.message_handler(commands=['add'])
    def handle_manual_add(message):
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
