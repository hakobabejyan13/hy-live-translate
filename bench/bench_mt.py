"""Benchmark NLLB-200 translation on FLEURS hy_am: BLEU, chrF, seconds per sentence and token counts.

Two Armenian inputs per FLEURS clip:
  reference  the FLEURS Armenian transcript, so the score is MT quality alone (one row per unique sentence)
  asr        the FastConformer transcript from bench/results/*_nvidia-fastconformer_fleurs.csv,
             so the score is the full ASR -> MT cascade (one row per clip)
English references are the FLEURS en_us transcripts with the same sentence id. Clips whose sentence id has
no en_us transcript are listed and left out of the scores.

Results are saved in bench/results/:
  mt_summary.csv                      one row per run, input and device, appended on every run
  <run>_nllb-600m_<input>_<device>.csv   per sentence: Armenian input, English output and reference,
                                      tokens in/out, capped, seconds

Run from the repo root, after bench_asr.py has written a FastConformer FLEURS result:
  pip install -r requirements.txt -r bench\\requirements-bench.txt
  python bench\\bench_mt.py --device cuda
  python bench\\bench_mt.py --device cpu
"""

import argparse
import csv
import platform
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import psutil
import sacrebleu
import torch
from huggingface_hub import hf_hub_download

HERE = Path(__file__).parent
RESULTS = HERE / "results"
sys.path.insert(0, str(HERE.parent))
from translate import MT_MODEL, Translator  # noqa: E402

SUMMARY_COLUMNS = ["run", "model", "input", "device", "device_name", "threads", "sentences", "bleu", "chrf",
                   "mean_s", "p95_s", "max_s", "tokens_in_mean", "tokens_out_mean", "capped", "load_s",
                   "vram_peak_gb", "ram_peak_gb", "asr_csv"]


def fleurs_tsv(lang, split):
    """Rows of a FLEURS transcript file. Columns: id, file name, raw transcription, transcription, ..."""
    path = hf_hub_download("google/fleurs", f"data/{lang}/{split}.tsv", repo_type="dataset")
    return [line.split("\t") for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def load_inputs(asr_csv):
    """Returns (reference items, asr items, missing ids). Each item: (key, sentence id, Armenian text, English ref)."""
    hy = {r[1].removesuffix(".wav"): (r[0], r[2]) for r in fleurs_tsv("hy_am", "test")}  # clip -> (id, text)
    en = {r[0]: r[2] for split in ("train", "dev", "test") for r in fleurs_tsv("en_us", split)}
    with open(asr_csv, encoding="utf-8") as f:
        asr_rows = list(csv.DictReader(f))

    reference, asr, missing, seen = [], [], set(), set()
    for row in asr_rows:
        sentence_id, text_hy = hy[row["id"]]
        if sentence_id not in en:
            missing.add(sentence_id)
            continue
        asr.append((row["id"], sentence_id, row["hypothesis"], en[sentence_id]))
        if sentence_id not in seen:
            seen.add(sentence_id)
            reference.append((sentence_id, sentence_id, text_hy, en[sentence_id]))
    return reference, asr, sorted(missing)


def device_name(device):
    return torch.cuda.get_device_name() if device == "cuda" else (platform.processor() or platform.machine())


def run_input(name, items, mt, run_id, device, load_s, asr_csv):
    print(f"\n=== {name}: {len(items)} sentences on {device} ({torch.get_num_threads()} CPU threads) ===")
    proc = psutil.Process()
    ram_peak = proc.memory_info().rss
    rows, hyps, refs, times = [], [], [], []
    for key, sentence_id, text_hy, ref_en in items:
        t = time.time()
        out = mt.translate(text_hy)
        dt = time.time() - t
        ram_peak = max(ram_peak, proc.memory_info().rss)
        hyps.append(out.text_en)
        refs.append(ref_en)
        times.append(dt)
        rows.append({"key": key, "sentence_id": sentence_id, "text_hy": text_hy, "text_en": out.text_en,
                     "reference_en": ref_en, "tokens_in": out.tokens_in, "tokens_out": out.tokens_out,
                     "capped": out.capped, "seconds": f"{dt:.3f}"})
        print(f"[{key}] {dt:.2f}s{'  [CAPPED]' if out.capped else ''}  {out.text_en}")

    with open(RESULTS / f"{run_id}_nllb-600m_{name}_{device}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    result = {"run": run_id, "model": MT_MODEL, "input": name, "device": device, "device_name": device_name(device),
              "threads": torch.get_num_threads(), "sentences": len(items),
              "bleu": f"{sacrebleu.corpus_bleu(hyps, [refs]).score:.1f}",
              "chrf": f"{sacrebleu.corpus_chrf(hyps, [refs]).score:.1f}",
              "mean_s": f"{np.mean(times):.3f}", "p95_s": f"{np.percentile(times, 95):.3f}",
              "max_s": f"{max(times):.3f}",
              "tokens_in_mean": f"{np.mean([r['tokens_in'] for r in rows]):.1f}",
              "tokens_out_mean": f"{np.mean([r['tokens_out'] for r in rows]):.1f}",
              "capped": sum(r["capped"] for r in rows), "load_s": f"{load_s:.1f}",
              "vram_peak_gb": f"{torch.cuda.max_memory_allocated() / 1e9:.2f}" if device == "cuda" else "-",
              "ram_peak_gb": f"{ram_peak / 1e9:.2f}", "asr_csv": Path(asr_csv).name}
    summary = RESULTS / "mt_summary.csv"
    if summary.exists():
        with open(summary, encoding="utf-8") as f:
            header = f.readline().strip().split(",")
        if header != SUMMARY_COLUMNS:
            raise SystemExit(f"{summary} has older columns {header}. Rename it (e.g. mt_summary_old.csv) and re-run.")
    new = not summary.exists()
    with open(summary, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SUMMARY_COLUMNS)
        if new:
            w.writeheader()
        w.writerow(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    parser.add_argument("--threads", type=int, default=None, help="CPU threads (default: PyTorch default)")
    parser.add_argument("--asr-csv", default=None,
                        help="FastConformer FLEURS result to translate (default: newest in bench/results)")
    parser.add_argument("--inputs", nargs="+", default=["reference", "asr"], choices=["reference", "asr"])
    args = parser.parse_args()
    if args.threads:
        torch.set_num_threads(args.threads)
    if args.device == "cuda" and not torch.cuda.is_available():
        raise SystemExit("CUDA not available to PyTorch; use --device cpu or install the CUDA build.")

    asr_csv = args.asr_csv
    if asr_csv is None:
        found = sorted(RESULTS.glob("*_nvidia-fastconformer_fleurs.csv"))
        if not found:
            raise SystemExit("No *_nvidia-fastconformer_fleurs.csv in bench/results. "
                             "Run: python bench/bench_asr.py --models nvidia-fastconformer --fleurs 100")
        asr_csv = found[-1]
    reference, asr, missing = load_inputs(asr_csv)
    if missing:
        print(f"WARNING: {len(missing)} FLEURS sentence ids have no en_us transcript and are left out: "
              + ", ".join(missing))
    items = {"reference": reference, "asr": asr}

    t0 = time.time()
    mt = Translator(args.device)
    mt.warmup()
    load_s = time.time() - t0

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = [run_input(name, items[name], mt, run_id, args.device, load_s, asr_csv) for name in args.inputs]

    print(f"\n{'input':10} {'dev':4} {'n':>4} {'BLEU':>5} {'chrF':>5} {'mean s':>7} {'p95 s':>6} {'max s':>6} "
          f"{'tok in':>6} {'tok out':>7} {'capped':>6} {'VRAM GB':>8} {'RAM GB':>7}")
    for r in results:
        print(f"{r['input']:10} {r['device']:4} {r['sentences']:>4} {r['bleu']:>5} {r['chrf']:>5} {r['mean_s']:>7} "
              f"{r['p95_s']:>6} {r['max_s']:>6} {r['tokens_in_mean']:>6} {r['tokens_out_mean']:>7} "
              f"{r['capped']:>6} {r['vram_peak_gb']:>8} {r['ram_peak_gb']:>7}")
    print(f"\nSaved to {RESULTS}")


if __name__ == "__main__":
    main()
