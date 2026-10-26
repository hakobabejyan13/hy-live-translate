"""Benchmark Armenian ASR models on the same clips: WER, CER, seconds per clip and footprint.

Footprint per model: parameter count, peak GPU memory (whole process, so CTranslate2 counts too) and
peak process RAM. Use --device cpu (optionally --threads N) to see how a model runs without a GPU.

Clip sets:
  hakob   bench/clips/hakob/<id>.wav with references in bench/sentences_hakob.tsv (record_clips.py)
  fleurs  first N clips of the FLEURS hy_am test split (--fleurs N), downloaded once into bench/clips/fleurs

Each model is loaded alone, warmed up on the first clip (not timed), run on every clip, then freed.
Results are saved in bench/results/:
  summary.csv                 one row per model and clip set, appended on every run
  <run>_<model>_<set>.csv     per-clip reference, transcript, WER and time

Setup (Python 3.12+, from the repo root):
  pip install -r requirements.txt -r bench\\requirements-bench.txt
"""

import argparse
import csv
import gc
import tarfile
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import numpy as np
import psutil
import soundfile as sf
import torch

SAMPLE_RATE = 16000
HERE = Path(__file__).parent
RESULTS = HERE / "results"


# ---------- models: each loader returns (transcribe(audio, path) -> str, parameter count) ----------

def n_params(model):
    return sum(p.numel() for p in model.parameters())


def load_whisper_turbo(device):
    """Current skeleton ASR: faster-whisper large-v3-turbo, same settings as skeleton.py (int8 on CPU)."""
    from faster_whisper import WhisperModel
    model = WhisperModel("large-v3-turbo", device=device, compute_type="float16" if device == "cuda" else "int8",
                         cpu_threads=torch.get_num_threads())

    def transcribe(audio, path):
        parts, _ = model.transcribe(audio, language="hy", beam_size=1, condition_on_previous_text=False)
        return " ".join(p.text.strip() for p in parts)
    return transcribe, 809_000_000  # CTranslate2 does not expose parameters; 809M per the OpenAI model card


def _hf_whisper(device, model_id, **generate_kwargs):
    from transformers import WhisperForConditionalGeneration, WhisperProcessor
    dtype = torch.float16 if device == "cuda" else torch.float32
    processor = WhisperProcessor.from_pretrained(model_id)
    model = WhisperForConditionalGeneration.from_pretrained(model_id, torch_dtype=dtype).to(device).eval()

    def transcribe(audio, path):
        features = processor.feature_extractor(audio, sampling_rate=SAMPLE_RATE, return_tensors="pt").input_features
        with torch.inference_mode():
            out = model.generate(features.to(device, dtype), language="hy", task="transcribe",
                                 num_beams=1, **generate_kwargs)
        return processor.batch_decode(out, skip_special_tokens=True)[0]
    return transcribe, n_params(model)


def load_buzzasr(device):
    """BuzzASR/armenian: whisper-large-v3 fully fine-tuned on FLEURS + Common Voice. Settings from its model card."""
    return _hf_whisper(device, "BuzzASR/armenian", no_repeat_ngram_size=3, repetition_penalty=1.2)


def load_chillarmo_turbo(device):
    """Chillarmo/whisper-large-v3-turbo-armenian: turbo fine-tuned on Common Voice 20 (drop-in for the current model)."""
    return _hf_whisper(device, "Chillarmo/whisper-large-v3-turbo-armenian")


def load_seamless(device):
    """facebook/seamless-m4t-v2-large, speech -> Armenian text (it can also go straight to English)."""
    from transformers import AutoProcessor, SeamlessM4Tv2ForSpeechToText
    model_id = "facebook/seamless-m4t-v2-large"
    dtype = torch.float16 if device == "cuda" else torch.float32
    processor = AutoProcessor.from_pretrained(model_id)
    model = SeamlessM4Tv2ForSpeechToText.from_pretrained(model_id, torch_dtype=dtype).to(device).eval()

    def transcribe(audio, path):
        inputs = processor.feature_extractor(audio, sampling_rate=SAMPLE_RATE, return_tensors="pt")
        inputs = {k: v.to(device) for k, v in inputs.items()}
        inputs["input_features"] = inputs["input_features"].to(dtype)
        with torch.inference_mode():
            out = model.generate(**inputs, tgt_lang="hye")
        return processor.decode(out[0], skip_special_tokens=True)
    return transcribe, n_params(model)


def load_nvidia_fastconformer(device):
    """nvidia/stt_hy_fastconformer_hybrid_large_pc: 115M FastConformer, best open model on ArmBench-ASR. Needs NeMo."""
    import nemo.collections.asr as nemo_asr
    model = nemo_asr.models.ASRModel.from_pretrained("nvidia/stt_hy_fastconformer_hybrid_large_pc",
                                                     map_location=device).to(device).eval()

    def transcribe(audio, path):
        out = model.transcribe([str(path)], batch_size=1, verbose=False)
        if isinstance(out, tuple):  # some NeMo versions return (best, all) for transducers
            out = out[0]
        hyp = out[0]
        return hyp.text if hasattr(hyp, "text") else hyp
    return transcribe, n_params(model)


MODELS = {
    "whisper-turbo": load_whisper_turbo,
    "buzzasr": load_buzzasr,
    "chillarmo-turbo": load_chillarmo_turbo,
    "seamless-m4t-v2": load_seamless,
    "nvidia-fastconformer": load_nvidia_fastconformer,
}


# ---------- clips ----------

def hakob_clips():
    refs = dict(line.split("\t", 1) for line in (HERE / "sentences_hakob.tsv").read_text(encoding="utf-8").splitlines()
                if line.strip())
    clips = []
    for clip_id, ref in refs.items():
        path = HERE / "clips" / "hakob" / f"{clip_id}.wav"
        if not path.exists():
            raise FileNotFoundError(f"{path} missing. Record the clips first: python bench/record_clips.py")
        clips.append((clip_id, path, ref))
    return clips


def fleurs_clips(n):
    from huggingface_hub import hf_hub_download
    out_dir = HERE / "clips" / "fleurs"
    out_dir.mkdir(parents=True, exist_ok=True)
    tsv = hf_hub_download("google/fleurs", "data/hy_am/test.tsv", repo_type="dataset")
    rows = [line.split("\t") for line in Path(tsv).read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = rows[:n]  # columns: id, file name, raw transcription, transcription, words, samples, gender
    if any(not (out_dir / r[1]).exists() for r in rows):
        tar_path = hf_hub_download("google/fleurs", "data/hy_am/audio/test.tar.gz", repo_type="dataset")
        wanted = {r[1] for r in rows}
        with tarfile.open(tar_path) as tar:
            for member in tar.getmembers():
                name = Path(member.name).name
                if name in wanted:
                    (out_dir / name).write_bytes(tar.extractfile(member).read())
    return [(r[1].removesuffix(".wav"), out_dir / r[1], r[2]) for r in rows]


def load_wav(path):
    audio, sr = sf.read(path, dtype="float32")
    if sr != SAMPLE_RATE or audio.ndim != 1:
        raise ValueError(f"{path}: expected 16 kHz mono, got {sr} Hz with shape {audio.shape}")
    return audio


# ---------- scoring ----------

def normalize(text):
    """Lowercase and drop punctuation/symbols (incl. Armenian ։ ՝ ՞ ՜ ՛ « »). Other scripts are kept, so
    hallucinations in the wrong script still count as errors."""
    text = text.lower().replace("և", "եւ")  # same ligature, two spellings; NeMo and Seamless write եւ
    text = "".join(c for c in text if c not in "՛՜՞")  # Armenian stress/question marks sit inside words
    text = "".join(" " if unicodedata.category(c)[0] in "PS" else c for c in text)
    return " ".join(text.split())


def edit_distance(a, b):
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        prev, row[0] = row[0], i
        for j, y in enumerate(b, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (x != y))
    return row[-1]


# ---------- main ----------

class Footprint:
    """Peak process RAM and peak GPU memory in use, sampled after load and after every clip."""

    def __init__(self, device):
        self.device, self.proc = device, psutil.Process()
        self.ram_peak = 0
        if device == "cuda":
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
            self.gpu_free_start, _ = torch.cuda.mem_get_info()
            self.gpu_peak = 0

    def sample(self):
        self.ram_peak = max(self.ram_peak, self.proc.memory_info().rss)
        if self.device == "cuda":
            used = self.gpu_free_start - torch.cuda.mem_get_info()[0]  # catches CTranslate2 too
            self.gpu_peak = max(self.gpu_peak, used, torch.cuda.max_memory_reserved())

    def vram_gb(self):
        return f"{self.gpu_peak / 1e9:.2f}" if self.device == "cuda" else "-"


def run_model(name, clips, clip_set, run_id, device):
    print(f"\n=== {name} on {clip_set} ({len(clips)} clips, {device}, {torch.get_num_threads()} CPU threads) ===")
    footprint = Footprint(device)
    t0 = time.time()
    transcribe, params = MODELS[name](device)
    load_s = time.time() - t0
    footprint.sample()
    audios = [load_wav(path) for _, path, _ in clips]
    transcribe(audios[0], clips[0][1])  # warm-up, not timed
    footprint.sample()

    rows, word_err, word_n, char_err, char_n, times, audio_s = [], 0, 0, 0, 0, [], 0.0
    for (clip_id, path, ref), audio in zip(clips, audios):
        t = time.time()
        hyp = transcribe(audio, path).strip()
        dt = time.time() - t
        footprint.sample()
        r, h = normalize(ref), normalize(hyp)
        we, ce = edit_distance(r.split(), h.split()), edit_distance(r, h)
        word_err, word_n, char_err, char_n = word_err + we, word_n + len(r.split()), char_err + ce, char_n + len(r)
        times.append(dt)
        audio_s += len(audio) / SAMPLE_RATE
        rows.append([clip_id, ref, hyp, f"{we / max(len(r.split()), 1):.3f}", f"{dt:.3f}"])
        print(f"[{clip_id}] {dt:.2f}s  {hyp}")

    with open(RESULTS / f"{run_id}_{name}_{clip_set}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "reference", "hypothesis", "wer", "seconds"])
        w.writerows(rows)

    result = {"run": run_id, "model": name, "clip_set": clip_set, "device": device,
              "threads": torch.get_num_threads(), "params_m": f"{params / 1e6:.0f}", "clips": len(clips),
              "wer": f"{100 * word_err / word_n:.1f}", "cer": f"{100 * char_err / char_n:.1f}",
              "mean_s": f"{np.mean(times):.3f}", "max_s": f"{max(times):.3f}",
              "rtf": f"{sum(times) / audio_s:.3f}", "load_s": f"{load_s:.1f}",
              "vram_gb": footprint.vram_gb(), "ram_gb": f"{footprint.ram_peak / 1e9:.2f}"}
    summary = RESULTS / "summary.csv"
    new = not summary.exists()
    if not new:
        with open(summary, encoding="utf-8") as f:
            header = f.readline().strip().split(",")
        if header != list(result):
            raise SystemExit(f"{summary} has older columns {header}. Rename it (e.g. summary_old.csv) and re-run.")
    with open(summary, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(result))
        if new:
            w.writeheader()
        w.writerow(result)

    del transcribe
    gc.collect()
    if device == "cuda":
        torch.cuda.empty_cache()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", nargs="+", default=["whisper-turbo", "buzzasr", "chillarmo-turbo", "seamless-m4t-v2"],
                        choices=list(MODELS))
    parser.add_argument("--fleurs", type=int, default=0, help="also run on the first N FLEURS hy_am test clips")
    parser.add_argument("--no-hakob", action="store_true", help="skip the recorded clips")
    parser.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    parser.add_argument("--threads", type=int, default=None, help="CPU threads (default: PyTorch default)")
    args = parser.parse_args()
    if args.threads:
        torch.set_num_threads(args.threads)
    if args.device == "cuda" and not torch.cuda.is_available():
        raise SystemExit("CUDA not available to PyTorch; use --device cpu or install the CUDA build.")

    sets = {}
    if not args.no_hakob:
        sets["hakob"] = hakob_clips()
    if args.fleurs:
        sets["fleurs"] = fleurs_clips(args.fleurs)
    if not sets:
        raise SystemExit("No clip set selected.")

    RESULTS.mkdir(exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = [run_model(m, clips, s, run_id, args.device) for m in args.models for s, clips in sets.items()]

    print(f"\n{'model':22} {'set':7} {'dev':4} {'params M':>8} {'WER%':>6} {'CER%':>6} {'mean s':>7} {'max s':>6} "
          f"{'RTF':>6} {'VRAM GB':>8} {'RAM GB':>7}")
    for r in results:
        print(f"{r['model']:22} {r['clip_set']:7} {r['device']:4} {r['params_m']:>8} {r['wer']:>6} {r['cer']:>6} "
              f"{r['mean_s']:>7} {r['max_s']:>6} {r['rtf']:>6} {r['vram_gb']:>8} {r['ram_gb']:>7}")
    print(f"\nSaved to {RESULTS}")


if __name__ == "__main__":
    main()
