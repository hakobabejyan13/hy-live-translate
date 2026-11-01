# Integrate NLLB and cut pipeline latency

Thread transcript. Started 2026-10-26, last activity 2026-10-29.

**Note from the coordinator** · 2026-10-26 23:11:46 UTC

> Extra handover from the ASR thread: NLLB-200 distilled 600M is already wired into skeleton.py. The NeMo version of skeleton.py hasn't been run live yet. The first live run with Whisper measured a median of 0.72 s end to end (ASR 0.35 s, MT about 0.13 s, VAD silence wait 0.25 s). The GitHub dev branch has the Whisper version plus bench/. The footprint-measuring bench_asr.py and bench/results/ exist only locally.

---

<sub>2026-10-26 23:11:52 UTC</sub>

> **Progress checklist:** Step 2 outline: NLLB MT + latency
>
> ✱ Read current skeleton.py, Rules.docx, PLAN/DECISIONS
> ○ Write the exact code-update outline
> ○ Share outline with Hakob for approval

---

<sub>2026-10-26 23:13:12 UTC</sub>

> **Progress checklist:** Step 2 outline: NLLB MT + latency
>
> ✓ Read current skeleton.py, Rules.docx, PLAN/DECISIONS
> ✓ Write the exact code-update outline
> ✱ Waiting for Hakob to approve the outline before coding

---

**Claude** · 2026-10-26 23:13:17 UTC

I've written the Step 2 outline as a doc: [Step 2 plan: NLLB integration and pipeline latency](https://claude.ai/artifact/36vuY6GujEFV8HUr4TG6js). No code has changed yet.

NLLB is already wired into `skeleton.py`, so Step 2 is mostly cleanup and measurement:
1. Live-run the NeMo skeleton as it is, to get a baseline. It hasn't run live yet.
2. Move ASR and MT into `asr.py` and `translate.py`. MT runs in fp16 on the GPU with greedy decoding and a token cap, and both models warm up at startup.
3. Flag any line slower than 5 s.
4. Add a FLEURS BLEU/chrF benchmark on GPU and CPU, plus smoke tests.

I'd like your answer on two things before I start coding:
1. Does a CPU-only run have to meet the 5 s limit too?
2. Are you OK with me creating the two module files now?

---

**Note from the coordinator** · 2026-10-26 23:13:54 UTC

> FYI: Hakob had the ASR thread push dev and fast-forward it into main (ee413a0). main and dev now both contain the NeMo skeleton, the footprint bench and bench/results. His local folder still has untracked copies of those files, so he has to move them before he can git pull.

---

**Hakob** · 2026-10-26 23:33:58 UTC

1. For the 5-second limit: let's test on GPU first, and then run it on CPU to see if we can hit under 5s there too.  
2. Yes, go ahead and create asr.py and translate.py now.  

Also, please make sure the code exports and saves all output metrics into CSV files (with clear columns for latency, token counts, and device type) so we can easily analyze the test results afterwards.  
Let's work on the dev branch. I approve the plan  

---

**Claude** · 2026-10-26 23:34:06 UTC

Got it. I'm starting on the dev branch with `asr.py` and `translate.py`, and every metric will go to a CSV.

---

<sub>2026-10-26 23:34:12 UTC</sub>

> **Progress checklist:** Step 2: NLLB MT + latency (dev branch)
>
> ✓ Outline approved by Hakob
> ✱ Write asr.py and translate.py
> ○ Update skeleton.py: warm-ups, over-budget flag, CSV columns (latency, tokens, device)
> ○ Write bench/bench_mt.py (BLEU/chrF + timing to CSV, GPU and CPU)
> ○ Smoke tests + TESTS.md
> ○ Push to dev
> ○ Hakob: live run on GPU, then CPU

---

<sub>2026-10-26 23:47:04 UTC</sub>

> **Progress checklist:** Step 2: NLLB MT + latency (dev branch)
>
> ✓ Outline approved by Hakob
> ✓ Write asr.py and translate.py
> ✓ Update skeleton.py: warm-ups, over-budget flag, CSV columns (latency, tokens, device)
> ✓ Write bench/bench_mt.py (BLEU/chrF + timing to CSV, GPU and CPU)
> ✓ Smoke tests + TESTS.md
> ✱ Dry-run the CSV and scoring code with stub models (real models only run on the laptop)
> ○ Push to dev
> ○ Hakob: live run on GPU, then CPU

---

<sub>2026-10-26 23:48:14 UTC</sub>

> **Progress checklist:** Step 2: NLLB MT + latency (dev branch)
>
> ✓ Outline approved by Hakob
> ✓ Write asr.py and translate.py
> ✓ Update skeleton.py: warm-ups, over-budget flag, CSV columns (latency, tokens, device)
> ✓ Write bench/bench_mt.py (BLEU/chrF + timing to CSV, GPU and CPU)
> ✓ Smoke tests + TESTS.md
> ✓ Dry-run the CSV and scoring code with stub models
> ✓ Push to dev (9861786), log decision 9 in DECISIONS.md
> ✱ Hakob: live run on GPU, then CPU, plus bench_mt

---

**Claude** · 2026-10-26 23:48:20 UTC

Step 2 is pushed to `dev` ([9861786](https://github.com/hakobabejyan13/hy-live-translate/commit/9861786)). The real models can't run here, so I've only checked the CSV and scoring code against stand-in models. Your laptop run will be the first real one.

**What changed**
- `asr.py` and `translate.py` are new. NLLB now runs in fp16 on the GPU, decodes greedily, and has a token cap. Both models warm up before listening starts.
- `skeleton.py` marks any line slower than 5 s.

**CSV files**
- `logs/latency_<run>.csv` has one row per line. Columns: every latency stage, `total_s`, `over_budget`, `device`, ASR and MT token counts, and the texts.
- `logs/sessions.csv` adds one row per run. Columns: device, VRAM peak, and median/p95/max latency.
- `bench/results/mt_summary.csv` holds BLEU/chrF, timing and token counts for the new translation benchmark.

**To run it**
1. Your untracked local copies of `skeleton.py`, `bench\` and the other files already on `dev` will block the pull, so move them out first. Then run `git checkout dev` and `git pull`.
2. Run `python skeleton.py`, then `python skeleton.py --device cpu`.
3. Run `python bench\bench_mt.py --device cuda`, then `--device cpu`. Add `pip install sacrebleu pytest` first, then run `pytest` for the smoke tests.

Send me the CSVs and I'll write up the results.

---

**Hakob** · 2026-10-29 12:28:48 UTC

this all results and logs  

---

**Claude** · 2026-10-29 12:29:28 UTC

Got all 8 files. I'm going through them now and will write up the GPU vs CPU results.

---

<sub>2026-10-29 12:31:11 UTC</sub>

> **Progress checklist:** Step 2: NLLB MT + latency (dev branch)
>
> ✓ Outline approved by Hakob
> ✓ asr.py, translate.py, skeleton CSVs, bench_mt.py, tests (9861786)
> ✓ Hakob: live run on GPU and CPU, plus bench_mt
> ✓ Results analysed and written up; baseline logged in DECISIONS.md
> ✓ Fixed GPU logprob scale and the single-thread CPU bug (61cbeb8)
> ○ Hakob: re-run CPU live test with the thread fix

---

**Claude** · 2026-10-29 12:31:15 UTC

Both devices are well under 5 s. The GPU median is **0.35 s** (max 0.55 s) and the CPU median is **1.08 s** (max 1.29 s). All 10 of your sentences translated correctly on both, compared with 3 of 10 with Whisper. On FLEURS, BLEU is 30.7 from the correct Armenian text and 28.1 from the ASR output. ASR errors cost very little now, so translation is the weaker stage.

The runs showed two bugs in my code. I fixed both and pushed to `dev` ([61cbeb8](https://github.com/hakobabejyan13/hy-live-translate/commit/61cbeb8)):
1. On GPU, `avg_logprob` was logging raw scores rather than probabilities.
2. Silero VAD sets PyTorch to one thread when it loads, so your CPU live run used a single thread.

Could you pull and re-run `python skeleton.py --device cpu`? It takes about 2 minutes. After that, we can either try the larger NLLB 1.3B for better translations or move on to Step 4 (loopback capture and speaker labels).

---

**Hakob** · 2026-10-29 12:32:18 UTC

(.venv-nemo) PS D:\_Projects\Hak_Task\hy-live-translate> pytest  
============================================================================== test session starts ===============================================================================  
platform win32 -- Python 3.12.10, pytest-9.2.0, pluggy-1.7.0  
rootdir: D:\_Projects\Hak_Task\hy-live-translate  
configfile: pytest.ini  
testpaths: tests  
plugins: anyio-4.15.1, hydra-core-1.3.2, platformdirs-4.13.5  
collected 5 items  

tests\test_asr.py ..                                                                                                                                                        [ 40%]  
tests\test_translate.py ...                                                                                                                                                 [100%]  

================================================================================ warnings summary ================================================================================  
tests/test_asr.py::test_numpy_input_runs_and_returns_text  
  D:\_Projects\Hak_Task\hy-live-translate\.venv-nemo\Lib\site-packages\torch\nn\modules\rnn.py:1013: UserWarning: dropout option adds dropout after all but last recurrent layer, so non-zero dropout expects num_layers greater than 1, but got dropout=0.2 and num_layers=1  
    super().__init__("LSTM", *args, **kwargs)  

tests/test_asr.py::test_numpy_input_runs_and_returns_text  
tests/test_asr.py::test_numpy_input_runs_and_returns_text  
  D:\_Projects\Hak_Task\hy-live-translate\.venv-nemo\Lib\site-packages\nemo\core\utils\cuda_python_utils.py:257: DeprecationWarning: The chararray class is deprecated and will be removed in a future release. Use an ndarray with a string or bytes dtype instead.  
    ptx = np.char.array(ptx)  

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html  
========================================================================= 5 passed, 3 warnings in 24.51s =========================================================================  

and this was write after pytest  

---

**Claude** · 2026-10-29 12:32:24 UTC

All 5 tests passed, so both models work and your clip `09.wav` transcribed correctly. The 3 warnings come from inside PyTorch and NeMo, not from our code, and you can ignore them.

If you had already pulled 61cbeb8, the ASR test also confirms the GPU confidence fix. It now checks that `avg_logprob` is between -5 and 0, and the old raw scores were -13 to -22.

The one thing still missing is the CPU live run with the thread fix: `python skeleton.py --device cpu`. Send me the new `sessions.csv` row. It should show `threads` = 20 instead of 1.

---

**Hakob** · 2026-10-29 12:56:36 UTC

only updated session.csv ?(added 1 row)  

---

**Claude** · 2026-10-29 12:56:41 UTC

Yes, that's expected. Every `skeleton.py` run adds one row to `logs/sessions.csv` and also creates a new `logs/latency_<run>.csv` with one row per sentence. `pytest` doesn't write any CSVs.

Please paste the new `sessions.csv` row here or attach both files. I'm mainly checking that `threads` now shows 20 instead of 1, and how much the CPU `mt_median_s` dropped from 0.72 s.

---

**Hakob** · 2026-10-29 12:57:54 UTC



---

<sub>2026-10-29 12:58:11 UTC</sub>

> **Progress checklist:** Step 2: NLLB MT + latency (dev branch)
>
> ✓ Outline approved by Hakob
> ✓ asr.py, translate.py, skeleton CSVs, bench_mt.py, tests (9861786)
> ✓ Hakob: live run on GPU and CPU, plus bench_mt
> ✓ Results analysed and written up; baseline logged in DECISIONS.md
> ✓ Fixed GPU logprob scale and the single-thread CPU bug (61cbeb8)
> ✓ CPU re-run with 20 threads: median 0.75 s, max 0.99 s

---

**Claude** · 2026-10-29 12:58:12 UTC

The thread fix worked. `threads` now shows 20, and the CPU-only run improved:

| CPU only | 1 thread | 20 threads |
|---|---|---|
| Total median | 1.08 s | **0.75 s** |
| Total max | 1.29 s | **0.99 s** |
| Translation median | 0.72 s | **0.39 s** |

That means both GPU and CPU finish within 1 s, and Step 2 is done. I added this row to DECISIONS.md.

---

**Decision card** · 2026-10-29 12:58:12 UTC

> What should we work on next?
>
> 1. **Step 4: loopback + speaker labels** (recommended): Next I build WASAPI loopback capture, put mic and loopback into one queue, and add ME / SPEAKER N labels, as Rules.docx requires.
> 2. **Try NLLB 1.3B first**: I add a --model flag to bench_mt.py, then you run it on FLEURS to compare BLEU and speed against the 600M model before we change anything live.
>
> Reason: The rules require two audio sources and speaker labels, and the current translation is already correct on your sentences. We can benchmark 1.3B later, because it only touches translate.py.

---

_2026-10-29 12:59:45 UTC · Hakob chose option 1: Step 4: loopback + speaker labels_

---

**Claude** · 2026-10-29 12:59:53 UTC

Step 4 (loopback capture and speaker labels) is getting its own new thread with everything from this one carried over. This thread is finished.
