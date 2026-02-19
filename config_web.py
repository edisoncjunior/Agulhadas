import os
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()

# ==========================
# TELEGRAM
# ==========================
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("TELEGRAM_SESSION_STRING")

telegram_client = TelegramClient(
    StringSession(SESSION_STRING),
    API_ID,
    API_HASH
)

SOURCE_CHAT_ID = int(os.getenv("SOURCE_CHAT_ID"))
TARGET_CHAT_ID = int(os.getenv("TARGET_CHAT_ID"))

# ==========================
# WEBHOOK LOCAL EXECUTOR
# ==========================
EXECUTOR_URL = os.getenv("EXECUTOR_URL")
EXECUTOR_TOKEN = os.getenv("EXECUTOR_TOKEN")
