# config.py

import os

# ——————————————————————————————————————————————————————————
# Google Calendar
# ——————————————————————————————————————————————————————————
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
# ID kalendarza (np. 'primary' lub pełne calendarId)
CALENDAR_ID = os.getenv('CALENDAR_ID', 'primary')

PLAY_ON_BACKEND = os.getenv('PLAY_ON_BACKEND', 'False').lower() in ('true', '1', 'yes')

HISTORY_BAND_DATA_FILE = os.getenv('HISTORY_BAND_DATA_FILE', 'band_data.json')
TRANSCRIPT_HISTORY_FILE = os.getenv('TRANSCRIPT_HISTORY_FILE', 'transcript_history.json')
NOTIFICATION_HISTORY_FILE = os.getenv('NOTIFICATION_HISTORY_FILE', 'notification_history.json')

# Ścieżki do plików kredencjałów OAuth2
GOOGLE_CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json')
GOOGLE_TOKEN_FILE       = os.getenv('GOOGLE_TOKEN_FILE',       'token.json')

# ——————————————————————————————————————————————————————————
# OpenAI
# ——————————————————————————————————————————————————————————
# Klucz API OpenAI – najlepiej w ENV, fallback na wartość w pliku
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')

# Model do generowania tekstu
OPENAI_CHAT_MODEL_CALENDAR   = os.getenv('OPENAI_CHAT_MODEL',   'gpt-4.1')
# Model do TTS
OPENAI_TTS_MODEL    = os.getenv('OPENAI_TTS_MODEL',    'gpt-4o-mini-tts')
OPENAI_TTS_VOICE    = os.getenv('OPENAI_TTS_VOICE',    'coral')
OPENAI_TTS_FORMAT   = os.getenv('OPENAI_TTS_FORMAT',   'mp3')

# ——————————————————————————————————————————————————————————
# Scheduler
# ——————————————————————————————————————————————————————————
CHECK_INTERVAL_MINUTES = int(os.getenv('CHECK_INTERVAL_MINUTES', '1'))
REMINDER_TOLERANCE = int(os.getenv('REMINDER_TOLERANCE', '60'))  # ± tolerance in seconds
