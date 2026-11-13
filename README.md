# BondsChecker

Telegram-бот, который напоминает о датах купонных выплат по облигациям.
График купонов берётся из MOEX ISS и кэшируется в SQLite.

Бот **не проверяет факт поступления денег**: он напоминает проверить выплату
и, если её нет, посмотреть сообщение эмитента о невыплате на
[e-disclosure.ru](https://www.e-disclosure.ru).

## Возможности

- `/start` — приветствие и создание подписки на напоминания в личке.
- `/add <название, ISIN или тикер>` — поиск бумаги в MOEX ISS и добавление
  в список. Массовый ввод: `/add RU000A10B4L9, SU26238RMFS4`.
- `/list` — добавленные бумаги.
- `/next` — ближайшие выплаты на 30 дней.
- Напоминания **за день** и **в день** выплаты в 10:00 МСК, одним дайджестом.
- Если бот был выключен в момент рассылки, при старте он досылает пропущенное
  (журнал `notifications_sent` защищает от дублей).
- Кэш купонов обновляется при добавлении бумаги, при старте и раз в неделю.

## Требования

- Python 3.12+
- Токен бота от [@BotFather](https://t.me/BotFather)

## Локальный запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r bond_notifier/requirements.txt
cp .env.example .env          # впишите BOT_TOKEN
cd bond_notifier
python main.py
```

Запускать нужно именно из каталога `bond_notifier`: импорты внутри проекта
не пакетные (`from config import ...`).

## Переменные окружения

| Переменная | Обязательна | По умолчанию | Назначение |
|---|---|---|---|
| `BOT_TOKEN` | да | — | токен Telegram-бота |
| `DB_PATH` | нет | `bond_notifier/bonds.db` | путь к файлу SQLite |
| `TIMEZONE` | нет | `Europe/Moscow` | часовой пояс планировщика |

`.env` читается из текущего каталога. Корневой сертификат для запросов к
MOEX подключается автоматически из `certifi`.

## Тесты и линт

```bash
pip install -r requirements-dev.txt
python -m pytest
ruff check bond_notifier tests
```

Тесты не обращаются к сети и используют временную БД.

## Docker

```bash
cp .env.example .env          # впишите BOT_TOKEN
docker compose up -d --build
docker compose logs -f
```

БД хранится в named volume `bonds_data` (`/data/bonds.db`), логи ограничены
ротацией в `docker-compose.yml`.

## systemd

Пошаговая инструкция — в [deploy/README.md](deploy/README.md).

## Структура

```
bond_notifier/
  main.py                 запуск бота, планировщик, стартовое обновление
  config.py               .env, BOT_TOKEN, MOEX_ISS_BASE, TIMEZONE, DB_PATH
  core/models.py          dataclass-модели
  core/database.py        SQLite: схема, портфель, кэш купонов, журнал отправок
  handlers/commands.py    /start, /add, /list, /next
  handlers/errors.py      глобальный error handler
  services/moex.py        MOEX ISS: поиск бумаг, график купонов
  services/cache.py       обновление кэша купонов
  services/notifier.py    дайджесты, досылка при старте
  services/formatting.py  форматирование сумм и дат
deploy/bondschecker.service
tests/
```

## Особенности данных MOEX

- Сумму в рублях берём из `value_rub`, валюту — из `faceunit`.
- У флоатеров будущие `value`/`value_rub` приходят пустыми — в сообщении
  будет «сумма будет определена».
- Пустой график купонов — не ошибка, а валидный ответ.
- Даты купонов московские, «сегодня» считается в `TIMEZONE`.
- Ошибка запроса к MOEX не обновляет `fetched_at`, поэтому бумага попадёт
  в следующее обновление кэша.
