"""Walking skeleton: microphone -> Silero VAD -> faster-whisper (hy) -> NLLB-200 (hy->en) -> terminal.

Single source, no speaker labels. Logs latency at each stage:
capture -> VAD -> queue -> ASR -> MT -> CLI, measured from the end of speech.
"""

import argparse
import csv
import queue
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd
import torch
from faster_whisper import WhisperModel
from silero_vad import VADIterator, load_silero_vad
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

SAMPLE_RATE = 16000
CHUNK = 512  # Silero VAD expects 512-sample chunks at 16 kHz
MAX_SEGMENT_S = 5.0
PRE_ROLL_S = 1.0  # audio kept before speech start so the VAD start index stays reachable

ASR_MODEL = "large-v3-turbo"
MT_MODEL = "facebook/nllb-200-distilled-600M"


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


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mic", type=int, default=None, help="input device index (default: system default)")
    parser.add_argument("--list-devices", action="store_true", help="list audio devices and exit")
    parser.add_argument("--device", default="cuda", help="cuda or cpu")
    parser.add_argument("--compute-type", default="float16", help="faster-whisper compute type (float16, int8, ...)")
    args = parser.parse_args()

    if args.list_devices:
        print(sd.query_devices())
        return

    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA not available to PyTorch. Install the CUDA build: "
                           "pip install -r requirements.txt (it pulls torch from the cu128 index).")

    print(f"Loading ASR model {ASR_MODEL} on {args.device} ({args.compute_type})...")
    asr = WhisperModel(ASR_MODEL, device=args.device, compute_type=args.compute_type)
    print(f"Loading MT model {MT_MODEL} on {args.device}...")
    tokenizer = AutoTokenizer.from_pretrained(MT_MODEL, src_lang="hye_Armn")
    mt = AutoModelForSeq2SeqLM.from_pretrained(MT_MODEL).to(args.device).eval()
    eng_id = tokenizer.convert_tokens_to_ids("eng_Latn")

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"latency_{datetime.now():%Y%m%d_%H%M%S}.csv"
    log_file = open(log_path, "w", newline="", encoding="utf-8")
    log = csv.writer(log_file)
    log.writerow(["time", "audio_s", "forced_cut", "capture_s", "vad_s", "queue_s", "asr_s", "mt_s", "cli_s",
                  "total_s", "avg_logprob", "no_speech_prob", "text_hy", "text_en"])

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

            parts, _ = asr.transcribe(seg.samples, language="hy", beam_size=1, condition_on_previous_text=False)
            parts = list(parts)
            text_hy = " ".join(p.text.strip() for p in parts).strip()
            avg_logprob = float(np.mean([p.avg_logprob for p in parts])) if parts else float("nan")
            no_speech = float(np.mean([p.no_speech_prob for p in parts])) if parts else float("nan")
            t_asr_done = time.time()

            if text_hy:
                inputs = tokenizer(text_hy, return_tensors="pt").to(args.device)
                with torch.inference_mode():
                    out = mt.generate(**inputs, forced_bos_token_id=eng_id, max_new_tokens=128)
                text_en = tokenizer.batch_decode(out, skip_special_tokens=True)[0]
            else:
                text_en = ""
            t_mt_done = time.time()

            stamp = datetime.fromtimestamp(seg.t_speech_end).strftime("%H:%M:%S")
            cut = " [cut at 5s]" if seg.forced_cut else ""
            line = (f"[{stamp}]{cut}  hy: {text_hy or '(empty)'}\n"
                    f"           en: {text_en or '(empty)'}\n")
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
            print("           latency: " + " | ".join(f"{k} {v:.2f}s" for k, v in stages.items())
                  + f" | total {total:.2f}s   (logprob {avg_logprob:.2f}, no_speech {no_speech:.2f})\n", flush=True)
            log.writerow([stamp, f"{len(seg.samples) / SAMPLE_RATE:.2f}", seg.forced_cut,
                          *(f"{v:.3f}" for v in stages.values()), f"{total:.3f}",
                          f"{avg_logprob:.3f}", f"{no_speech:.3f}", text_hy, text_en])
            log_file.flush()
    except KeyboardInterrupt:
        print(f"\nStopped. Latency log: {log_path}")
    finally:
        stop.set()
        log_file.close()


if __name__ == "__main__":
    main()
