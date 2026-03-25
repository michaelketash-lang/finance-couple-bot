import os
import json
import logging
from openai import OpenAI
from dotenv import load_dotenv
from database_manager import get_ai_context_data
import sqlite3
import datetime
import sys
# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FinancialInsightsAgent:
    """
    The 'Brain' of the finance bot.
    Retrieves formatted financial context and generates actionable insights.
    """

    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise EnvironmentError("OPENAI_API_KEY not found in .env file.")

        self.client = OpenAI(api_key=self.api_key)
        self.model_name = "gpt-4o-mini"

        from database_manager import setup_database
        setup_database() # This ensures all tables exist!

    def _get_system_prompt(self):
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
    def generate_insight(self):
        """
        The main Agent loop:
        1. Perception (Get Data)
        2. Reasoning (Talk to AI)
        3. Action (Save to DB)
        """
        # 1. PERCEPTION: Get the last 14 days of data
        logger.info("Gathering the last 14 days of financial data...")
        context_data = get_ai_context_data()

        # Convert the Python dictionary to a string so the AI can read it
        context_json = json.dumps(context_data)

        # 2. REASONING: Send the data to OpenAI
        logger.info("Sending data to OpenAI for analysis...")
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": f"Analyze this data: {context_json}"}
                ],
                # This ensures the AI returns a JSON object we can parse
                response_format={"type": "json_object"}
            )

            # Parse the text response back into a Python dictionary
            raw_content = response.choices[0].message.content
            result = json.loads(raw_content)

            insight_text = result.get("insight")
            insight_type = result.get("type")

            logger.info(f"💡 AI Insight ({insight_type}): {insight_text}")

            # 3. ACTION: Save the insight into the database and get the ID
            insight_id = self._save_to_database(insight_text, insight_type)

            # 4. ACTION: Trigger Telegram
            if insight_id:
                self.send_to_telegram(insight_id, insight_text, insight_type)

        except Exception as e:
            logger.error(f"Post-processing failed: {e}")

    def _save_to_database(self, text, insight_type):
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

    def _mark_as_read(self, insight_id):
        """A helper function to update the DB status."""
        try:
            with sqlite3.connect('finance_bot.db') as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE ai_insights SET isread = 1 WHERE id = ?", (insight_id,))
                conn.commit()
            logger.info(f"✅ Insight #{insight_id} marked as read in database.")
        except sqlite3.Error as e:
            logger.error(f"❌ Failed to mark insight as read: {e}")

    def send_to_telegram(self, insight_id, insight_text, insight_type):
        """
        Pure worker function: Receives data, sends it, and triggers the DB update.
        """
        import requests

        bot_token = os.getenv("TELEGRAM_TOKEN")
        chat_id = os.getenv("MY_CHAT_ID")

        if not bot_token or not chat_id:
            logger.error("Telegram credentials missing. Skipping message.")
            return

        # Format the visual template
        icons = {
            "alert": "🚨 *FINANCIAL ALERT* 🚨",
            "praise": "🥳 *GOOD NEWS* 🥳",
            "summary": "📊 *WEEKLY SUMMARY* 📊"
        }
        header = icons.get(insight_type, "💡 *NEW INSIGHT*")
        telegram_message = f"{header}\n\n{insight_text}"

        # Send to Telegram
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

                # Trigger the tiny helper function we just made
                self._mark_as_read(insight_id)
            else:
                logger.error(f"Telegram failed: {response.text}")
        except Exception as e:
            logger.error(f"Connection error to Telegram: {e}")


if __name__ == "__main__":
    # ---------------------------------------------------------
    # The 5-Minute Gatekeeper (For Testing)
    # Looks at the current minute (0-59).
    # Modulo 5 (% 5) ensures it only proceeds on the 0, 5, 10, 15... minute marks.
    # ---------------------------------------------------------
    current_minute = datetime.datetime.now().minute

    if current_minute % 5 != 0:
        logger.info(f"Current minute is {current_minute}. Not a 5-minute interval. Sleeping...")
        sys.exit()  # Stops the script immediately

    # If it IS a 5-minute mark, wake up the Agent!
    logger.info("🧠 5-minute mark reached! Waking up the AI Agent Test...")
    agent = FinancialInsightsAgent()
    agent.generate_insight()
    logger.info("✅ Pipeline complete.")