# app.py

from flask import Flask, jsonify, request, render_template
import io
import os
import asyncio
import numpy as np
import soundfile as sf
from dateutil import parser
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from openai import OpenAI
from datetime import datetime, timezone, timedelta

from flask_cors import CORS
from dotenv import load_dotenv

import config
import time
import ffmpeg
import json
import random
import notifications

from audio_handler import handle_audio
from voice_agents import voice_handler
# ——————————————————————————————————————————————————————————
# Inicjalizacja klienta OpenAI
# ——————————————————————————————————————————————————————————
client = OpenAI(api_key=config.OPENAI_API_KEY)

# ——————————————————————————————————————————————————————————
# Funkcje pomocnicze
# ——————————————————————————————————————————————————————————

def get_calendar_service():
    creds = None
    if os.path.exists(config.GOOGLE_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(config.GOOGLE_TOKEN_FILE, config.SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(config.GOOGLE_CREDENTIALS_FILE, config.SCOPES)
        creds = flow.run_local_server(port=0)
        with open(config.GOOGLE_TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    return build('calendar', 'v3', credentials=creds)

def generate_event_message(summary: str, start: str) -> str:
    prompt = (
    f"Create a short, friendly reminder for the event '{summary}', "
    f"which will take place on {start}."
)
    resp = client.chat.completions.create(
        model=config.OPENAI_CHAT_MODEL_CALENDAR,
        messages=[
            {"role": "system", "content": "You are a helpful assistant for old people."},
            {'role': 'user', 'content': prompt}
        ]
    )
    return resp.choices[0].message.content.strip()


def parse_datetime(dt_str: str) -> datetime:
    return parser.isoparse(dt_str)

# ——————————————————————————————————————————————————————————
# Zadanie cykliczne
# ——————————————————————————————————————————————————————————

def fetch_next_reminders(count: int = 1):
    """
    Pobiera `count` najbliższych wydarzeń z Google Calendar w horyzoncie najbliższych 10 dni.
    Zwraca listę słowników: {summary, start, message }.
    Jeśli nie ma żadnych wydarzeń, zwraca pustą listę.
    """
    service = get_calendar_service()
    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    now_iso = now.isoformat()
    until_iso = (now + timedelta(days=10)).isoformat()

    # Pobieramy `count` najbliższych wydarzeń
    events_result = service.events().list(
        calendarId=config.CALENDAR_ID,
        timeMin=now_iso,
        timeMax=until_iso,
        singleEvents=True,
        orderBy='startTime',
        maxResults=count
    ).execute()
    items = events_result.get('items', [])
    print(f"Fetched {len(items)} events.")

    reminders = []
    for ev in items:
        summary   = ev.get('summary', '(Brak tytułu)')
        start_str = ev['start'].get('dateTime', ev['start'].get('date'))
        
        print(f"Event: {summary} at {start_str}")
        # Generujemy tekst i audio
        text = generate_event_message(summary, start_str)
        print(f"Generated message: {text}")
        #audio_b64 = handle_audio(text)

        reminders.append({
            "summary": summary,
            "start":   start_str,
            "message": text
        })

    return reminders


# ==========================================================

app = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(app)

@app.route("/api/tts", methods=["POST"])
def api_tts():
    """Generuje audio z tekstu i zwraca jako Base64."""
    text = request.json.get("text")
    if not text:
        return jsonify({"error": "Brak tekstu do przetworzenia"}), 400

    # 1) Generuj audio
    audio_b64 = handle_audio(text, play_on=True)

    # 2) Zwróć Base64
    return "", 200


@app.route("/api/voice", methods=["POST"])
def api_voice():
    audio_bytes = request.data

    # 2) Zapisz oryginał (do ręcznej inspekcji)
    ts = int(time.time())
    webm_path = os.path.join("uploads", f"rec_{ts}.webm")
    with open(webm_path, "wb") as f:
        f.write(audio_bytes)

    # 3) Konwersja WebM→WAV PCM16 24 kHz Mono
    in_buf = io.BytesIO(audio_bytes)
    wav_buf = io.BytesIO()

    out, err = (
        ffmpeg
        .input("pipe:0")
        .output(
            "pipe:1",
            format="wav",
            acodec="pcm_s16le",
            ac=1,
            ar="24000"
        )
        .run(
            capture_stdout=True,
            capture_stderr=True,
            input=in_buf.read(),
            overwrite_output=True
        )
    )
    # teraz 'out' to bajty z przekonwertowanym WAV-em
    wav_buf.write(out)
    wav_buf.seek(0)

    # 4) Wczytaj WAV do numpy
    try:
        audio_np, sr = sf.read(wav_buf, dtype="int16")
    except Exception as e:
        return jsonify({"error": f"Niepoprawny WAV po konwersji: {e}"}), 400

    # 5) Wywołaj Twój async handler — teraz podajesz KORUTYNĘ!
    try:
        ret = asyncio.run(voice_handler(audio_np))
    except Exception as e:
        return jsonify({"error": f"Handler wyrzucił wyjątek: {e}"}), 500

    # 6) Zwróć status OK
    print(f"Received: {ret}")

    # Przygotuj dane do zapisania
    data_to_save = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "output_transcript": ret.get('output_transcript', ''),
        "input_transcript": ret.get('input_transcript', ''),
    }

    # Wczytaj istniejące dane lub stwórz pustą listę
    if os.path.exists(config.TRANSCRIPT_HISTORY_FILE):
        with open(config.TRANSCRIPT_HISTORY_FILE, "r", encoding="utf-8") as f:
            try:
                existing_data = json.load(f)
                if not isinstance(existing_data, list):
                    existing_data = []
            except json.JSONDecodeError:
                existing_data = []
    else:
        existing_data = []

    # Dodaj nowe dane
    existing_data.append(data_to_save)

    # Zapisz całą listę z powrotem do pliku
    with open(config.TRANSCRIPT_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)

    return jsonify(ret), 200


@app.route('/api/reminders', methods=['GET'])
def api_get_reminders():
    n = request.args.get('n', default=1, type=int)
    if n < 1:
        n = 1
    reminders = fetch_next_reminders(count=n)
    return jsonify(reminders), 200


@app.route("/api/band_data", methods=["POST"])
def api_band_data():
    # 1) Wczytaj JSON z body (force=True, jeśli nagłówek nie jest ustawiony)
    try:
        data = request.get_json(force=True)
    except Exception as e:
        return jsonify({"error": f"Niepoprawny JSON: {e}"}), 400

    # 2) Wczytaj istniejącą historię, albo zainicjuj pustą listę
    history = []
    history_file = config.HISTORY_BAND_DATA_FILE

    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
                if not isinstance(history, list):
                    history = []
        except json.JSONDecodeError:
            history = []

    # 3) Dodaj nowy wpis
    entry = {
        "received_at": datetime.datetime.utcnow().isoformat() + "Z",
        "data":        data
    }
    history.append(entry)

    try:
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        return jsonify({"error": f"Nie udało się zapisać historii: {e}"}), 500

    print(f"Saved band entry: {entry}")
    return jsonify({"status": "OK"}), 200


@app.route('/api/inject_anomaly', methods=['POST'])
def inject_anomaly():
    # Wczytaj historię
    with open(config.HISTORY_BAND_DATA_FILE, 'r', encoding='utf-8') as f:
        history = json.load(f)

    # Wygeneruj anomalny wpis na podstawie ostatniego pomiaru lub całkowicie nowy
    last = history[-1] if history else {}
    new_entry = {
        "received_at": datetime.utcnow().isoformat() + "Z",
        "heart_rate": last.get('heart_rate', 80),
        "spo2": last.get('spo2', 98),
        "battery": last.get('battery', 100.0),
        "fall_detected": False
    }

    choice = random.choice(['hr_low', 'hr_high', 'spo2_low', 'fall'])
    if choice == 'hr_low':
        new_entry['heart_rate'] = random.randint(20, 35)
    elif choice == 'hr_high':
        new_entry['heart_rate'] = random.randint(130, 160)
    elif choice == 'spo2_low':
        new_entry['spo2'] = random.randint(78, 85)
    else:
        new_entry['fall_detected'] = True

    # Dodaj do historii
    history.append({"received_at": new_entry['received_at'], "heart_rate": new_entry['heart_rate'], "spo2": new_entry['spo2'], "battery": new_entry['battery'], "fall_detected": new_entry['fall_detected']})
    with open(config.HISTORY_BAND_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    return jsonify(new_entry), 200


@app.route('/api/notifications', methods=['GET'])
def api_notifications():
    """
    Zwraca listę wszystkich powiadomień zapisanych w config.NOTIFICATION_HISTORY_FILE.
    """
    path = config.NOTIFICATION_HISTORY_FILE
    if not os.path.exists(path):
        return jsonify([]), 200

    try:
        with open(path, "r", encoding="utf-8") as f:
            notifications_list = json.load(f)
            if not isinstance(notifications_list, list):
                notifications_list = []
    except Exception:
        notifications_list = []

    if os.path.exists(config.NOTIFICATION_HISTORY_FILE):
        os.remove(config.NOTIFICATION_HISTORY_FILE)

    return jsonify(notifications_list), 200


@app.route("/", methods=["GET"])
def index():
    if os.path.exists(config.TRANSCRIPT_HISTORY_FILE):
        os.remove(config.TRANSCRIPT_HISTORY_FILE)

    if os.path.exists(config.NOTIFICATION_HISTORY_FILE):
        os.remove(config.NOTIFICATION_HISTORY_FILE)

    return render_template("index.html")

if __name__ == '__main__':
    load_dotenv()
    app.run(host='0.0.0.0', port=5000)
