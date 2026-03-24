import os
import json
import logging
from openai import OpenAI
from dotenv import load_dotenv
from database_manager import get_ai_context_data
import sqlite3
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

            # 3. ACTION: Save the insight into the database
            self._save_to_database(insight_text, insight_type)

            # 3. Send to Telegram (The Megaphone)
            self.send_to_telegram(insight_text, insight_type)

        except Exception as e:
            logger.error(f"Post-processing failed: {e}")

    def _save_to_database(self, text, insight_type):
        try:
            with sqlite3.connect('finance_bot.db') as conn:
                cursor = conn.cursor()
                # matches the table you created in database_manager.py [cite: 1]
                sql = "INSERT INTO ai_insights (insight, type, isread) VALUES (?, ?, ?)"
                cursor.execute(sql, (text, insight_type, False))
                conn.commit()
            logger.info("✅ Insight saved to finance_bot.db")
        except sqlite3.Error as e:
            logger.error(f"❌ Database error: {e}")

    def send_to_telegram(self, insight_text, insight_type):
        """
        Sends the generated insight directly to your Telegram chat.
        """
        import requests

        # 1. Get credentials from .env
        bot_token = os.getenv("TELEGRAM_TOKEN")
        chat_id = os.getenv("MY_CHAT_ID")

        if not bot_token or not chat_id:
            logger.error("Telegram credentials missing in .env. Skipping message.")
            return

        # 2. Format the "Telegram Prompt" (The visual template)
        icons = {
            "alert": "🚨 *FINANCIAL ALERT* 🚨",
            "praise": "🥳 *GOOD NEWS* 🥳",
            "summary": "📊 *WEEKLY SUMMARY* 📊"
        }
        header = icons.get(insight_type, "💡 *NEW INSIGHT*")

        # Use Markdown for bold text
        telegram_message = f"{header}\n\n{insight_text}"

        # 3. Send the request to Telegram's API
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": telegram_message,
            "parse_mode": "Markdown"  # This allows the bold stars to work
        }

        try:
            response = requests.post(url, data=payload)
            if response.status_code == 200:
                logger.info("🚀 Insight sent to Telegram!")
            else:
                logger.error(f"Telegram failed: {response.text}")
        except Exception as e:
            logger.error(f"Connection error to Telegram: {e}")

if __name__ == "__main__":
    agent = FinancialInsightsAgent()
    agent.generate_insight()