import os
import json
import logging
from typing import Dict, Any, Optional
from openai import OpenAI
from dotenv import load_dotenv

# Set up logging for production monitoring
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExpenseAIParser:
    """
    A service class to handle financial data extraction using LLMs.
    Optimized for messy Hebrew PDF text and expense classification.
    """

    # Model configuration
    MODEL_NAME = "gpt-4o"
    SUPPORTED_CATEGORIES = ["Food", "Transport", "Home", "Shopping", "Health",
                            "Leisure", "Other"]
    DEFAULT_CURRENCY = "ILS"

    def __init__(self):
        load_dotenv()
        self.api_key = self._get_api_key()
        self.client = OpenAI(api_key=self.api_key)

    def _get_api_key(self) -> str:
        """Retrieves the OpenAI API key from environment variables."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY missing from environment.")
            raise EnvironmentError("API Key not found.")
        return api_key

    def _get_system_prompt(self) -> str:
        categories_str = ", ".join(self.SUPPORTED_CATEGORIES)
        return (
            f"You are a strict financial data extractor for an Israeli user named Michael Ketash. "
            f"You will receive text containing an 'EMAIL BODY' and 'PDF CONTENT'. "
            f"Your mission is to identify if this is a valid expense and extract the details."
            f"\n\nSTRICT RULES:"
            f"\n1. MERCHANT IDENTIFICATION:"
            f"\n   - Check 'EMAIL BODY' for brand names (e.g., 'Wolt', 'Netflix', 'Ninja')."
            f"\n   - Check 'PDF CONTENT' for legal names (e.g., 'ח.פ', 'עוסק מורשה')."
            f"\n   - PRIORITIZE the brand/business name over the product name."
            f"\n   - IGNORE payment gateways like 'Tranzila', 'iCount', 'Cardcom', 'YaadPay', 'CreditGuard'."
            f"\n   - NEVER use 'Michael Ketash' as the merchant; he is the customer."
            f"\n2. HEBREW FIXING: If names in 'PDF CONTENT' are reversed (Visual Hebrew), you MUST flip them (e.g., 'לפא' -> 'אפל')."
            f"\n3. CATEGORIZATION: Map the expense ONLY to one of these: [{categories_str}]. Use 'Other' if unsure."
            f"\n4. AMOUNT: Extract the FINAL grand total to be paid as a float."
            f"\n5. VALIDATION: Set 'is_expense' to true ONLY if it's a clear financial transaction/bill."
            f"\n\nSTRICT JSON OUTPUT:"
            f"\n{{'is_expense': bool, 'merchant': str, 'amount': float, 'category': str}}"
        )

    def _clean_amount_value(self, raw_amount: Any) -> float:
        """Utility to convert various AI outputs into a clean float."""
        try:
            if raw_amount is None:
                return 0.0
            # Remove currency symbols and commas, then convert to float
            clean_str = str(raw_amount).replace('₪', '').replace(',',
                                                                 '').strip()
            return float(clean_str)
        except (ValueError, TypeError):
            return 0.0

    def _fetch_completion(self, user_input: str) -> Optional[str]:
        """Handles the API call to OpenAI."""
        try:
            response = self.client.chat.completions.create(
                model=self.MODEL_NAME,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user",
                     "content": f"Analyze this text: {user_input}"}
                ],
                response_format={"type": "json_object"}
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            return None

    def _sanitize_response(self, raw_json: Optional[str]) -> Dict[str, Any]:
        """Parses the AI's JSON output and applies default values/logic."""
        defaults = {
            "is_expense": False,
            "merchant": "Unknown",
            "amount": 0.0,
            "category": "Other",
            "currency": self.DEFAULT_CURRENCY
        }

        if not raw_json:
            return defaults

        try:
            parsed = json.loads(raw_json)
            # Ensure essential keys exist and amount is a valid float
            parsed["amount"] = self._clean_amount_value(parsed.get("amount"))
            parsed["is_expense"] = bool(parsed.get("is_expense", False))

            # Merge parsed data with defaults to ensure all keys are present
            return {**defaults, **parsed}

        except json.JSONDecodeError:
            logger.warning("AI returned invalid JSON. Using fallback defaults.")
            return defaults

    def parse(self, input_text: str) -> Dict[str, Any]:
        """
        The main entry point.
        Orchestrates fetching data from AI and sanitizing the result.
        """
        logger.info(f"Parsing input (Length: {len(input_text)})")
        raw_output = self._fetch_completion(input_text)
        return self._sanitize_response(raw_output)


# Global singleton instance
parser_service = ExpenseAIParser()