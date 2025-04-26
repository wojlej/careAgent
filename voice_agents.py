from agents import Agent, function_tool
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions
from agents.voice import (
    AudioInput,
    SingleAgentVoiceWorkflow,
    SingleAgentWorkflowCallbacks,
    VoicePipeline,
)
import requests
import json
import numpy as np
import numpy.typing as npt
import sounddevice as sd
import config
from notifications import append_notification


class AudioPlayer:
    def __enter__(self):
        self.stream = sd.OutputStream(samplerate=24000, channels=1, dtype=np.int16)
        self.stream.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stream.stop()  # wait for the stream to finish
        self.stream.close()

    def add_audio(self, audio_data: npt.NDArray[np.int16]):
        self.stream.write(audio_data)





@function_tool
def get_recent_band_data() -> str:
    
    count = 5
    # Ścieżki plików
    history_file = config.HISTORY_BAND_DATA_FILE

    # Wczytanie JSON-a
    try:
        with open(history_file, "r", encoding="utf-8") as f:
            history = json.load(f)
        if not isinstance(history, list):
            history = []
    except Exception as e:
        return json.dumps({"error": f"Nie udało się odczytać historii: {e}"}, ensure_ascii=False)

    recent = history[-count:]

    # Uproszczenie struktury: przenosimy pola z każdego entry["data"]
    simplified = []
    for entry in recent:
        record = entry
        simplified.append(record)

    print(f"[debug] get_recent_band_data: {simplified}")
    return json.dumps(simplified, ensure_ascii=False)


@function_tool
def get_calendar_events(query: str) -> str:
    print(f"[debug] get_calendar_events called with query: {query}")
    resp = requests.get(
        "http://localhost:5000/api/reminders",
        params={"n": 10}
    )
    resp.raise_for_status()
    return resp.text

@function_tool
def notify_event(description: str) -> str:
    print(f"[debug] notify_event called with description: {description}")
    append_notification(event="info", description=description)
    return "Event has been recorded in the event log."


@function_tool
def notify_caregiver(alert: str) -> str:
    print(f"[debug] notify_caregiver called with alert: {alert}")

    append_notification(event="anomaly", description=alert)
    
    # Removing an anomaly that was introduced for testing purposes
    history_file = config.HISTORY_BAND_DATA_FILE

    try:
        with open(history_file, "r", encoding="utf-8") as f:
            history = json.load(f)
        if not isinstance(history, list):
            history = []
    except Exception as e:
        return f"Opiekun powiadomiony (błąd odczytu historii: {e})."

    def is_anomaly(entry):
        if entry.get("fall_detected", False):
            return True
        hr = entry.get("heart_rate")
        if isinstance(hr, (int, float)) and (hr < 50 or hr > 120):
            return True
        sp = entry.get("spo2")
        if isinstance(sp, (int, float)) and sp < 90:
            return True
        return False

    original_len = len(history)
    filtered = [e for e in history if not is_anomaly(e)]
    removed = original_len - len(filtered)

    try:
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(filtered, f, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Opiekun powiadomiony. Usunięto {removed} anomalii, ale błąd zapisu: {e}."

    return f"Opiekun powiadomiony. Usunięto {removed} wpisów-anomalii z historii."


fun_agent = Agent(
    name="Fun",
    handoff_description="A playful agent for entertainment: jokes, puzzles, crossword hints, riddles.",
    instructions=prompt_with_handoff_instructions(
        """
You are a helpful, entertaining assistant.
Always respond in English in a cheerful and creative tone.
When the user requests entertainment, a puzzle, a riddle, or help solving a crossword clue,
you take over the conversation.
Provide a joke, a riddle, or a crossword hint at a level suitable for seniors.
After each piece of entertainment you deliver, always call function **notify_event**
with a brief description of the exercise (e.g. "Provided a riddle about animals", 
"Offered a crossword hint for clue X"), because puzzles and entertainment serve
as mental exercises for the user.
"""
    ),
    model="gpt-4o-mini",
    tools=[notify_event],  # nie potrzebuje dodatkowych narzędzi
)

def build_main_agent():

    with open("daily_routine_context.json", "r", encoding="utf-8") as f:
        daily_routine = json.dumps(json.load(f), ensure_ascii=False, indent=2)
    with open("proposed_medications.json", "r", encoding="utf-8") as f:
        medications = json.dumps(json.load(f), ensure_ascii=False, indent=2)

    convo_file = config.TRANSCRIPT_HISTORY_FILE
    try:
        with open(convo_file, encoding="utf-8") as f:
            convo = json.load(f)
    except Exception:
        convo = []
    last_entries = convo[-5:]
    history_json = json.dumps(last_entries, ensure_ascii=False, indent=2)

    prompt = f"""
You are a care assistant for elderly and disabled individuals.
Always respond in a gentle, supportive tone in English.

— Permanent User Context —
• Daily routine:
{daily_routine}

• List of medications:
{medications}

— Conversation History (last 5 exchanges) —
Each entry includes:
- timestamp
- input_transcript (what the user said)
- output_transcript (your previous response)

{history_json}

— Dynamic Context and Rules of Conduct —

1. At the start of each conversation (before generating your response), invoke **get_recent_band_data** and analyze the trend:
   - If any measurement has `fall_detected=true` or if heart rate/SpO₂ values fall outside the safe range (heart rate < 50 or > 120, SpO₂ < 90%), immediately call **notify_caregiver** with a description of the concerning measurements. Inform the user that the caregiver has been notified.

2. If the user reports alarming symptoms (such as shortness of breath, chest pain, dizziness, headache, or fainting):
   - Immediately call **notify_caregiver** with an alert.
   - Log the reported symptoms by calling **notify_event** with an appropriate description, so that all health concerns are recorded.
   - Check which medications the user is taking and analyze whether the symptoms could be related to their treatment.

3. If the user asks about upcoming events, dates, or schedules, call **get_calendar_events** and generate a helpful response based on the available events.

4. If the user requests entertainment, a riddle, joke, a puzzle, or help solving a crossword clue, hand off the conversation to the **Fun** agent.

5. In all other cases, respond gently: remind about medication, encourage hydration, rest, or suggest a short walk.
"""

    return Agent(
        name="Assistant",
        instructions=prompt_with_handoff_instructions(prompt),
        model="gpt-4o-mini",
        tools=[notify_caregiver, get_calendar_events, get_recent_band_data, notify_event],
        handoffs=[fun_agent],
    )


class WorkflowCallbacks(SingleAgentWorkflowCallbacks):
    def __init__(self):
        super().__init__()
        self.transcription: str | None = None

    def on_run(self, workflow: SingleAgentVoiceWorkflow, transcription: str) -> None:
        self.transcription = transcription
        print(f"[debug] on_run transcription: {transcription}")


async def voice_handler(audio: np.ndarray):
    
    callbacks = WorkflowCallbacks()

    pipeline = VoicePipeline(
        workflow=SingleAgentVoiceWorkflow(build_main_agent(), callbacks=callbacks)
    )
    
    audio_input = AudioInput(buffer=audio)
    result = await pipeline.run(audio_input)
    
    with AudioPlayer() as player:
        async for event in result.stream():
            if event.type == "voice_stream_event_audio":
                player.add_audio(event.data)
                print("Received audio")
            elif event.type == "voice_stream_event_lifecycle":
                print(f"Lifecycle: {event.event}")
        # dodajemy 1 s ciszy na koniec
        player.add_audio(np.zeros(24000 * 1, dtype=np.int16))

    
    text_response    = result.total_output_text
    input_transcript = callbacks.transcription or ""

    return {
        "output_transcript": text_response,
        "input_transcript":  input_transcript
    }