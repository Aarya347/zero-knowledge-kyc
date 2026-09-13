"""Active liveness: randomized spoken-digit challenge, verified with offline ASR
(Vosk) restricted to a digit-word grammar. The recognized digits must contain
the challenged digits as an ordered subsequence."""
import wave
from . import config

DIGIT_WORDS = {
    "zero": 0, "oh": 0, "o": 0,
    "one": 1, "two": 2, "three": 3, "four": 4, "for": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
}


class SpeechModelUnavailable(Exception):
    pass


class SpeechVerifier:
    def __init__(self, model_dir=config.VOSK_MODEL_DIR):
        import os
        if not os.path.isdir(model_dir):
            raise SpeechModelUnavailable(f"vosk model missing at {model_dir}")
        from vosk import Model, KaldiRecognizer  # noqa
        self._Model = Model
        self._KaldiRecognizer = KaldiRecognizer
        self.model = Model(model_dir)

    def transcribe_digits(self, wav_path: str):
        wf = wave.open(wav_path, "rb")
        if wf.getframerate() != 16000 or wf.getnchannels() != 1:
            wf.close()
            raise ValueError("wav must be 16 kHz mono")
        grammar = '["%s"]' % '", "'.join(sorted(set(DIGIT_WORDS.keys())))
        rec = self._KaldiRecognizer(self.model, 16000, grammar)
        words = []
        import json as _json
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            if rec.AcceptWaveform(data):
                j = _json.loads(rec.Result())
                words += (j.get("text") or "").split()
        j = _json.loads(rec.FinalResult())
        words += (j.get("text") or "").split()
        wf.close()
        return [DIGIT_WORDS[w] for w in words if w in DIGIT_WORDS]

    def verify(self, wav_path: str, digits):
        heard = self.transcribe_digits(wav_path)
        it = iter(heard)
        ok = all(d in it for d in digits)  # ordered-subsequence match
        return {"passed": bool(ok), "heard_digits": heard, "challenged": list(digits)}
