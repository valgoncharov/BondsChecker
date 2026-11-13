# Деплой через systemd

Инструкция предполагает Debian/Ubuntu, каталог `/opt/bonds/app` и системного
пользователя `bonds`. Пути совпадают с `bondschecker.service`; при их
изменении поправьте unit.

## 1. Пользователь и каталог

```bash
sudo useradd --system --create-home --home-dir /opt/bonds bonds
sudo mkdir -p /opt/bonds/app
sudo chown -R bonds:bonds /opt/bonds
```

## 2. Код и зависимости

```bash
sudo -u bonds git clone git@github.com:valgoncharov/BondsChecker.git /opt/bonds/app
cd /opt/bonds/app
sudo -u bonds python3 -m venv .venv
sudo -u bonds .venv/bin/pip install -r bond_notifier/requirements.txt
```

## 3. Конфигурация

```bash
sudo -u bonds cp .env.example .env
sudo -u bonds editor .env          # впишите BOT_TOKEN
sudo chmod 600 .env
```

Файл `/opt/bonds/app/.env` подхватывается юнитом через `EnvironmentFile`.

## 4. Юнит

```bash
sudo cp deploy/bondschecker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bondschecker
sudo systemctl status bondschecker
```

Проверка логов:

```bash
journalctl -u bondschecker -f
```

## Обновление

```bash
cd /opt/bonds/app
sudo -u bonds git pull
sudo -u bonds .venv/bin/pip install -r bond_notifier/requirements.txt
sudo systemctl restart bondschecker
```

## Данные

SQLite лежит в `bond_notifier/bonds.db` (или в `DB_PATH`). Для бэкапа
достаточно остановить сервис и скопировать `bonds.db` вместе с `-wal`/`-shm`.
