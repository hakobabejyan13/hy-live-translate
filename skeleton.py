"""Live Armenian -> English: microphone + system audio (WASAPI loopback) -> Silero VAD -> NVIDIA FastConformer (hy)
-> speaker label -> NLLB-200 (hy->en) -> terminal.

One capture thread and one VAD thread per source; finished segments from both go into one queue that a single
worker drains in order. Mic lines are labelled ME, system-audio lines SPEAKER 1, 2, ... or SPEAKER ? (see speaker.py).
Use headphones: there is no echo handling, so the mic would also pick up the other side of the call.

Logs latency at each stage, measured from the end of speech: capture -> VAD -> queue -> ASR -> speaker -> MT -> CLI.
Every run writes two CSV files in logs/:
  latency_<run>.csv   one row per segment: source, speaker, per-stage latency, token counts, device, texts;
                      dropped fragments (see short_lines.py) are logged with kind=fragment and nothing printed
  sessions.csv        one row per run, appended: device, load time, peak VRAM, latency median/p95/max
"""

import argparse
import csv
import platform
import queue
import threading
import time
import wave
from datetime import datetime
from pathlib import Path

import numpy as np
import torch

DEFAULT_THREADS = torch.get_num_threads()  # read before importing silero_vad: it calls torch.set_num_threads(1)

import silero_vad  # noqa: E402, F401  (imported here so its set_num_threads(1) runs before ours)

import audio_capture  # noqa: E402
from asr import ASR_MODEL, DEFAULT_BOOST_ALPHA, Recognizer  # noqa: E402
from glossary import GLOSSARY_FILE, Glossary  # noqa: E402
from short_lines import FRAGMENT, REPLY, classify  # noqa: E402
from speaker import SPEAKER_MODEL, UNKNOWN, Embedder, SpeakerLabeler  # noqa: E402
from translate import MT_MODEL, Translation, Translator  # noqa: E402
from vad import Segmenter, silero_detector  # noqa: E402

SAMPLE_RATE = audio_capture.SAMPLE_RATE
BUDGET_S = 5.0  # challenge limit: end of speech -> English line on screen
LOG_DIR = Path("logs")
LABEL_WIDTH = len("SPEAKER 10")

LINE_COLUMNS = ["time", "device", "source", "speaker", "spk_sim", "audio_s", "forced_cut", "capture_s", "vad_s",
                "queue_s", "asr_s", "spk_s", "mt_s", "cli_s", "total_s", "over_budget", "asr_tokens", "avg_logprob",
                "mt_tokens_in", "mt_tokens_out", "mt_capped", "text_hy_asr", "text_hy", "text_mt_in", "kind", "text_en", "wav"]
SESSION_COLUMNS = ["run", "sources", "device", "device_name", "threads", "asr_model", "mt_model", "speaker_model",
                   "load_s", "vram_peak_gb", "lines", "lines_mic", "lines_loopback", "speakers", "unknown_speaker",
                   "over_budget", "mt_capped", "total_median_s", "total_p95_s", "total_max_s", "asr_median_s",
                   "spk_median_s", "mt_median_s", "latency_csv"]


def save_wav(path, samples):
    """16-bit 16 kHz mono WAV, for checking speaker labels and cuts after a call."""
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes())


def segment_source(source, chunks, seg_queue, stop):
    """Run one source's chunks through its own VAD and put finished segments on the shared queue."""
    segmenter = Segmenter(source, silero_detector())
    while not stop.is_set():
        try:
            chunk = chunks.get(timeout=0.5)
        except queue.Empty:
            continue
        segment = segmenter.feed(chunk)
        if segment is not None:
            seg_queue.put(segment)


def start_source(source, device_name_arg, seg_queue, stop):
    """Open the device and start its capture and VAD threads; returns the threads."""
    device = audio_capture.open_device(source, device_name_arg)
    chunks = queue.Queue()
    capture = audio_capture.start(source, device, chunks, stop)
    vad = threading.Thread(target=segment_source, args=(source, chunks, seg_queue, stop), name=f"vad-{source}",
                           daemon=True)
    vad.start()
    return [capture, vad]


def device_name(device):
    return torch.cuda.get_device_name() if device == "cuda" else (platform.processor() or platform.machine())


def fmt_stat(values, fn):
    return f"{fn(values):.3f}" if values else "-"


def vram_peak_gb(device):
    return f"{torch.cuda.max_memory_allocated() / 1e9:.2f}" if device == "cuda" else "-"


def append_session(row):
    """Append one run to logs/sessions.csv; refuse to mix in rows with different columns."""
    path = LOG_DIR / "sessions.csv"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            header = f.readline().strip().split(",")
        if header != SESSION_COLUMNS:
            raise SystemExit(f"{path} has older columns {header}. Rename it (e.g. sessions_old.csv) and re-run.")
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SESSION_COLUMNS)
        if new:
            w.writeheader()
        w.writerow(row)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sources", default="both", choices=["both", "mic", "loopback"],
                        help="audio to listen to (default: both)")
    parser.add_argument("--mic", default=None, help="microphone name or part of it (default: system default)")
    parser.add_argument("--speaker", default=None,
                        help="speaker whose output is captured as loopback, name or part of it (default: system default)")
    parser.add_argument("--list-devices", action="store_true", help="list audio devices and exit")
    parser.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    parser.add_argument("--boost", type=float, default=DEFAULT_BOOST_ALPHA,
                        help=f"ASR phrase-boosting weight for glossary loanwords (default {DEFAULT_BOOST_ALPHA}; 0 = off)")
    parser.add_argument("--save-audio", action="store_true",
                        help="save every segment as logs/audio_<run>/<line>_<source>.wav (for tuning speaker labels)")
    parser.add_argument("--threads", type=int, default=DEFAULT_THREADS,
                        help=f"CPU threads for PyTorch (default: {DEFAULT_THREADS}, PyTorch's default here)")
    args = parser.parse_args()

    if args.list_devices:
        audio_capture.list_devices()
        return

    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA not available to PyTorch. Install the CUDA build: "
                           "pip install -r requirements.txt (it pulls torch from the cu128 index).")
    torch.set_num_threads(args.threads)
    sources = ["mic", "loopback"] if args.sources == "both" else [args.sources]

    t_load = time.time()
    glossary = Glossary.from_file()
    print(f"Glossary: {len(glossary.table)} loanword spellings from {GLOSSARY_FILE.name}")
    print(f"Loading ASR model {ASR_MODEL} on {args.device}...")
    asr = Recognizer(args.device)
    if args.boost > 0:
        phrases = glossary.boost_phrases()
        print(f"Boosting {len(phrases)} loanword spellings in the ASR (alpha {args.boost})...")
        asr.set_boosting(phrases, args.boost)
    print(f"Loading MT model {MT_MODEL} on {args.device}...")
    mt = Translator(args.device)
    embed = None
    if "loopback" in sources:
        print(f"Loading speaker model {SPEAKER_MODEL} on {args.device}...")
        embed = Embedder(args.device)
    print("Warming up...")
    asr.warmup()
    mt.warmup()
    if embed is not None:
        embed.warmup()
    speakers = SpeakerLabeler(embed)
    load_s = time.time() - t_load
    print(f"Ready in {load_s:.1f}s on {device_name(args.device)} ({torch.get_num_threads()} CPU threads"
          + (f", {vram_peak_gb(args.device)} GB VRAM peak)" if args.device == "cuda" else ")"))

    LOG_DIR.mkdir(exist_ok=True)
    run_id = f"{datetime.now():%Y%m%d_%H%M%S}"
    log_path = LOG_DIR / f"latency_{run_id}.csv"
    audio_dir = LOG_DIR / f"audio_{run_id}"
    if args.save_audio:
        audio_dir.mkdir()
    log_file = open(log_path, "w", newline="", encoding="utf-8")
    log = csv.DictWriter(log_file, fieldnames=LINE_COLUMNS)
    log.writeheader()
    totals, asr_times, spk_times, mt_times = [], [], [], []
    counts = {"mic": 0, "loopback": 0, "unknown": 0, "over": 0, "capped": 0, "fragments": 0}

    seg_queue = queue.Queue()
    stop = threading.Event()
    threads = []
    for source in sources:
        threads += start_source(source, args.mic if source == "mic" else args.speaker, seg_queue, stop)
    print("Listening... (Ctrl+C to stop)\n")

    try:
        while True:
            try:
                seg = seg_queue.get(timeout=0.5)
            except queue.Empty:
                dead = [t.name for t in threads if not t.is_alive()]
                if dead:
                    raise RuntimeError(f"Thread(s) {', '.join(dead)} stopped; see the error above.")
                continue
            t_asr_start = time.time()
            tr = asr.transcribe(seg.samples)
            fixed = glossary.apply(tr.text_hy)
            kind, reply = classify(fixed.for_mt)
            t_asr_done = time.time()
            if kind == FRAGMENT:  # half a word: not printed, and not counted in the latency stats
                log.writerow({"time": datetime.fromtimestamp(seg.t_speech_end).strftime("%H:%M:%S"),
                              "device": args.device, "source": seg.source,
                              "audio_s": f"{len(seg.samples) / SAMPLE_RATE:.2f}", "forced_cut": seg.forced_cut,
                              "asr_s": f"{t_asr_done - t_asr_start:.3f}", "asr_tokens": tr.tokens,
                              "avg_logprob": f"{tr.avg_logprob:.3f}", "text_hy_asr": tr.text_hy,
                              "text_hy": fixed.shown, "text_mt_in": fixed.for_mt, "kind": kind})
                log_file.flush()
                counts["fragments"] += 1
                continue
            spk = speakers.label(seg)
            t_spk_done = time.time()
            en = Translation(reply, 0, 0, False) if kind == REPLY else mt.translate(fixed.for_mt)
            t_mt_done = time.time()

            stamp = datetime.fromtimestamp(seg.t_speech_end).strftime("%H:%M:%S")
            indent = " " * (len("[00:00:00] ") + LABEL_WIDTH + 1)
            cut = "  [cut]" if seg.forced_cut else ""
            line = (f"[{stamp}] {spk.label:<{LABEL_WIDTH}} hy: {fixed.shown or '(empty)'}{cut}\n"
                    f"{indent}en: {en.text_en or '(empty)'}{'  [MT CAPPED]' if en.capped else ''}\n")
            print(line, end="", flush=True)
            t_printed = time.time()
            wav_name = ""
            if args.save_audio:  # after t_printed so saving never counts as latency
                wav_name = f"{len(totals) + 1:03d}_{seg.source}.wav"
                save_wav(audio_dir / wav_name, seg.samples)

            stages = {
                "capture": seg.t_closing_chunk - seg.t_speech_end,
                "vad": seg.t_vad_done - seg.t_closing_chunk,
                "queue": t_asr_start - seg.t_vad_done,
                "asr": t_asr_done - t_asr_start,
                "spk": t_spk_done - t_asr_done,
                "mt": t_mt_done - t_spk_done,
                "cli": t_printed - t_mt_done,
            }
            total = t_printed - seg.t_speech_end
            over_budget = total > BUDGET_S
            sim = "" if spk.similarity is None else f"{spk.similarity:.2f}"
            print(f"{indent}latency: " + " | ".join(f"{k} {v:.2f}s" for k, v in stages.items())
                  + f" | total {total:.2f}s" + (f"  OVER {BUDGET_S:.0f}s BUDGET" if over_budget else "")
                  + f"   (logprob {tr.avg_logprob:.2f}" + (f", spk sim {sim}" if sim else "") + ")\n", flush=True)
            log.writerow({"time": stamp, "device": args.device, "source": seg.source, "speaker": spk.label,
                          "spk_sim": sim, "audio_s": f"{len(seg.samples) / SAMPLE_RATE:.2f}",
                          "forced_cut": seg.forced_cut, **{f"{k}_s": f"{v:.3f}" for k, v in stages.items()},
                          "total_s": f"{total:.3f}", "over_budget": over_budget, "asr_tokens": tr.tokens,
                          "avg_logprob": f"{tr.avg_logprob:.3f}", "mt_tokens_in": en.tokens_in,
                          "mt_tokens_out": en.tokens_out, "mt_capped": en.capped,
                          "text_hy_asr": tr.text_hy, "text_hy": fixed.shown, "text_mt_in": fixed.for_mt,
                          "kind": kind, "text_en": en.text_en, "wav": wav_name})
            log_file.flush()
            totals.append(total)
            asr_times.append(stages["asr"])
            if kind != REPLY:  # a fixed reply never reaches NLLB
                mt_times.append(stages["mt"])
            if seg.source == "loopback":
                spk_times.append(stages["spk"])
            counts[seg.source] += 1
            counts["unknown"] += spk.label == UNKNOWN
            counts["over"] += over_budget
            counts["capped"] += en.capped
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        stop.set()
        log_file.close()
        append_session({"run": run_id, "sources": "+".join(sources), "device": args.device,
                        "device_name": device_name(args.device), "threads": torch.get_num_threads(),
                        "asr_model": ASR_MODEL, "mt_model": MT_MODEL,
                        "speaker_model": SPEAKER_MODEL if embed is not None else "-", "load_s": f"{load_s:.1f}",
                        "vram_peak_gb": vram_peak_gb(args.device), "lines": len(totals), "lines_mic": counts["mic"],
                        "lines_loopback": counts["loopback"], "speakers": speakers.speakers,
                        "unknown_speaker": counts["unknown"], "over_budget": counts["over"],
                        "mt_capped": counts["capped"], "total_median_s": fmt_stat(totals, np.median),
                        "total_p95_s": fmt_stat(totals, lambda x: np.percentile(x, 95)),
                        "total_max_s": fmt_stat(totals, max), "asr_median_s": fmt_stat(asr_times, np.median),
                        "spk_median_s": fmt_stat(spk_times, np.median), "mt_median_s": fmt_stat(mt_times, np.median),
                        "latency_csv": log_path.name})
        print(f"Dropped {counts['fragments']} half-word fragment(s), see kind=fragment in the log.")
        print(f"Latency log: {log_path}\nSession summary appended to {LOG_DIR / 'sessions.csv'}")


if __name__ == "__main__":
    main()
