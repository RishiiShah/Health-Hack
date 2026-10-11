"""ElevenLabs text-to-speech, server side only, cached in PostgreSQL [00-Boundaries: ElevenLabs integration].

It only reads out text that was already decided; it never decides anything. One attempt, 10-second timeout, no retry:
on any failure the caller gets None (the API answers 503) and the text is still shown.
"""
import hashlib
import json
import os
import urllib.request
from threading import Lock
import psycopg

SCHEMA = "CREATE TABLE IF NOT EXISTS tts_audio (sha256 TEXT PRIMARY KEY, voice_id TEXT NOT NULL, model_id TEXT NOT NULL, audio BYTEA NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now())"
URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


class Speech:
    def __init__(self, url: str, api_key: str | None = None, voice_id: str | None = None, model_id: str | None = None):
        self.api_key = api_key if api_key is not None else os.getenv("ELEVENLABS_API_KEY")
        self.voice_id = voice_id or os.getenv("ELEVENLABS_VOICE_ID")
        self.model_id = model_id or os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
        self.conn = psycopg.connect(url, autocommit=True)
        self.conn.execute(SCHEMA)
        self.lock = Lock()

    @property
    def available(self) -> bool:
        return bool(self.api_key and self.voice_id)

    def audio(self, text: str) -> bytes | None:
        if not self.available:
            return None
        key = hashlib.sha256(f"{self.voice_id}\n{self.model_id}\n{text}".encode()).hexdigest()
        with self.lock:
            row = self.conn.execute("SELECT audio FROM tts_audio WHERE sha256=%s", (key,)).fetchone()
        if row:
            return bytes(row[0])
        request = urllib.request.Request(URL.format(voice_id=self.voice_id), data=json.dumps({"text": text, "model_id": self.model_id}).encode(),
                                         headers={"xi-api-key": self.api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                audio = response.read()
        except (OSError, ValueError):
            return None
        with self.lock:
            self.conn.execute("INSERT INTO tts_audio(sha256,voice_id,model_id,audio) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                              (key, self.voice_id, self.model_id, audio))
        return audio
