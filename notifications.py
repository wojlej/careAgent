# notifications.py
import os
import json
import datetime
import config

def append_notification(event: str, description: str) -> None:
    """
    Dopisuje do pliku config.NOTIFICATION_HISTORY_FILE wpis:
    {
      "timestamp": ISO8601_UTC,
      "event": event,
      "description": description
    }
    """
    path = config.NOTIFICATION_HISTORY_FILE

    # Wczytaj istniejącą listę lub zainicjuj pustą
    notifications = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                notifications = json.load(f)
                if not isinstance(notifications, list):
                    notifications = []
        except json.JSONDecodeError:
            notifications = []

    # Stwórz nowy wpis
    entry = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "event": event,
        "description": description
    }
    notifications.append(entry)

    # Zapisz z powrotem
    with open(path, "w", encoding="utf-8") as f:
        json.dump(notifications, f, ensure_ascii=False, indent=2)
