"""
voice_engine.py — JARVIS v3 Voice Engine
Wake-word detection (Vosk) + TTS (pyttsx3). All optional — graceful no-op if not installed.
"""
from __future__ import annotations
import logging, queue, threading
from typing import Callable

logger = logging.getLogger(__name__)


class VoiceEngine:
    def __init__(self, config=None) -> None:
        from config import get_config
        cfg = config or get_config()
        v = cfg.section("voice")
        self.enabled    = bool(v.get("enabled", False))
        self.wake_words = [w.lower() for w in v.get("wake_words", ["jarvis"])]
        self.tts_rate   = int(v.get("tts_rate", 175))
        self.tts_vol    = float(v.get("tts_volume", 0.92))
        self.model_dirs = v.get("vosk_model_dirs", [])
        self.device     = v.get("input_device_index", None)
        self._tts       = None
        self._model     = None
        self._listening = False
        self._q: queue.Queue = queue.Queue()
        self.on_wake_word:  Callable[[str], None] | None = None
        self.on_transcript: Callable[[str], None] | None = None

        if self.enabled:
            self._init_tts()
            self._init_asr()

    def _init_tts(self) -> None:
        try:
            import pyttsx3
            self._tts = pyttsx3.init()
            self._tts.setProperty("rate", self.tts_rate)
            self._tts.setProperty("volume", self.tts_vol)
        except Exception as e:
            logger.info("TTS unavailable: %s", e)

    def _init_asr(self) -> None:
        try:
            import vosk, os
            for d in self.model_dirs:
                expanded = os.path.expanduser(d)
                import os as _os
                if _os.path.isdir(expanded):
                    self._model = vosk.Model(expanded)
                    logger.info("Vosk model: %s", expanded)
                    return
        except ImportError:
            logger.info("vosk not installed")
        except Exception as e:
            logger.warning("ASR init: %s", e)

    def speak(self, text: str) -> None:
        if not self._tts:
            return
        def _run():
            self._tts.say(text)
            self._tts.runAndWait()
        threading.Thread(target=_run, daemon=True).start()

    def start_listening(self) -> None:
        if self._model is None or self._listening:
            return
        self._listening = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop_listening(self) -> None:
        self._listening = False

    def _loop(self) -> None:
        try:
            import sounddevice as sd, vosk, json
            rec = vosk.KaldiRecognizer(self._model, 16000)
            with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype="int16",
                                   channels=1, device=self.device,
                                   callback=lambda d,f,t,s: self._q.put(bytes(d))):
                while self._listening:
                    data = self._q.get()
                    if rec.AcceptWaveform(data):
                        text = json.loads(rec.Result()).get("text", "").lower()
                        if text and self.on_transcript:
                            self.on_transcript(text)
                        for ww in self.wake_words:
                            if ww in text and self.on_wake_word:
                                self.on_wake_word(text)
                                break
        except ImportError:
            logger.info("sounddevice/vosk not installed")
        except Exception as e:
            logger.error("Listen loop: %s", e)
        finally:
            self._listening = False

    @property
    def is_available(self) -> bool:
        return self.enabled and (self._tts is not None or self._model is not None)
