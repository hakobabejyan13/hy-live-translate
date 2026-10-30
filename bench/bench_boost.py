"""Does NeMo phrase boosting help the ASR write loanwords the way glossary.tsv expects?

Re-transcribes recorded clips with FastConformer (RNNT greedy_batch, as in asr.py) once without boosting and
once per boosting weight, with the glossary's Armenian spellings as boosted phrases (NeMo GPU-PB boosting tree,
nemo.collections.asr.parts.context_biasing). Then runs glossary.py on every transcript and counts how many of
the expected words from sentences_loanwords.tsv reach the text sent to MT.

Control sets check that boosting does not hurt plain Armenian: WER on bench/clips/hakob (sentences_hakob.tsv,
skipped if not recorded) and, with --fleurs N, on the first N FLEURS hy_am test clips.

Usage (from the repo root, after `python skeleton.py --sources mic --save-audio` while reading
bench/sentences_loanwords.tsv):
  python bench/bench_boost.py --clips logs/audio_<run>
Results: printed table + bench/results/boost_<run>.csv (every transcript, per weight).
"""

import argparse
import csv
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import soundfile as sf
import torch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bench"))

from asr import Recognizer  # noqa: E402
from bench_asr import edit_distance, fleurs_clips, normalize  # noqa: E402
from glossary import Glossary  # noqa: E402

HERE = Path(__file__).parent
SAMPLE_RATE = 16000


def load_wav(path):
    audio, sr = sf.read(path, dtype="float32")
    if sr != SAMPLE_RATE or audio.ndim != 1:
        raise ValueError(f"{path}: expected 16 kHz mono, got {sr} Hz with shape {audio.shape}")
    return audio


def expected_words():
    words = Counter()
    for line in (HERE / "sentences_loanwords.tsv").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            words.update(w.strip().lower() for w in line.split("\t")[3].split(",") if w.strip())
    return words


def loanword_hits(texts, expected):
    """Expected words found in the MT input, counted at most as often as they are expected."""
    joined = " ".join(texts).lower()
    found = {w: min(n, joined.count(w)) for w, n in expected.items()}
    return sum(found.values()), [w for w, n in expected.items() if found[w] < n]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clips", required=True, type=Path, help="folder from skeleton.py --save-audio")
    parser.add_argument("--alphas", type=float, nargs="+", default=[0.0, 0.5, 1.0, 2.0],
                        help="boosting weights to try; 0 = no boosting (default: 0 0.5 1 2)")
    parser.add_argument("--fleurs", type=int, default=0, help="also check WER on the first N FLEURS hy_am test clips")
    parser.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    args = parser.parse_args()

    clips = sorted(args.clips.glob("*_mic.wav"))
    if not clips:
        raise SystemExit(f"No *_mic.wav files in {args.clips}. Record with: python skeleton.py --sources mic --save-audio")
    control = []
    hakob_tsv = HERE / "sentences_hakob.tsv"
    for line in hakob_tsv.read_text(encoding="utf-8").splitlines():
        if line.strip():
            cid, ref = line.split("\t", 1)
            path = HERE / "clips" / "hakob" / f"{cid}.wav"
            if path.exists():
                control.append((path, ref))
    if args.fleurs:
        control += [(path, ref) for _, path, ref in fleurs_clips(args.fleurs)]

    glossary = Glossary.from_file()
    phrases = glossary.boost_phrases()
    expected = expected_words()
    print(f"{len(clips)} loanword clips, {len(control)} control clips, {len(phrases)} boosted phrases, "
          f"{sum(expected.values())} expected loanwords")

    asr = Recognizer(args.device)
    run_id = f"{datetime.now():%Y%m%d_%H%M%S}"
    out_path = HERE / "results" / f"boost_{run_id}.csv"
    rows, summary = [], []
    for alpha in args.alphas:
        asr.set_boosting(phrases, alpha)
        asr.warmup()
        texts, times = [], []
        for path in clips:
            audio = load_wav(path)
            if args.device == "cuda":
                torch.cuda.synchronize()
            t = time.perf_counter()
            tr = asr.transcribe(audio)
            if args.device == "cuda":
                torch.cuda.synchronize()
            times.append(time.perf_counter() - t)
            fixed = glossary.apply(tr.text_hy)
            texts.append(fixed.for_mt)
            rows.append({"alpha": alpha, "clip": path.name, "text_hy_asr": tr.text_hy, "text_mt_in": fixed.for_mt,
                         "asr_s": f"{times[-1]:.3f}"})
        hits, missed = loanword_hits(texts, expected)
        errors = words = 0
        for path, ref in control:
            hyp = asr.transcribe(load_wav(path)).text_hy
            errors += edit_distance(normalize(ref).split(), normalize(hyp).split())
            words += len(normalize(ref).split())
            rows.append({"alpha": alpha, "clip": f"control/{path.name}", "text_hy_asr": hyp, "text_mt_in": "",
                         "asr_s": ""})
        wer = f"{100 * errors / words:.1f}%" if words else "-"
        summary.append((alpha, hits, wer, sum(times) / len(times), missed))

    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["alpha", "clip", "text_hy_asr", "text_mt_in", "asr_s"])
        w.writeheader()
        w.writerows(rows)

    total = sum(expected.values())
    print(f"\n{'alpha':>5}  {'loanwords':>10}  {'control WER':>11}  {'ASR s/clip':>10}  missed")
    for alpha, hits, wer, sec, missed in summary:
        print(f"{alpha:>5}  {hits:>4} / {total:<3}  {wer:>11}  {sec:>10.3f}  {', '.join(missed)}")
    print(f"\nTranscripts: {out_path}")


if __name__ == "__main__":
    main()
