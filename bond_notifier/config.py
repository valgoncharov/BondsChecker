import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN не задан. Добавьте его в .env (в корне проекта или в "
        "bond_notifier/) либо в переменные окружения."
    )

# MOEX ISS — бесплатный, авторизация не нужна для базовых данных
MOEX_ISS_BASE = "https://iss.moex.com/iss"

# Абсолютный путь к БД, чтобы не зависеть от текущего каталога запуска.
# Переопределяется переменной окружения DB_PATH.
DB_PATH = os.getenv(
    "DB_PATH",
    str(Path(__file__).resolve().parent / "bonds.db"),
)
