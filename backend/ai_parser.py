import os
import json
import logging
from typing import Dict, Any, Optional
from openai import OpenAI
from dotenv import load_dotenv

# Set up logging - better than 'print' for production debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ExpenseAIParser:
    """
    A service class to handle financial data extraction using LLMs.
    """
    # Constants - Centralized configuration
    MODEL_NAME = "gpt-4o-mini"
    SUPPORTED_CATEGORIES = ["Food", "Transport", "Home", "Shopping", "Health",
                            "Leisure", "Other"]
    DEFAULT_CURRENCY = "ILS"

    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.error("OPENAI_API_KEY missing from environment.")
            raise EnvironmentError("API Key not found.")

        # Reusing the client across calls (Efficiency)
        self.client = OpenAI(api_key=self.api_key)

    def _get_system_prompt(self) -> str:
        categories_str = ", ".join(self.SUPPORTED_CATEGORIES)
        return (
            f"You are a financial assistant for an Israeli user. "
            f"Analyze transaction text and return a JSON object with: "
            f"'merchant' (Clean English name, e.g., 'Aroma Espresso Bar' instead of 'AROMA TEL AVIV'), "
            f"'amount' (Number, default 0.0 if not found), "
            f"'category' (One of: {categories_str}), "
            f"'currency' (Default 'ILS'). "
            f"If the input is just a merchant name, extract category and clean the name. "
            f"If the input includes a number, treat it as the amount."
        )

    def _fetch_completion(self, user_input: str) -> Optional[str]:
        """Handles the low-level API communication."""
        try:
            response = self.client.chat.completions.create(
                model=self.MODEL_NAME,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": f"Process: {user_input}"}
                ],
                response_format={"type": "json_object"}
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            return None

    def _sanitize_response(self, raw_json: Optional[str]) -> Dict[str, Any]:
        """Validates the AI output and applies business logic fallbacks."""
        # The 'Source of Truth' for our data structure
        pattern_defaults = {
            "merchant": "Unknown",
            "amount": 0.0,
            "category": "Other",
            "currency": self.DEFAULT_CURRENCY
        }

        if not raw_json:
            return pattern_defaults

        try:
            parsed_data = json.loads(raw_json)

            # Type Casting: Ensure amount is a float
            if "amount" in parsed_data and parsed_data["amount"] is not None:
                try:
                    parsed_data["amount"] = float(parsed_data["amount"])
                except ValueError:
                    parsed_data["amount"] = 0.0

            # Merge with defaults: {**defaults, **actual_data}
            # This ensures even if the AI misses a field, the app doesn't crash.
            return {**pattern_defaults, **parsed_data}

        except json.JSONDecodeError:
            logger.warning("AI returned invalid JSON. Using fallbacks.")
            return pattern_defaults

    def parse(self, input_text: str) -> Dict[str, Any]:
        """
        The Public Facade.
        flow from input to structured output.
        """
        logger.info(f"Processing input: {input_text}")
        raw_output = self._fetch_completion(input_text)
        return self._sanitize_response(raw_output)


# Singleton Pattern Instance
parser_service = ExpenseAIParser()
