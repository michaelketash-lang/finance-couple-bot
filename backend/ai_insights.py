"""
ai_insights.py
==============

Scheduled AI agent that generates financial insights from recent spending data.
Retrieves the last 14 days of financial context, sends it to OpenAI GPT-4o-mini,
saves the resulting insight to the local SQLite database, and forwards it to the
configured Telegram chat.
"""

import os
import json
import logging
from openai import OpenAI
from dotenv import load_dotenv
from database_manager import get_ai_context_data
import sqlite3
import datetime
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FinancialInsightsAgent:
    """The AI brain of the finance bot.

    Retrieves formatted financial context and generates actionable insights.
    """

    def __init__(self) -> None:
        """Initialize the agent and validate the OpenAI API key."""
        load_dotenv()
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise EnvironmentError("OPENAI_API_KEY not found in .env file.")

        self.client = OpenAI(api_key=self.api_key)
        self.model_name = "gpt-4o-mini"

    def _get_system_prompt(self) -> str:
        """Build the system prompt for the OpenAI chat completion.

        :returns: Instruction string telling the model to focus on variable
                  spending categories and return a JSON object with
                  ``insight`` and ``type`` keys.
        """
        return(
            "You are an expert, proactive financial assistant. "
            "Your job is to provide the user with ONE highly meaningful insight about their recent spending. "
            "IMPORTANT: Ignore 'Rent' and 'Bills' unless there is a massive, unexpected change in the amount. "
            "Focus your analysis on 'Variable' categories like Food, Leisure, Shopping, and Transport. "
            "Look for: "
            "1. Frequent small purchases at a specific merchant (e.g., too many Wolt orders). "
            "2. Categories where spending is accelerating faster than the historical average. "
            "3. Praise if the user is significantly under-budget in a variable category. "
            "4. Single large expenses at the same store"
            "5. Pathetic displays of indiscipline"
            "Tone: Condescending and insulting"
            "OUTPUT FORMAT: Return a strict JSON object with two keys: "
            "'insight' (1-2 sentences) and 'type' ('alert', 'summary', or 'praise')."
        )

    def generate_insight(self) -> None:
        """Run the full agent loop: fetch data, query AI, save result, notify via Telegram.

        Follows a perceive → reason → act pattern:

        1. Fetches the last 14 days of financial data.
        2. Sends it to OpenAI for analysis.
        3. Saves the result to the database.
        4. Forwards the insight to Telegram.
        """
        logger.info("Gathering the last 14 days of financial data...")
        context_data = get_ai_context_data()
        context_json = json.dumps(context_data)

        logger.info("Sending data to OpenAI for analysis...")
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": f"Analyze this data: {context_json}"}
                ],
                response_format={"type": "json_object"}  # Forces valid JSON output from the model
            )

            raw_content = response.choices[0].message.content
            result = json.loads(raw_content)

            insight_text = result.get("insight")
            insight_type = result.get("type")

            logger.info(f"💡 AI Insight ({insight_type}): {insight_text}")

            insight_id = self._save_to_database(insight_text, insight_type)

            if insight_id:
                self.send_to_telegram(insight_id, insight_text, insight_type)

        except Exception as e:
            logger.error(f"Post-processing failed: {e}")

    def _save_to_database(self, text: str, insight_type: str) -> int | None:
        """Persist a generated insight to the ``ai_insights`` table.

        :param text: The insight text produced by the AI.
        :param insight_type: One of ``'alert'``, ``'summary'``, or ``'praise'``.
        :returns: The ``rowid`` of the newly inserted row, or ``None`` on failure.
        """
        try:
            with sqlite3.connect('finance_bot.db') as conn:
                cursor = conn.cursor()
                sql = "INSERT INTO ai_insights (insight, type, isread) VALUES (?, ?, ?)"
                cursor.execute(sql, (text, insight_type, False))
                conn.commit()
            logger.info("✅ Insight saved to finance_bot.db")
            return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"❌ Database error: {e}")
            return None

    def _mark_as_read(self, insight_id: int) -> None:
        """Mark an insight as read in the database.

        :param insight_id: Primary key of the insight to update.
        """
        try:
            with sqlite3.connect('finance_bot.db') as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE ai_insights SET isread = 1 WHERE id = ?", (insight_id,))
                conn.commit()
            logger.info(f"✅ Insight #{insight_id} marked as read in database.")
        except sqlite3.Error as e:
            logger.error(f"❌ Failed to mark insight as read: {e}")

    def send_to_telegram(self, insight_id: int, insight_text: str, insight_type: str) -> None:
        """Send a formatted insight message to the configured Telegram chat.

        :param insight_id: Database ID used to mark the insight as read after delivery.
        :param insight_text: The insight body to include in the message.
        :param insight_type: Controls the header icon (``'alert'``, ``'praise'``, ``'summary'``).
        """
        import requests

        bot_token = os.getenv("TELEGRAM_TOKEN")
        chat_id = os.getenv("MY_CHAT_ID")

        if not bot_token or not chat_id:
            logger.error("Telegram credentials missing. Skipping message.")
            return

        # Map insight type to a Telegram-formatted header with emoji
        icons = {
            "alert": "🚨 *FINANCIAL ALERT* 🚨",
            "praise": "🥳 *GOOD NEWS* 🥳",
            "summary": "📊 *WEEKLY SUMMARY* 📊"
        }
        header = icons.get(insight_type, "💡 *NEW INSIGHT*")
        telegram_message = f"{header}\n\n{insight_text}"

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": telegram_message,
            "parse_mode": "Markdown"
        }

        try:
            response = requests.post(url, data=payload)
            if response.status_code == 200:
                logger.info("🚀 Insight sent to Telegram!")
                self._mark_as_read(insight_id)
            else:
                logger.error(f"Telegram failed: {response.text}")
        except Exception as e:
            logger.error(f"Connection error to Telegram: {e}")


if __name__ == "__main__":
    today_ordinal = datetime.date.today().toordinal()

    if today_ordinal % 3 != 0:
        logger.info(f"Day {today_ordinal} is not the 3rd day. Returning to sleep...")
        sys.exit()

    logger.info("🧠 3-Day interval reached! Waking up the AI Agent...")
    agent = FinancialInsightsAgent()
    agent.generate_insight()
    logger.info("✅ Insight cycle complete.")
