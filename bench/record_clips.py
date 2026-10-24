"""Record one WAV per sentence in sentences_hakob.tsv for the ASR benchmark.

Press Enter to start a sentence, read it aloud, press Enter to stop.
Clips are saved as 16 kHz mono WAV in bench/clips/hakob/<id>.wav.
"""

import argparse
import queue
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf

SAMPLE_RATE = 16000
HERE = Path(__file__).parent


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mic", type=int, default=None, help="input device index (see skeleton.py --list-devices)")
    parser.add_argument("--only", nargs="*", help="re-record only these sentence ids")
    args = parser.parse_args()

    out_dir = HERE / "clips" / "hakob"
    out_dir.mkdir(parents=True, exist_ok=True)
    sentences = [line.split("\t", 1) for line in (HERE / "sentences_hakob.tsv").read_text(encoding="utf-8").splitlines() if line.strip()]

    for clip_id, text in sentences:
        if args.only and clip_id not in args.only:
            continue
        input(f"\n[{clip_id}] {text}\nPress Enter, then read the sentence...")
        chunks = queue.Queue()

        def callback(indata, frames, time_info, status):
            if status:
                raise RuntimeError(f"Audio input error: {status}")
            chunks.put(indata[:, 0].copy())

        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", device=args.mic, callback=callback):
            input("Recording... press Enter to stop.")
        audio = np.concatenate(list(chunks.queue))
        sf.write(out_dir / f"{clip_id}.wav", audio, SAMPLE_RATE)
        print(f"Saved {out_dir / f'{clip_id}.wav'} ({len(audio) / SAMPLE_RATE:.1f} s)")


if __name__ == "__main__":
    main()
