"""Walking skeleton: microphone -> Silero VAD -> NVIDIA FastConformer (hy) -> NLLB-200 (hy->en) -> terminal.

Single source, no speaker labels. Logs latency at each stage:
capture -> VAD -> queue -> ASR -> MT -> CLI, measured from the end of speech.

Every run writes two CSV files in logs/:
  latency_<run>.csv   one row per printed line: per-stage latency, token counts, device, texts
  sessions.csv        one row per run, appended: device, load time, peak VRAM, latency median/p95/max
"""

import argparse
import csv
import platform
import queue
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd
import torch

DEFAULT_THREADS = torch.get_num_threads()  # read before importing silero_vad: it calls torch.set_num_threads(1)

from silero_vad import VADIterator, load_silero_vad  # noqa: E402

from asr import ASR_MODEL, Recognizer  # noqa: E402
from translate import MT_MODEL, Translator  # noqa: E402

SAMPLE_RATE = 16000
CHUNK = 512  # Silero VAD expects 512-sample chunks at 16 kHz
MAX_SEGMENT_S = 5.0
PRE_ROLL_S = 1.0  # audio kept before speech start so the VAD start index stays reachable
BUDGET_S = 5.0  # challenge limit: end of speech -> English line on screen
LOG_DIR = Path("logs")

LINE_COLUMNS = ["time", "device", "audio_s", "forced_cut", "capture_s", "vad_s", "queue_s", "asr_s", "mt_s", "cli_s",
                "total_s", "over_budget", "asr_tokens", "avg_logprob", "mt_tokens_in", "mt_tokens_out", "mt_capped",
                "text_hy", "text_en"]
SESSION_COLUMNS = ["run", "device", "device_name", "threads", "asr_model", "mt_model", "load_s", "vram_peak_gb",
                   "lines", "over_budget", "mt_capped", "total_median_s", "total_p95_s", "total_max_s",
                   "asr_median_s", "mt_median_s", "latency_csv"]


@dataclass
class Segment:
    samples: np.ndarray
    t_speech_end: float  # wall time of the last speech sample
    t_closing_chunk: float  # wall time the chunk that closed the segment was captured
    t_vad_done: float
    forced_cut: bool  # True when cut at MAX_SEGMENT_S instead of at a pause


def capture_and_segment(device, seg_queue, stop):
    """Read the mic, run VAD on it and put finished speech segments on seg_queue."""
    vad = VADIterator(load_silero_vad(), sampling_rate=SAMPLE_RATE, min_silence_duration_ms=300, speech_pad_ms=100)
    chunk_queue = queue.Queue()

    def callback(indata, frames, time_info, status):
        chunk_queue.put((indata[:, 0].copy(), time.time(), status))

    buffer = np.zeros(0, dtype=np.float32)
    buffer_start = 0  # stream sample index of buffer[0]
    speech_start = None  # stream sample index where current speech began
    t_stream_start = None  # wall time of stream sample 0

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=CHUNK,
                        device=device, callback=callback):
        print("Listening... (Ctrl+C to stop)\n")
        while not stop.is_set():
            chunk, t_captured, status = chunk_queue.get()
            if status:
                raise RuntimeError(f"Audio input error: {status}")
            if t_stream_start is None:
                t_stream_start = t_captured - len(chunk) / SAMPLE_RATE
            buffer = np.concatenate([buffer, chunk])
            event = vad(torch.from_numpy(chunk))
            stream_pos = buffer_start + len(buffer)

            if event and "start" in event:
                speech_start = event["start"]

            end = None
            forced = False
            if event and "end" in event and speech_start is not None:
                end = event["end"]
            elif speech_start is not None and stream_pos - speech_start >= MAX_SEGMENT_S * SAMPLE_RATE:
                end = stream_pos
                forced = True

            if end is not None and end <= speech_start:
                # VAD closed the speech right after a forced cut: nothing left to emit.
                speech_start = None
            elif end is not None:
                samples = buffer[max(speech_start - buffer_start, 0):end - buffer_start]
                seg_queue.put(Segment(
                    samples=samples,
                    t_speech_end=t_stream_start + end / SAMPLE_RATE,
                    t_closing_chunk=t_captured,
                    t_vad_done=time.time(),
                    forced_cut=forced,
                ))
                # A forced cut keeps the VAD in speech state; the next segment starts here.
                speech_start = end if forced else None

            # Drop audio that can no longer be part of a segment.
            keep_from = speech_start if speech_start is not None else stream_pos - int(PRE_ROLL_S * SAMPLE_RATE)
            if keep_from > buffer_start:
                buffer = buffer[keep_from - buffer_start:]
                buffer_start = keep_from


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
    parser.add_argument("--mic", type=int, default=None, help="input device index (default: system default)")
    parser.add_argument("--list-devices", action="store_true", help="list audio devices and exit")
    parser.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    parser.add_argument("--threads", type=int, default=DEFAULT_THREADS,
                        help=f"CPU threads for PyTorch (default: {DEFAULT_THREADS}, PyTorch's default here)")
    args = parser.parse_args()

    if args.list_devices:
        print(sd.query_devices())
        return

    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA not available to PyTorch. Install the CUDA build: "
                           "pip install -r requirements.txt (it pulls torch from the cu128 index).")
    torch.set_num_threads(args.threads)

    t_load = time.time()
    print(f"Loading ASR model {ASR_MODEL} on {args.device}...")
    asr = Recognizer(args.device)
    print(f"Loading MT model {MT_MODEL} on {args.device}...")
    mt = Translator(args.device)
    print("Warming up...")
    asr.warmup()
    mt.warmup()
    load_s = time.time() - t_load
    print(f"Ready in {load_s:.1f}s on {device_name(args.device)} ({torch.get_num_threads()} CPU threads"
          + (f", {vram_peak_gb(args.device)} GB VRAM peak)" if args.device == "cuda" else ")"))

    LOG_DIR.mkdir(exist_ok=True)
    run_id = f"{datetime.now():%Y%m%d_%H%M%S}"
    log_path = LOG_DIR / f"latency_{run_id}.csv"
    log_file = open(log_path, "w", newline="", encoding="utf-8")
    log = csv.DictWriter(log_file, fieldnames=LINE_COLUMNS)
    log.writeheader()
    totals, asr_times, mt_times, over, capped = [], [], [], 0, 0

    seg_queue = queue.Queue()
    stop = threading.Event()
    worker = threading.Thread(target=capture_and_segment, args=(args.mic, seg_queue, stop), daemon=True)
    worker.start()

    try:
        while True:
            try:
                seg = seg_queue.get(timeout=0.5)
            except queue.Empty:
                if not worker.is_alive():
                    raise RuntimeError("Audio capture thread stopped; see the error above.")
                continue
            t_asr_start = time.time()
            tr = asr.transcribe(seg.samples)
            t_asr_done = time.time()
            en = mt.translate(tr.text_hy)
            t_mt_done = time.time()

            stamp = datetime.fromtimestamp(seg.t_speech_end).strftime("%H:%M:%S")
            cut = " [cut at 5s]" if seg.forced_cut else ""
            line = (f"[{stamp}]{cut}  hy: {tr.text_hy or '(empty)'}\n"
                    f"           en: {en.text_en or '(empty)'}{'  [MT CAPPED]' if en.capped else ''}\n")
            print(line, end="", flush=True)
            t_printed = time.time()

            stages = {
                "capture": seg.t_closing_chunk - seg.t_speech_end,
                "vad": seg.t_vad_done - seg.t_closing_chunk,
                "queue": t_asr_start - seg.t_vad_done,
                "asr": t_asr_done - t_asr_start,
                "mt": t_mt_done - t_asr_done,
                "cli": t_printed - t_mt_done,
            }
            total = t_printed - seg.t_speech_end
            over_budget = total > BUDGET_S
            print("           latency: " + " | ".join(f"{k} {v:.2f}s" for k, v in stages.items())
                  + f" | total {total:.2f}s" + (f"  OVER {BUDGET_S:.0f}s BUDGET" if over_budget else "")
                  + f"   (logprob {tr.avg_logprob:.2f})\n", flush=True)
            log.writerow({"time": stamp, "device": args.device, "audio_s": f"{len(seg.samples) / SAMPLE_RATE:.2f}",
                          "forced_cut": seg.forced_cut, **{f"{k}_s": f"{v:.3f}" for k, v in stages.items()},
                          "total_s": f"{total:.3f}", "over_budget": over_budget, "asr_tokens": tr.tokens,
                          "avg_logprob": f"{tr.avg_logprob:.3f}", "mt_tokens_in": en.tokens_in,
                          "mt_tokens_out": en.tokens_out, "mt_capped": en.capped,
                          "text_hy": tr.text_hy, "text_en": en.text_en})
            log_file.flush()
            totals.append(total)
            asr_times.append(stages["asr"])
            mt_times.append(stages["mt"])
            over += over_budget
            capped += en.capped
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        stop.set()
        log_file.close()
        append_session({"run": run_id, "device": args.device, "device_name": device_name(args.device),
                        "threads": torch.get_num_threads(), "asr_model": ASR_MODEL, "mt_model": MT_MODEL,
                        "load_s": f"{load_s:.1f}", "vram_peak_gb": vram_peak_gb(args.device), "lines": len(totals),
                        "over_budget": over, "mt_capped": capped,
                        "total_median_s": fmt_stat(totals, np.median),
                        "total_p95_s": fmt_stat(totals, lambda x: np.percentile(x, 95)),
                        "total_max_s": fmt_stat(totals, max), "asr_median_s": fmt_stat(asr_times, np.median),
                        "mt_median_s": fmt_stat(mt_times, np.median), "latency_csv": log_path.name})
        print(f"Latency log: {log_path}\nSession summary appended to {LOG_DIR / 'sessions.csv'}")


if __name__ == "__main__":
    main()
