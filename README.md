# hy-live-translate

Live Armenian speech to English text in the terminal, fully local. It listens to two sources at once,
your microphone and the call audio playing through your speakers (for example a Google Meet call),
writes down what was said in Armenian and prints an English translation under it, usually within
about half a second of the speaker finishing. Example output:

```
[16:17:02] ME         hy: Բարև, ինչպե՞ս ես։
                      en: Hi, how are you?
                      latency: capture 0.25s | vad 0.00s | queue 0.00s | asr 0.09s | spk 0.00s | mt 0.11s | cli 0.00s | total 0.45s   (logprob -0.12)

[16:17:05] SPEAKER 1  hy: Լավ եմ, merge-ը արեցի։
                      en: I'm fine, I did the merge.
                      latency: capture 0.25s | vad 0.00s | queue 0.00s | asr 0.10s | spk 0.03s | mt 0.12s | cli 0.00s | total 0.50s   (logprob -0.20, spk sim 0.71)
```

No cloud services are used. All models run on your machine, on an NVIDIA GPU or on the CPU.

## Headphones (recommended)

Headphones are recommended but not required: it was also tested without headphones and worked fine.
There is no echo cancellation, so with loud speakers the microphone can pick up
the other people in the call and some of their lines may appear twice: once from the call audio as
`SPEAKER N` and again from the mic as `ME`. Echo handling is a known limitation and a possible
future improvement.

## How it works

```
mic ──────► capture ─► VAD ─┐
                            ├─► queue ─► ASR (Armenian) ─► glossary ─► speaker label ─► MT (English) ─► terminal
loopback ─► capture ─► VAD ─┘
```

| Stage | What it does | File |
|---|---|---|
| Audio capture | Opens the mic and a WASAPI loopback of the speakers with `soundcard`, at the device's native format, then downmixes to mono and resamples to 16 kHz | `audio_capture.py` |
| VAD | Silero VAD cuts each source into speech segments. A segment ends after 300 ms of silence. Longer speech is cut from 5 s on at the first short pause between words (150 ms), so words are not split, or at 7 s if the speaker never pauses. Fragments under 0.5 s are joined to the speech that follows, or dropped | `vad.py` |
| ASR | NVIDIA FastConformer for Armenian (`nvidia/stt_hy_fastconformer_hybrid_large_pc`, NeMo), with phrase boosting for loanwords | `asr.py` |
| Glossary | Turns English and Russian loanwords that the ASR wrote in Armenian script (`քոմիթ`, `փուշ արա`) into `commit`, `push`, and so on, keeping Armenian endings (`commit-ները`) | `glossary.py`, `glossary.tsv` |
| Short lines | Drops half-word fragments (`Հովհ.`) and answers one-word replies (`Այո` -> `Yes.`) without the translation model | `short_lines.py` |
| Speaker labels | `ME` for the mic; TitaNet-Large voice embeddings to tell remote speakers apart | `speaker.py` |
| Translation | NLLB-200 distilled 600M (`facebook/nllb-200-distilled-600M`), Armenian to English, greedy decoding | `translate.py` |
| Terminal output and logs | Prints each line with its latency and writes CSV logs | `skeleton.py` |

## Requirements

- Windows 11 (audio capture uses WASAPI loopback; the rest is cross-platform)
- Python 3.12 (NeMo needs 3.12 or newer)
- An NVIDIA GPU with a recent driver is recommended. About 2 GB of VRAM is enough (peak 1.78 GB
  measured on an RTX 5070 Laptop GPU). CPU only also works and stays well under the 5 s limit.
- A few GB of disk for Python packages and models, and internet for the first run (models
  download from Hugging Face and are cached after that)

## Setup

From the repository folder, in PowerShell:

```powershell
py -3.12 -m venv .venv-nemo
.venv-nemo\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

`requirements.txt` pulls PyTorch from the CUDA 12.8 index, so the GPU build is installed on Windows.
Check that PyTorch sees the GPU:

```powershell
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name())"
```

If PowerShell refuses to run `Activate.ps1`, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

## Running

Activate the venv first (`.venv-nemo\Scripts\Activate.ps1`). Then find your audio devices:

```powershell
python skeleton.py --list-devices
```

This lists the microphones and the speakers whose output can be captured, plus the Windows defaults.
To translate a call, start the call (headphones recommended) and run:

```powershell
python skeleton.py
```

The first start downloads the models; later starts take a few seconds. When `Listening...` appears,
speak. Stop with `Ctrl+C`; a summary of the run is printed and saved.

| Option | Meaning |
|---|---|
| `--sources both\|mic\|loopback` | What to listen to (default `both`). `mic` alone is handy for testing your own voice |
| `--mic NAME` | Microphone to use, by name or part of it (default: Windows default mic) |
| `--speaker NAME` | Speakers or headphones whose sound is captured as the call audio (default: Windows default output) |
| `--list-devices` | List audio devices and exit |
| `--device cuda\|cpu` | Where the models run (default `cuda`; it stops with an error if CUDA is missing instead of quietly using the CPU) |
| `--threads N` | CPU threads for PyTorch (default: PyTorch's default for your CPU); matters mostly with `--device cpu`, see below |
| `--boost ALPHA` | ASR phrase boosting weight for glossary loanwords (default `2.0`; `0` turns it off) |
| `--save-audio` | Also save every segment as a WAV file, for checking speaker labels and cuts afterwards |

Examples:

```powershell
python skeleton.py --sources mic                      # only your microphone
python skeleton.py --speaker "Headphones" --save-audio
python skeleton.py --device cpu                       # no GPU
```

### Running on the CPU

Without an NVIDIA GPU, or to test CPU-only speed, add `--device cpu`. `--threads N` sets how many CPU
threads PyTorch uses for the models:

```powershell
python skeleton.py --device cpu                # PyTorch's default thread count
python skeleton.py --device cpu --threads 8    # fewer threads, leaves room for the call app
python skeleton.py --device cpu --threads 20   # all threads of a Core Ultra 7 255HX
```

More threads make ASR and translation faster, up to about the number of cores; on a laptop that is
also running a video call, a few less than that can be smoother. The `Ready in ...` line at startup
shows the thread count in use, and the `asr` and `mt` numbers on every line (and `asr_median_s`,
`mt_median_s` in `logs/sessions.csv`) show the effect, so try two or three values and keep the
fastest. On the test laptop with 20 threads the median was 0.75 s per line (max 0.99 s), against
1.08 s with a single thread.

## Reading the output

Each line shows the time the speaker stopped, who spoke, the Armenian text (`hy:`), the English
translation (`en:`) and how long each stage took.

| Label | Meaning |
|---|---|
| `ME` | Your microphone |
| `SPEAKER 1`, `SPEAKER 2`, ... | Remote voices from the call audio, numbered in the order they first speak. Numbers are only kept for one run |
| `SPEAKER ?` | A remote line that could not be given a speaker with confidence: shorter than 1 s, or a voice that is close to no known speaker. A new speaker number is only created from a segment of at least 2 s. The program shows `?` instead of guessing |

Flags that can appear on a line:

- `[cut]`: the person kept talking for over 5 s without a 300 ms pause, so the segment was cut at
  the next short gap between words (or at 7 s if there was none) and the rest follows on the next line.
- `[MT CAPPED]`: the translation hit its length limit (2 x input tokens + 16), which usually means
  the model started repeating itself.
- `OVER 5s BUDGET`: the line took longer than the 5 s limit from end of speech to screen.

Very short fragments such as half a word are not printed; they are counted in the summary at the end
and logged in the CSV.

## Logs

Every run writes to `logs/` (not committed):

| File | Contents |
|---|---|
| `logs/latency_<run>.csv` | One row per line: time, source, speaker and similarity, audio length, latency per stage and total, ASR and MT token counts, ASR confidence, the raw ASR text (`text_hy_asr`), the text after the glossary (`text_hy`, `text_mt_in`), the English and the WAV name. Dropped fragments have `kind=fragment` |
| `logs/sessions.csv` | One row per run, appended: device, load time, peak VRAM, line and speaker counts, latency median, p95 and max |
| `logs/audio_<run>/NNN_<source>.wav` | Each segment's audio, only with `--save-audio` |

If `sessions.csv` comes from an older version with different columns, the program stops and asks you
to rename it.

## Results

Measured on the target laptop (Intel Core Ultra 7 255HX, RTX 5070 Laptop GPU, 32 GB RAM). Latency is
measured from the end of speech to the English line on screen.

| Test | Device | Latency median | Max | Notes |
|---|---|---|---|---|
| Live Google Meet call, Hakob + 1 remote speaker, both sources (2026-10-30) | GPU | 0.51 s | 2.03 s | Lines above 1.5 s were the 5 s forced cuts; speaker labels correct |
| 10 read sentences, mic only | GPU | 0.35 s | 0.55 s | 10/10 translations correct, 1.78 GB VRAM peak |
| 10 read sentences, mic only | CPU, 20 threads | 0.75 s | 0.99 s | 10/10 translations correct |

Accuracy on the FLEURS Armenian test set (100 clips):

| | Score |
|---|---|
| ASR (FastConformer) | WER 10.6%, CER 3.3% |
| Translation from the ASR output | BLEU 28.1, chrF 56.6 |
| Translation from the reference Armenian text | BLEU 30.7, chrF 58.3 |

The ASR model was picked by comparing four Armenian models with `bench/bench_asr.py`
(whisper-large-v3-turbo scored 42.9% WER on the same clips). Raw results are in `bench/results/`.

## Tests

```powershell
pip install -r bench\requirements-bench.txt
pytest                 # everything
pytest -m "not slow"   # only the tests that load no model (a few seconds)
```

Tests marked `slow` load the real models. [TESTS.md](TESTS.md) lists every test and what it checks.
Opening the real WASAPI devices is not unit tested; check it with `--list-devices` and a call.

Benchmarks, separate from the tests:

- `bench/bench_asr.py`: ASR WER, CER and speed
- `bench/bench_mt.py`: translation BLEU, chrF and speed
- `bench/bench_boost.py`: phrase boosting weights on recorded loanword clips
- `bench/record_clips.py`: records your own test sentences

## Customising loanwords

`glossary.tsv` maps the Armenian-script spellings the ASR writes for English and Russian words to
the word to show and translate. Add a line when a word you use often comes out wrong; check the
`text_hy_asr` column of the latency CSV to see how the ASR spelled it. The file is checked at
startup, and a broken line stops the program with a message.

A word is only boosted in the ASR and fixed afterwards if it is in the file, so a new term (say `Telegram`)
needs a line before it can work. Put the normal spelling on one line (boosted) and the odd spellings
the ASR really wrote on another line marked `noboost`. A spelling can be two words when the ASR splits a
loanword (`աուտենտի ֆիկացիա`), and `mtonly` keeps a name in Armenian on screen while NLLB gets the Latin
spelling (`Հակոբ` is sent as `Hakob`, not translated as `Jacob`).

## Limitations

- No echo cancellation: headphones are recommended so the mic does not pick up the call (see above).
- Speaker numbers start again in every run; there is no memory of voices between runs.
- Very short remote lines (under 1 s) are always `SPEAKER ?`.
- The ASR writes only Armenian script, so English words depend on the glossary and boosting, and an
  unusual pronunciation can still be missed or turned into an Armenian word.
- Audio capture is written for Windows (WASAPI).

## Repository notes

The exported AI chat logs used while building this project are saved in the `chats/` folder, as the
challenge rules require.
