"""
Centralized environment configuration for the AI Agent Orchestration Platform.
Loads variables from a .env file in the project root and provides typed defaults.
"""
import os
from dotenv import load_dotenv

# Load .env from the project root (one level above backend/)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))


# --- LLM API Keys ---
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")

# --- Messaging Channel Tokens ---
TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
SLACK_BOT_TOKEN: str = os.environ.get("SLACK_BOT_TOKEN", "")
WHATSAPP_ACCESS_TOKEN: str = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID: str = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_VERIFY_TOKEN: str = os.environ.get("WHATSAPP_VERIFY_TOKEN", "verify_me")

# --- Server Settings ---
API_HOST: str = os.environ.get("API_HOST", "127.0.0.1")
API_PORT: int = int(os.environ.get("API_PORT", "8000"))

# --- Default Model Settings ---
DEFAULT_MODEL_PROVIDER: str = os.environ.get("DEFAULT_MODEL_PROVIDER", "gemini")
DEFAULT_MODEL_NAME: str = os.environ.get("DEFAULT_MODEL_NAME", "gemini-2.5-flash")
