import json
import os
import re
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from faster_whisper import WhisperModel

VEXA_BASE = os.environ["VEXA_BASE_URL"].rstrip("/")
VEXA_AUTH = (os.environ["VEXA_BASIC_USER"], os.environ["VEXA_BASIC_PASS"])
VEXA_HEADERS = {"X-API-Key": os.environ["VEXA_API_KEY"]}
TG_URL = os.environ["TELEGRAM_ALERT_URL"]
TG_SECRET = os.environ["TELEGRAM_ALERT_SECRET"]
OLLAMA = os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:1.5b")
ROOT = Path(os.environ.get("RECORDINGS_ROOT", "/var/lib/vexa/recordings"))
STATE_DIR = Path("/state")
STATE_DIR.mkdir(parents=True, exist_ok=True)
TRANSCRIPT_DIR = STATE_DIR / "transcripts"
TRANSCRIPT_DIR.mkdir(exist_ok=True)
EXPORT_DIR = STATE_DIR / "recordings"
EXPORT_DIR.mkdir(exist_ok=True)
STATE_FILE = STATE_DIR / "state.json"
POLL = int(os.environ.get("POLL_SECONDS", "8"))


def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"files": {}, "meeting_status": {}, "exported": {}, "transcript_text": {}}


state = load_state()
for key in ("files", "meeting_status", "exported", "transcript_text"):
    state.setdefault(key, {})


def save_state():
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
    tmp.replace(STATE_FILE)


def send_telegram(text):
    try:
        requests.post(
            TG_URL,
            headers={"x-alert-secret": TG_SECRET, "content-type": "application/json"},
            json={"text": text[:3900]},
            timeout=12,
        )
    except Exception as exc:
        print("telegram_error", repr(exc), flush=True)


def vexa_get(path):
    response = requests.get(VEXA_BASE + path, auth=VEXA_AUTH, headers=VEXA_HEADERS, timeout=15)
    response.raise_for_status()
    return response.json()


QUESTION_RE = re.compile(
    r"\b(what|why|how|when|where|who|which|can|could|should|would|do you|are you|is it|will you|timeline|cost|price|budget|proposal|requirement|integrat(?:e|ion)|security|hosting|maintenance)\b",
    re.I,
)
SILENCE_RE = re.compile(r"^(you|thank you|thanks|okay|ok|uh|um|hmm|yes|no|hello|hi)[\s.,!?-]*$", re.I)


def ask_llm(text):
    prompt = (
        "You are a private sales-call copilot for Digiscience. Return a short Telegram alert. "
        "Identify any customer question, requirement, risk, or buying signal, then draft a concise suggested reply and one useful follow-up question. "
        "Do not invent facts. Keep under 90 words.\n\nTranscript chunk:\n" + text
    )
    try:
        response = requests.post(
            OLLAMA + "/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 120, "temperature": 0.2},
            },
            timeout=35,
        )
        if response.ok:
            result = (response.json().get("response") or "").strip()
            if result:
                return result
    except Exception as exc:
        print("ollama_error", repr(exc), flush=True)
    return "Suggested response: acknowledge the point, confirm the exact requirement, then ask about timeline, users, integrations, and success criteria."


def recording_paths(recording):
    user_id = str(recording.get("user_id") or 1)
    recording_id = str(recording.get("id"))
    session_uid = recording.get("session_uid") or "*"
    base = ROOT / "recordings" / user_id / recording_id
    return sorted(base.glob(f"{session_uid}/audio/*.webm")) if base.exists() else []


def is_stable(path):
    try:
        stat = path.stat()
    except FileNotFoundError:
        return False
    return stat.st_size > 2500 and time.time() - stat.st_mtime > 4


def append_transcript(meet_id, chunk_name, text):
    with (TRANSCRIPT_DIR / f"{meet_id}.txt").open("a") as handle:
        handle.write(f"[{utcnow()}] {chunk_name}: {text}\n")
    state["transcript_text"][meet_id] = ((state["transcript_text"].get(meet_id, "") + " " + text).strip())[-12000:]


def export_recording(meet_id, files):
    if not files or state["exported"].get(meet_id):
        return
    output = EXPORT_DIR / f"{meet_id}.webm"
    list_file = None
    try:
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            list_file = handle.name
            for path in files:
                handle.write("file '" + str(path).replace("'", "'\\''") + "'\n")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-vn", "-c:a", "libopus", str(output)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=120,
        )
        if output.exists() and output.stat().st_size > 0:
            state["exported"][meet_id] = str(output)
            send_telegram(f"Recording exported for Meet {meet_id}: {output}. Transcript: /state/transcripts/{meet_id}.txt")
    except Exception as exc:
        print("export_error", meet_id, repr(exc), flush=True)
    finally:
        if list_file:
            try:
                os.unlink(list_file)
            except OSError:
                pass


def transcribe_file(model, path):
    segments, _ = model.transcribe(str(path), language="en", vad_filter=True, beam_size=1)
    text = " ".join(segment.text.strip() for segment in segments if segment.text and segment.text.strip()).strip()
    return re.sub(r"\s+", " ", text)


def main():
    print("Loading Whisper model", flush=True)
    model = WhisperModel(
        os.environ.get("WHISPER_MODEL_SIZE", "tiny"),
        device="cpu",
        compute_type="int8",
        download_root="/state/whisper",
    )
    print("Copilot watcher started", utcnow(), flush=True)
    send_telegram("Meeting copilot pipeline is online: local Whisper transcription, recording export, and Telegram advice alerts are running.")
    while True:
        try:
            meetings = vexa_get("/bots").get("meetings", [])
            for meeting in meetings:
                meet_id = meeting.get("native_meeting_id") or str(meeting.get("id"))
                status = meeting.get("status")
                if status != state["meeting_status"].get(meet_id):
                    state["meeting_status"][meet_id] = status
                    if status in {"awaiting_admission", "active", "failed", "completed"}:
                        suffix = ""
                        if status == "awaiting_admission":
                            suffix = " Please admit Digiscience AI Notetaker."
                        if status == "failed":
                            suffix = " Fallback watcher will still process captured audio chunks."
                        send_telegram(f"Meet {meet_id} status: {status}.{suffix}")
                recordings = (meeting.get("data") or {}).get("recordings") or meeting.get("recordings") or []
                all_files = []
                for recording in recordings:
                    paths = recording_paths(recording)
                    all_files.extend(paths)
                    for path in paths:
                        key = str(path)
                        if key in state["files"] or not is_stable(path):
                            continue
                        try:
                            text = transcribe_file(model, path)
                        except Exception as exc:
                            print("transcribe_error", key, repr(exc), flush=True)
                            continue
                        state["files"][key] = {"meet": meet_id, "text": text, "bytes": path.stat().st_size, "at": utcnow()}
                        if text and len(text) >= 5 and not SILENCE_RE.match(text):
                            append_transcript(meet_id, path.name, text)
                            send_telegram(f"Live transcript from Meet {meet_id}: {text}")
                            if "?" in text or QUESTION_RE.search(text):
                                send_telegram(f"Copilot suggestion for Meet {meet_id}: {ask_llm(text)}")
                if status in {"completed", "failed"} and all_files:
                    export_recording(meet_id, all_files)
            save_state()
        except Exception as exc:
            print("loop_error", repr(exc), flush=True)
        time.sleep(POLL)


if __name__ == "__main__":
    main()
