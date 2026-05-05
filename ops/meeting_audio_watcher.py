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

ROOT = Path(os.environ.get("RECORDINGS_ROOT", "/var/lib/vexa/recordings"))
TG_URL = os.environ["TELEGRAM_ALERT_URL"]
TG_SECRET = os.environ["TELEGRAM_ALERT_SECRET"]
STATE_DIR = Path("/state")
STATE_DIR.mkdir(parents=True, exist_ok=True)
TRANSCRIPT_DIR = STATE_DIR / "transcripts"
TRANSCRIPT_DIR.mkdir(exist_ok=True)
EXPORT_DIR = STATE_DIR / "recordings"
EXPORT_DIR.mkdir(exist_ok=True)
STATE_FILE = STATE_DIR / "state.json"
POLL = int(os.environ.get("POLL_SECONDS", "8"))
QUESTION_RE = re.compile(r"\b(what|why|how|when|where|who|which|can|could|should|would|timeline|cost|price|budget|proposal|requirement|security|hosting|maintenance)\b", re.I)
SILENCE_RE = re.compile(r"^(you|thank you|thanks|okay|ok|uh|um|hmm|yes|no|hello|hi)[\s.,!?-]*$", re.I)

def utcnow(): return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

def load_state():
    if STATE_FILE.exists():
        try: return json.loads(STATE_FILE.read_text())
        except Exception: pass
    return {"groups": {}, "exported": {}}
state = load_state(); state.setdefault("groups", {}); state.setdefault("exported", {})

def save_state():
    tmp = STATE_FILE.with_suffix(".tmp"); tmp.write_text(json.dumps(state, indent=2, sort_keys=True)); tmp.replace(STATE_FILE)

def send_telegram(text):
    try:
        r = requests.post(TG_URL, headers={"x-alert-secret": TG_SECRET, "content-type": "application/json"}, json={"text": text[:3900]}, timeout=12)
        print("telegram", r.status_code, text[:80], flush=True)
    except Exception as exc:
        print("telegram_error", repr(exc), flush=True)

def all_audio_files(): return sorted((ROOT / "recordings").glob("*/*/*/audio/*.webm"))

def rec_key(path):
    parts = path.parts; hits = [i for i, part in enumerate(parts) if part == "recordings"]
    try:
        i = hits[-1]; return f"user-{parts[i+1]}-rec-{parts[i+2]}-session-{parts[i+3]}"
    except Exception: return path.parent.parent.name

def stable_files(files):
    out = []
    for path in files:
        try: stat = path.stat()
        except FileNotFoundError: continue
        if stat.st_size > 2500 and time.time() - stat.st_mtime > 4: out.append(path)
    return out

def concat_audio(files, output):
    with tempfile.NamedTemporaryFile("w", delete=False) as handle:
        list_file = handle.name
        for path in files: handle.write("file '" + str(path).replace("'", "'\\''") + "'\n")
    try:
        p = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-vn", "-c:a", "libopus", str(output)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        if p.returncode:
            print("ffmpeg_error", p.returncode, p.stderr.decode("utf-8", "ignore")[-500:], flush=True)
            return False
        return output.exists() and output.stat().st_size > 0
    finally:
        try: os.unlink(list_file)
        except OSError: pass

def transcribe_file(model, path):
    segments, _ = model.transcribe(str(path), language="en", vad_filter=True, beam_size=1)
    text = " ".join(s.text.strip() for s in segments if s.text and s.text.strip()).strip()
    return re.sub(r"\s+", " ", text)

def append_transcript(key, text):
    with (TRANSCRIPT_DIR / f"{key}.txt").open("a") as handle: handle.write(f"[{utcnow()}] {text}\n")

def new_delta(previous, current):
    previous = previous.strip(); current = current.strip()
    if not current or current == previous: return ""
    if previous and current.startswith(previous): return current[len(previous):].strip(" -.,")
    if previous and len(current) > len(previous): return current[-600:].strip()
    return current

def maybe_export(key, files):
    if key in state["exported"] or not files: return
    latest = max(path.stat().st_mtime for path in files)
    if time.time() - latest < 75: return
    output = EXPORT_DIR / f"{key}.webm"
    if concat_audio(files, output):
        state["exported"][key] = str(output); send_telegram(f"Recording exported: {key}. Transcript: /state/transcripts/{key}.txt")

def process_group(model, key, files):
    files = stable_files(files)
    if not files: return
    signature = ":".join(f"{p.name}-{p.stat().st_size}" for p in files)
    group = state["groups"].setdefault(key, {})
    if group.get("signature") == signature:
        maybe_export(key, files); return
    combined = STATE_DIR / f"{key}.latest.webm"
    if not concat_audio(files, combined): return
    text = transcribe_file(model, combined)
    print("transcribed", key, "files", len(files), "chars", len(text), flush=True)
    group["signature"] = signature
    if text and len(text) >= 5 and not SILENCE_RE.match(text):
        delta = new_delta(group.get("text", ""), text); group["text"] = text
        if delta:
            append_transcript(key, delta); send_telegram(f"Live transcript [{key}]: {delta}")
            if "?" in delta or QUESTION_RE.search(delta): send_telegram("Copilot prompt: acknowledge this point, answer only what is known, and ask for exact scope, timeline, integrations, and success criteria.")
    maybe_export(key, files)

def main():
    print("Loading Whisper", flush=True)
    model = WhisperModel(os.environ.get("WHISPER_MODEL_SIZE", "tiny"), device="cpu", compute_type="int8", download_root="/state/whisper")
    print("Whisper ready", flush=True); send_telegram("Direct audio watcher is online: local Whisper will transcribe combined Vexa audio chunks and send Telegram alerts.")
    loop = 0
    while True:
        try:
            groups = {}
            for path in all_audio_files(): groups.setdefault(rec_key(path), []).append(path)
            loop += 1
            if loop % 5 == 1: print("scan", len(groups), "groups", sum(len(v) for v in groups.values()), "files", flush=True)
            for key, files in groups.items():
                try: process_group(model, key, files)
                except Exception as exc: print("group_error", key, repr(exc), flush=True)
            save_state()
        except Exception as exc: print("loop_error", repr(exc), flush=True)
        time.sleep(POLL)
if __name__ == "__main__": main()
