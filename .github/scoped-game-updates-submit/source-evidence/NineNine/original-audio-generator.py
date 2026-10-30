#!/usr/bin/env python3
"""Original NineNine score/synthesis, authored for Kamilunavo, 2026-10-29.

No samples, plugins, RNG, remote assets or external dependencies. Re-run with
Python 3 to reproduce the checked-in mono PCM16 files and provenance manifest.
"""
import argparse
import array
import hashlib
import json
import math
from pathlib import Path
import sys
import wave

RATE = 22050
SCORE = [(0.0, 57), (1.75, 64), (3.75, 69), (6.0, 53), (8.25, 60),
         (10.0, 65), (12.0, 55), (14.5, 62), (16.0, 67), (18.0, 52),
         (20.25, 59), (21.5, 64)]


def tone(midi, seconds, gain, attack=.03):
    count = round(seconds * RATE)
    frequency = 440.0 * 2.0 ** ((midi - 69) / 12)
    result = []
    for index in range(count):
        t = index / RATE
        # Both edges approach zero smoothly; no hard gate or square waves.
        edge = min(1.0, t / attack, (count - 1 - index) / RATE / attack)
        envelope = math.sin(math.pi * .5 * max(0.0, edge)) ** 2
        # Roundoff at pi may be a tiny negative; amplitude cannot be negative.
        envelope *= max(0.0, math.sin(math.pi * index / (count - 1))) ** .8
        phase = math.tau * frequency * t
        result.append(gain * envelope * (math.sin(phase) + .12 * math.sin(phase * 2)) / 1.12)
    return result


def add(buffer, samples, start):
    offset = round(start * RATE)
    for index, sample in enumerate(samples):
        if offset + index < len(buffer): buffer[offset + index] += sample


def compose():
    music = [0.0] * (24 * RATE)
    for start, midi in SCORE:
        add(music, tone(midi, min(2.4, 24 - start), .10, .20), start)
        add(music, tone(midi - 12, min(3.0, 24 - start), .035, .35), start)
    hit = [0.0] * round(.28 * RATE)
    add(hit, tone(76, .20, .13, .012), 0)
    add(hit, tone(83, .20, .10, .012), .08)
    miss = [0.0] * round(.22 * RATE)
    add(miss, tone(55, .22, .12, .014), 0)
    add(miss, tone(50, .15, .045, .014), .07)
    return {"precision-loop.wav": music, "ui.wav": tone(76, .075, .065, .010), "hit.wav": hit, "miss.wav": miss}


def generate(output):
    output.mkdir(parents=True, exist_ok=True)
    receipts = {}
    for name, samples in compose().items():
        assert max(abs(v) for v in samples) < .5
        pcm = array.array("h", [round(sample * 32767) for sample in samples])
        if sys.byteorder != "little": pcm.byteswap()
        path = output / name
        with wave.open(str(path), "wb") as wav:
            wav.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
            wav.writeframes(pcm.tobytes())
        receipts[name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "frames": len(samples), "rate": RATE, "channels": 1, "pcmBits": 16}
    provenance = {"schema": 1, "authorship": "Original composition and deterministic procedural synthesis written for Kamilunavo on 2026-10-29 by the Codex implementation agent under owner instruction.",
                  "externalAudioInputs": [], "generator": "scripts/generate_original_audio.py", "generatorSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  "scoreMidiAtSeconds": SCORE, "outputs": receipts, "notice": "assets/audio/NOTICE.txt"}
    (output / "PROVENANCE.json").write_text(json.dumps(provenance, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "assets/audio")
    generate(parser.parse_args().output)
