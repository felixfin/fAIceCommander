"""Offline voice generation with Piper TTS - a development tool, never part of the game.

Piper is GPL-3.0, so it lives in its own venv and is not a game dependency; only the generated
audio ships. Setup (once, outside .venv):

    python -m venv tools/voice/.pipervenv
    tools/voice/.pipervenv/Scripts/python -m pip install piper-tts
    # download the four voices (.onnx + .onnx.json) from huggingface.co/rhasspy/piper-voices
    # into tools/voice/models/ - all trained only on public-domain recordings (see each MODEL_CARD):
    # en_US-norman-medium, en_US-kristin-medium, en_US-ljspeech-high, en_US-john-medium

Run: tools/voice/.pipervenv/Scripts/python -I tools/voice/tts_generate.py [line ids...]
Writes raw WAVs to tools/voice/raw/<id>.wav; then run tts_process.py with the game's .venv.
"""
import sys
import wave
from pathlib import Path

from piper import PiperVoice, SynthesisConfig

HERE = Path(__file__).parent
VOICES = HERE / "models"
OUT = HERE / "raw"
OUT.mkdir(exist_ok=True)

# id: (voice, spoken text, length_scale)  -- length_scale > 1 is slower; "//" marks a long pause
PAUSE_SENTENCE, PAUSE_LONG = 0.32, 0.75
LINES = {
    "intro_01": ("norman", "For centuries, humanity has been at war with the Catliens.", 1.18),
    "intro_02": ("norman", "Feline. Brilliant. Merciless. Their swarms have burned world after world.", 0.98),
    "intro_03": ("norman", "Most of us are slaves now. // Pets of the higher castes.", 1.15),
    "intro_04": ("norman", "They neuter the males. They milk the females.", 1.15),
    "intro_05": ("norman", "One mind steers the swarm: the Mother. Destroy her, and the swarm falls into chaos.", 1.12),
    "intro_06": ("norman", "Commander James Nathaniel Honor found her. His fleet struck hard.", 1.08),
    "intro_07": ("norman", "Her hyperdrive failed. // But his fleet was lost.", 1.1),
    "intro_08": ("kristin", "Only the head, and part of the torso, could be saved.", 1.0),
    "intro_09": ("norman", "We built him a ship from the wreckage. There is nothing left for another attempt.", 1.12),
    "intro_10": ("ljspeech", "Commander? Can you hear me? You don't know who you are. But you know the way. Star by star.", 0.95),
    "intro_11": ("norman", "Face Commander. // You are our last hope!", 1.15),
    "outro_01": ("norman", "The Mother is dead.", 1.25),
    "outro_02": ("norman", "Across the galaxy, the swarm loses its mind.", 1.15),
    "outro_03": ("norman", "On a thousand worlds, the collars fall.", 1.15),
    "outro_04": ("john", "My name is. // James Nathaniel Honor.", 1.15),
}
FILES = {"norman": "en_US-norman-medium", "kristin": "en_US-kristin-medium",
         "ljspeech": "en_US-ljspeech-high", "john": "en_US-john-medium"}

only = set(sys.argv[1:])
loaded = {}
for line_id, (voice, text, scale) in LINES.items():
    if only and line_id not in only:
        continue
    if voice not in loaded:
        loaded[voice] = PiperVoice.load(str(VOICES / f"{FILES[voice]}.onnx"))
    cfg = SynthesisConfig(length_scale=scale, noise_scale=0.6, noise_w_scale=0.7)
    v = loaded[voice]
    rate = v.config.sample_rate
    pcm = b""
    for k, part in enumerate(text.split("//")):
        if k:
            pcm += bytes(2) * int(rate * PAUSE_LONG)
        for j, chunk in enumerate(v.synthesize(part.strip(), syn_config=cfg)):
            if j:
                pcm += bytes(2) * int(rate * PAUSE_SENTENCE)
            pcm += chunk.audio_int16_bytes
    with wave.open(str(OUT / f"{line_id}.wav"), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm)
    with wave.open(str(OUT / f"{line_id}.wav"), "rb") as wf:
        print(f"{line_id}: {wf.getnframes() / wf.getframerate():.2f}s  ({voice})")
