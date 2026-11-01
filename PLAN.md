# PLAN: Live Armenian Transcription -> English Translation

## 1. Goal

A Python command-line program that listens to two live audio sources at once, transcribes
Armenian speech, translates it to English, and prints both to the terminal with a speaker label.

Typical use: the user is on a Google Meet call. Their own voice comes from the microphone,
the other participants come from the laptop speakers (system audio).

## 2. Constraints

- **Local models only.** No cloud speech or translation APIs. Downloading model weights once is fine.
- **Latency <= 5 s** from the end of a spoken phrase to the English line appearing.
- **Armenian (Eastern, `hy`) speech -> English text.**
- **Two audio sources:** microphone + system audio loopback.
- **Terminal output only.** No GUI, installer, echo handling or cross-session speaker memory.
- **Fail fast and loud.** No silent fallbacks, retry loops or complex timeouts. Errors crash with a clear message; uncertain results are labelled, never hidden.
- **Simplicity first.** One fixed model per stage, no model bake-off. Get the end-to-end pipeline working before anything else.

## 3. Answers to clarifying questions

| Question | Answer |
|---|---|
| What are the two sources? | Microphone + other participants through the speakers (e.g. Google Meet). |
| Target machine? | Windows 11 laptop: Intel Core Ultra 7 255HX, RTX 5070 Laptop GPU (8 GB VRAM), 32 GB RAM. All development testing is done here, on live calls. |
| Operating system? | Windows 11. System audio is captured through WASAPI loopback. |
| Speaker identification? | Mic is always `ME`. Remote participants are `SPEAKER 1`, `SPEAKER 2`, ... (numbered in order of first appearance, reset every session). Uncertain cases are `SPEAKER ?`. |
| Test data? | No private Armenian recordings with transcripts. Live calls for real use; a small public Armenian set (FLEURS `hy_am`) only for the baseline WER/CER required in DECISIONS.md. |

## 4. Models (fixed)

| Stage | Model | Runtime |
|---|---|---|
| ASR | `nvidia/stt_hy_fastconformer_hybrid_large_pc` (NeMo FastConformer, decision 8) with phrase boosting of glossary loanwords, alpha 2.0 (decision 15) | NeMo, RNNT greedy_batch, Python 3.12+ |
| Translation | NLLB-200 (`facebook/nllb-200-distilled-600M`), `hye_Armn -> eng_Latn` | Hugging Face `transformers`, fp16 on CUDA, fp32 on CPU, greedy |
| VAD | Silero VAD | `silero-vad` package, one model per source |
| Speaker embedding | NVIDIA TitaNet-Large (`nvidia/speakerverification_en_titanet_large`, decision 11) | NeMo, on CUDA |

The ASR and translation models sit behind small module interfaces (section 5), so swapping one later
only touches that module.

## 5. Architecture

```
 mic ──────> audio_capture ─┐
                            ├─> vad ─> asr ─> translate ─> cli
 loopback ─> audio_capture ─┘          └──> speaker ──────┘
```

One capture thread per source. Each source has its own VAD that cuts its stream into segments.
Finished segments from both sources go into one queue. A single worker takes segments in order and
runs ASR, speaker identification and translation, then prints the line.

Every segment carries timestamps from each stage so latency is logged per stage:
`capture -> VAD -> ASR -> MT -> CLI`.

### Modules, inputs and outputs

| Module | Input | Output |
|---|---|---|
| `audio_capture` | Device (mic or WASAPI loopback), source name | Stream of `AudioChunk(source: "mic" \| "loopback", samples: np.ndarray[float32], 16 kHz mono, t_captured: float)` |
| `vad` | `AudioChunk` stream for one source | `Segment(source, samples, t_speech_start, t_speech_end, t_vad_done)`. Cut at pauses, max length ~5 s so long speech never blows the latency budget. |
| `asr` | `Segment` | `Transcript(segment, text_hy: str, avg_logprob: float, no_speech_prob: float, t_asr_done)` |
| `speaker` | `Segment` | Label: `ME`, `SPEAKER N` or `SPEAKER ?` (rules below) |
| `translate` | `Transcript` | `Translation(transcript, text_en: str, t_mt_done)` |
| `cli` | `Translation` + label | One printed line plus the latency breakdown, with `t_printed` taken at print time |

Example line:

```
[11:42:07] SPEAKER 1  hy: Բարև, ինչպե՞ս ես։  en: Hi, how are you?
           latency: capture 0.10s | vad 0.35s | asr 0.90s | mt 0.25s | cli 0.01s | total 1.61s
```

`total` = `t_printed - t_speech_end` (time from the end of speech to the line on screen).

### `audio_capture`: resampling and downmixing

`audio_capture` is the only module that deals with device formats. Everything after it receives
16 kHz mono `float32`.

- **Loopback (WASAPI):** opened at the device's native format, usually 48 kHz stereo. The module
  downmixes to mono (mean of channels) and resamples to 16 kHz (polyphase resampling, e.g.
  `scipy.signal.resample_poly`, or `soxr`).
- **Microphone:** same treatment if the device does not deliver 16 kHz mono natively.
- The native rate and channel count are read from the device, not assumed. If the device cannot be
  opened, or reports a format the code does not handle, the program exits with a clear error.
- Library: `soundcard` (supports WASAPI loopback on Windows). Its API is checked against the docs
  before coding, and the choice is logged in DECISIONS.md.

### `speaker`: labelling rules (no silent fallbacks)

- Mic segments -> always `ME`.
- Loopback segments -> compute a speaker embedding and compare (cosine similarity) to the centroids
  of the speakers seen so far in this session:
  - similarity >= `MATCH_THRESHOLD` -> that `SPEAKER N` (centroid updated);
  - similarity < `NEW_THRESHOLD` (or no speakers yet) -> new `SPEAKER N+1`;
  - anything in between (an uncertain match) -> `SPEAKER ?`.
- Segments shorter than ~1 s -> `SPEAKER ?` without trying to match, because embeddings from very short audio are unreliable.
- `SPEAKER ?` lines are still transcribed and translated in full; only the label says the speaker is unknown.
  Nothing is dropped or guessed quietly.
- Thresholds start as constants at the top of the module, tuned on live calls, and logged in DECISIONS.md.

## 6. Build order

1. **PLAN.md and DECISIONS.md** (this step).
2. **Walking skeleton** (`skeleton.py`): mic only -> Silero VAD -> NeMo FastConformer ->
   NLLB-200 -> terminal, with latency logged at each stage (`capture -> VAD -> ASR -> MT -> CLI`).
   No loopback, no speaker labels. Run it live on the RTX 5070 laptop.
3. **Baseline metrics:** run the same ASR and MT on a small FLEURS `hy_am` sample to record WER, CER
   and BLEU/chrF in DECISIONS.md, next to the live latency numbers.
4. **Module isolation**, one at a time, each with unit tests listed in TESTS.md:
   1. `audio_capture` with WASAPI loopback (48 kHz stereo -> 16 kHz mono).
   2. Two sources merged into one queue, mic labelled `ME`.
   3. `speaker` for remote participants (`SPEAKER N` / `SPEAKER ?`).
   4. `cli` formatting.
5. **Live end-to-end test** on a real Google Meet call, checking labels, translation quality and latency <= 5 s.

**Status (2026-10-30): all steps done.** Final Meet test (run `20261030_164955`, Hakob + 1 remote, 21 lines):
latency median 0.51 s, max 2.03 s, nothing over 5 s; speaker labels correct. Details in DECISIONS.md
(decisions 15-19 and the baseline table). README.md is on `dev`.

Commit after every working step. If a fix fails three times, revert to the last working commit.

## 7. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| ASR weak on Armenian or on English/Russian loanwords | Poor transcripts and translations | Done: whisper-turbo (WER ~70% live) replaced by NeMo FastConformer (FLEURS WER 10.6%); loanwords handled by the glossary plus phrase boosting (decisions 13-15). |
| RTX 5070 (Blackwell) needs recent CUDA / cuDNN / CTranslate2 / PyTorch builds | Skeleton does not run on GPU | Check library support for this GPU before installing; log the working versions in DECISIONS.md. |
| Latency over 5 s | Fails the requirement | Per-stage latency logging shows which stage is slow; cap segment length at ~5 s. |
| Loopback format differs between devices (44.1 vs 48 kHz, stereo vs more channels) | Wrong pitch/speed or crash | Read the native format from the device, resample and downmix in `audio_capture`, fail loudly on anything unexpected. |
| Mic picks up the speakers (no echo handling by rule) | Remote speech transcribed twice, once as `ME` | Headphones recommended, not required: Hakob tested without them and it worked fine. Noted in the README as a known limitation. |
| ASR or MT invents text from noise or half-word fragments ("Հովհ." -> "John: I know.") | Fake lines | VAD only passes speech; segments under 0.5 s are held and joined to speech within 1 s, else dropped; one-letter or cut-off single words are logged as `fragment` and not printed (decisions 16-17). `avg_logprob` is printed per line so weak lines are visible. |
| Speaker embeddings unreliable on short segments, similar voices, overlap, call compression | Wrong labels | Short or uncertain segments are labelled `SPEAKER ?` instead of guessed. |

## 8. Testing strategy

- **Live testing** on the target Windows 11 / RTX 5070 laptop, on real calls with Armenian speech.
  Per-stage latency is logged for every line; the session log is kept for DECISIONS.md.
- **Baseline metrics** (DECISIONS.md): WER and CER (`jiwer`) and BLEU/chrF (`sacrebleu`) on a small
  FLEURS `hy_am` sample, for the one fixed model pair. No model comparison.
- **Unit tests** (`pytest`, listed in TESTS.md), each module tested alone with fixed inputs and WAV files,
  no live audio:
  - `audio_capture`: 48 kHz stereo test signal -> 16 kHz mono with correct length and frequency.
  - `vad`: silence + speech file -> expected segments; max segment length enforced.
  - `speaker`: mic -> `ME`; short segment -> `SPEAKER ?`; known embeddings -> correct match, new speaker, uncertain -> `SPEAKER ?`.
  - `cli`: line format and latency breakdown.
  - `asr` / `translate`: one known Armenian clip/sentence produces non-empty output of the right type (smoke test).
