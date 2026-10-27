import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

# MOEX ISS — бесплатный, авторизация не нужна для базовых данных
MOEX_ISS_BASE = "https://iss.moex.com/iss"