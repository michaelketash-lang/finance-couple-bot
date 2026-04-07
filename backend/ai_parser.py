"""
ai_parser.py
============

LLM-powered expense parser for extracting structured financial data from
unstructured text (Hebrew PDFs, email bodies, or direct user messages).

Uses OpenAI GPT-4o to classify each input as an expense or not, and to
extract merchant name, amount, and category from the 10 predefined categories.

Exposes a module-level singleton ``parser_service`` for use across the app.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from openai import OpenAI
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExpenseAIParser:
    """Parse financial data from unstructured text using an LLM.

    Optimized for messy Hebrew PDF text and expense classification.
    """

    MODEL_NAME = "gpt-4o"
    SUPPORTED_CATEGORIES = ["Groceries", "Eating Out", "Transport", "Utilities", "Rent",
                            "Maintenance", "Shopping", "Health", "Leisure", "Other"]
    DEFAULT_CURRENCY = "ILS"

    def __init__(self) -> None:
        """Initialize the parser and validate the OpenAI API key."""
        load_dotenv()
        self.api_key = self._get_api_key()
        self.client = OpenAI(api_key=self.api_key)

    def _get_api_key(self) -> str:
        """Retrieve the OpenAI API key from environment variables.

        :returns: The API key string.
        :raises EnvironmentError: If ``OPENAI_API_KEY`` is not set.
        """
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY missing from environment.")
            raise EnvironmentError("API Key not found.")
        return api_key

    def _get_system_prompt(self) -> str:
        """Build the system prompt that defines extraction rules and category definitions.

        :returns: A multi-line instruction string for the model, including
                  all 10 category definitions and strict output rules.
        """
        categories_desc = (
            "- Groceries: Supermarkets, Rami Levy, Shufersal, AM:PM, Victory, Local grocery stores.\n"
            "- Eating Out: Restaurants, Wolt, Ten Bis, Coffee shops, Bars, Pizza, Deliveries.\n"
            "- Transport: Fuel, Bus (Rav-Kav), Train, Parking (Pango/Cellopark), Car insurance/repairs.\n"
            "- Utilities: Electricity (IEC), Water (Gihon/Mekorot), Gas, Internet, Cell phone bills.\n"
            "- Rent: Monthly rent payments.\n"
            "- Maintenance: Building committee (Va'ad Bayit), Home repairs, Hardware stores (Tambour), Cleaning supplies.\n"
            "- Shopping: Clothes, Shoes, Electronics, Amazon, Gifts, Household items.\n"
            "- Health: Pharmacy (Super-Pharm/Be), Doctor visits, Health insurance (Kupat Holim), Dentist.\n"
            "- Leisure: Cinema, Hobbies, Vacation, Gym/Sports, Subscriptions (Netflix/Spotify).\n"
            "- Other: Any transaction that absolutely doesn't fit (e.g., Bank fees, broad insurance)."
        )

        payer_1 = os.getenv('PAYER_1', 'Payer1')
        payer_2 = os.getenv('PAYER_2', 'Payer2')

        return (
            f"You are a strict financial data extractor for a household expense tracker. "
            f"You will receive text from an EMAIL, a PDF document, or a DIRECT USER MESSAGE."
            f"Your mission is to identify if this is a valid expense and extract the details."
            f"\n\nSTRICT CATEGORIES TO USE:\n{categories_desc}"
            f"\n\nSTRICT RULES:"
            f"\n1. MERCHANT IDENTIFICATION:"
            f"\n   - Check 'EMAIL BODY' for brand names (e.g., 'Wolt', 'Netflix', 'Ninja')."
            f"\n   - Check 'PDF CONTENT' for legal names (e.g., 'ח.פ', 'עוסק מורשה')."
            f"\n   - PRIORITIZE the brand/business name over the product name."
            f"\n   - IGNORE payment gateways like 'Tranzila', 'iCount', 'Cardcom', 'YaadPay', 'CreditGuard'."
            f"\n   - NEVER use '{payer_1}' or '{payer_2}' as the merchant; they are the customers."
            f"\n2. HEBREW FIXING: If names in 'PDF CONTENT' are reversed (Visual Hebrew), you MUST flip them (e.g., 'לפא' -> 'אפל')."
            f"\n3. CATEGORIZATION: Map the expense ONLY to one of the 10 categories above. Use 'Other' only if unsure."
            f"\n4. AMOUNT: Extract the FINAL grand total to be paid as a float."
            f"\n5. VALIDATION: Set 'is_expense' to true ONLY if it's a clear financial transaction, bill, or purchase."
            f"\n\nSTRICT JSON OUTPUT:"
            f"\n{{'is_expense': bool, 'merchant': str, 'amount': float, 'category': str}}"
        )

    def _clean_amount_value(self, raw_amount: Any) -> float:
        """Convert various AI amount outputs into a clean float.

        :param raw_amount: Raw value from the AI response (may include currency symbols or commas).
        :returns: A clean float, or ``0.0`` if conversion fails.
        """
        try:
            if raw_amount is None:
                return 0.0
            # Strip shekel symbol and thousands separators before casting
            clean_str = str(raw_amount).replace('₪', '').replace(',', '').strip()
            return float(clean_str)
        except (ValueError, TypeError):
            return 0.0

    def _fetch_completion(self, user_input: str) -> Optional[str]:
        """Send the input text to OpenAI and return the raw JSON string response.

        :param user_input: The raw text to analyze (email body, PDF text, or user message).
        :returns: Raw JSON string from the model, or ``None`` if the API call fails.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.MODEL_NAME,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": f"Analyze this text: {user_input}"}
                ],
                response_format={"type": "json_object"}  # Forces valid JSON output from the model
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            return None

    def _sanitize_response(self, raw_json: Optional[str]) -> Dict[str, Any]:
        """Parse the AI's JSON output and apply safe defaults for missing or invalid fields.

        :param raw_json: Raw JSON string returned by the model, or ``None`` on failure.
        :returns: A dict with guaranteed keys: ``is_expense``, ``merchant``,
                  ``amount``, ``category``, ``currency``.
        """
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
            parsed["amount"] = self._clean_amount_value(parsed.get("amount"))
            parsed["is_expense"] = bool(parsed.get("is_expense", False))
            # Merge with defaults so all keys are always present
            return {**defaults, **parsed}
        except json.JSONDecodeError:
            logger.warning("AI returned invalid JSON. Using fallback defaults.")
            return defaults

    def parse(self, input_text: str) -> Dict[str, Any]:
        """Extract structured expense data from raw input text.

        :param input_text: Raw text from an email, PDF, or direct user message.
        :returns: A dict with keys ``is_expense``, ``merchant``, ``amount``,
                  ``category``, and ``currency``.
        """
        logger.info(f"Parsing input (Length: {len(input_text)})")
        raw_output = self._fetch_completion(input_text)
        return self._sanitize_response(raw_output)


# Global singleton — avoids re-initializing the OpenAI client on every request
parser_service = ExpenseAIParser()