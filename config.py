import os
from dotenv import load_dotenv

# Force reload in case of changes
load_dotenv(override=True)

BOT_TOKEN = os.getenv("BOT_TOKEN")
try:
    ADMIN_ID = 7995476485
except (TypeError, ValueError):
    print("❌ ERROR: ADMIN_ID not found in .env or invalid!")
    ADMIN_ID = 0 # Prevent immediate crash to see error log
GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
CITY = os.getenv("CITY", "Moscow")

# Fallback AI Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# UserBot Sync
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
PAYMENT_TOKEN = os.getenv("PAYMENT_TOKEN")
WEBAPP_URL = "https://4riz7.github.io/4riz-github.io/index.html?v=2.0"
