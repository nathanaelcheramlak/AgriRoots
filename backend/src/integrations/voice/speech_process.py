"""Separate-process adapter to the upstream GPL-3.0-or-later eSpeak NG runtime."""
import ctypes as c
import io
import json
from pathlib import Path
import sys
import wave
import espeakng_loader


def main():
    request = json.load(sys.stdin)
    text = request["text"]
    language = request["language"]
    if language not in ("en", "am") or not text or len(text) > 20000:
        raise ValueError("Invalid speech request")
    library = c.CDLL(espeakng_loader.get_library_path())
    library.espeak_Initialize.argtypes = [c.c_int, c.c_int, c.c_char_p, c.c_int]
    rate = library.espeak_Initialize(2, 0, str(Path(espeakng_loader.get_data_path()).parent).encode(), 0x8000)
    if rate <= 0: raise RuntimeError("Local speech initialization failed")
    library.espeak_SetVoiceByName.argtypes = [c.c_char_p]
    if library.espeak_SetVoiceByName(language.encode()) != 0:
        raise ValueError("Requested local voice is unavailable")
    library.espeak_SetParameter(1, 155, 0)  # words per minute
    chunks = []
    callback_type = c.CFUNCTYPE(c.c_int, c.POINTER(c.c_short), c.c_int, c.c_void_p)
    @callback_type
    def callback(samples, length, _events):
        if samples and length: chunks.append(c.string_at(samples, length * 2))
        return 0
    library.espeak_SetSynthCallback.argtypes = [callback_type]
    library.espeak_SetSynthCallback(callback)
    library.espeak_Synth.argtypes = [c.c_void_p, c.c_size_t, c.c_uint, c.c_int, c.c_uint, c.c_uint, c.c_void_p, c.c_void_p]
    encoded = text.encode("utf-8") + b"\0"
    # UTF-8 and end pause; SSML/phoneme interpretation are deliberately disabled.
    if library.espeak_Synth(encoded, len(encoded), 0, 1, 0, 0x1001, None, None) != 0:
        raise RuntimeError("Local speech synthesis failed")
    library.espeak_Terminate()
    audio = io.BytesIO()
    with wave.open(audio, "wb") as stream:
        stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(rate)
        stream.writeframes(b"".join(chunks))
    sys.stdout.buffer.write(audio.getvalue())


if __name__ == "__main__": main()
