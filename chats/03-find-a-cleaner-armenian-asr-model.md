# Find a cleaner Armenian ASR model

Thread transcript. Started 2026-10-24, last activity 2026-10-26.

**Hakob** · 2026-10-24 15:30:18 UTC

starting new  thread for selectio.py an PLAN.md first step  

---

_2026-10-24 15:30:31 UTC · Using folder C:\Users\hakob\Desktop\my_projecct\hy-live-translate_

---

<sub>2026-10-24 15:30:38 UTC</sub>

> **Progress checklist:** Run walking skeleton end to end
>
> ✱ Read PLAN.md, DECISIONS.md, Rules.docx and skeleton.py
> ○ Check Python/CUDA setup on the laptop
> ○ Fix anything blocking a first run
> ○ Hakob runs it live with real models
> ○ Record baseline latency in DECISIONS.md

---

<sub>2026-10-24 15:31:22 UTC</sub>

> **Progress checklist:** Run walking skeleton end to end
>
> ✓ Read PLAN.md, DECISIONS.md, Rules.docx and skeleton.py
> ✓ Fix setup snags: CUDA PyTorch build in requirements.txt, clear error if GPU missing
> ✱ Hakob runs it live with real models
> ○ Record baseline latency in DECISIONS.md

---

**Claude** · 2026-10-24 15:31:27 UTC

I took "selectio.py" to mean **skeleton.py**, so tell me if you meant another file. It's ready for its first live run on your laptop. I can read and edit the folder from here, but I can't run Windows Python or your mic, so this run is yours.

I made two small changes, neither committed:
- **requirements.txt** now pulls PyTorch from the CUDA 12.8 index. Plain `torch` from PyPI installs a CPU-only build on Windows, and the RTX 5070 needs CUDA 12.8 or newer. That build also ships the cuBLAS 12 and cuDNN 9 DLLs that faster-whisper needs. skeleton.py imports torch first, so it should find them without a separate CUDA install.
- **skeleton.py** now stops with a clear message if PyTorch can't see the GPU.

In PowerShell, from the repo folder:
```
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
python skeleton.py --list-devices
python skeleton.py --mic <index>
```
The first run downloads about 2.5 GB of models. Speak a few Armenian sentences, press Ctrl+C, and paste me the terminal output along with any errors. The latency CSV goes to `logs/`, and I'll read it from there and fill in DECISIONS.md.

If you hit a `cublas64_12.dll` or `cudnn` error, paste it and I'll fix it.

---

**Hakob** · 2026-10-24 15:41:28 UTC

push selection.py and requirements.txt to github  

---

**Claude** · 2026-10-24 15:41:33 UTC

Got it. I'll take that as skeleton.py and push it with requirements.txt to a branch on GitHub.

---

**Claude** · 2026-10-24 15:41:55 UTC

Pushed skeleton.py and requirements.txt to the branch [claude/project-thread-zh7eme](https://github.com/hakobabejyan13/hy-live-translate/tree/claude/project-thread-zh7eme). It's one commit and I didn't open a PR. Tell me if you want one into main.

I didn't push your local .gitignore change because you only named the two files. That change is what keeps `logs/` out of git, so commit it yourself before you run the skeleton, or tell me to add it to this branch.

---

**Hakob** · 2026-10-24 18:58:56 UTC

[10/24/2026 8:45 PM] Kali: Loading weights: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████| 512/512 [00:00<00:00, 36596.52it/s]  
Warning: You are sending unauthenticated requests to the HF Hub. Please set a HF_TOKEN to enable higher rate limits and faster downloads.  
Listening... (Ctrl+C to stop)  

[transformers] Both max_new_tokens (=128) and max_length`(=200) seem to have been set. `max_new_tokens will take precedence. Please refer to the documentation for more information. (https://huggingface.co/docs/transformers/main/en/main_classes/text_generation)  
[20:37:29]  hy: Հարև ձզ ինչ պեսեք?  
           en: What do you think of a black bear?  
           latency: capture 0.25s | vad 0.00s | queue 0.00s | asr 0.84s | mt 1.49s | cli 0.00s | total 2.58s   (logprob -0.42, no_speech 0.00)  

[transformers] Both max_new_tokens (=128) and max_length`(=200) seem to have been set. `max_new_tokens will take precedence. Please refer to the documentation for more information. (https://huggingface.co/docs/transformers/main/en/main_classes/text_generation)  
[20:37:39]  hy: Իմանունը առամ է։  
           en: The name is a dragon.  
           latency: capture 0.25s | vad 0.00s | queue 0.00s | asr 0.32s | mt 0.09s | cli 0.00s | total 0.67s   (logprob -0.16, no_speech 0.00)  

[transformers] Both max_new_tokens (=128) and max_length`(=200) seem to have been set. `max_new_tokens will take precedence. Please refer to the documentation for more information. (https://huggingface.co/docs/transformers/main/en/main_classes/text_generation)  
[20:37:46]  hy: Այսոր եղանակը շատ լավ է։  
           en: This is a very good weather.  
           latency: capture 0.25s | vad 0.00s | queue 0.00s | asr 0.35s | mt 0.11s | cli 0.00s | total 0.71s   (logprob -0.08, no_speech 0.00)  

[transformers] Both max_new_tokens (=128) and max_length`(=200) seem to have been set. `max_new_tokens will take precedence. Please refer to the documentation for more information. (https://huggingface.co/docs/transformers/main/en/main_classes/text_generation)  
[20:37:51]  hy: Ես սիրում եմ սուրջ խմել։  
           en: I like to drink seriously.  
           latency: capture 0.25s | vad 0.00s | queue 0.00s | asr 0.36s | mt 0.11s | cli 0.00s | total 0.72s   (logprob -0.11, no_speech 0.00)  

[transformers] Both max_new_tokens (=128) and max_length`(=200) seem to have been set. `max_new_tokens will take precedence. Please refer to the documentation for more information. (https://huggingface.co/docs/transformers/main/en/main_classes/text_generation)  
[20:37:57]  hy: որտեղ է մոտակա խանութը։  
           en: Where's the nearest store?  
           latency: capture 0.25s | vad 0.00s | queue 0.00s | asr 0.35s | mt 0.13s | cli 0.00s | total 0.72s   (logprob -0.11, no_speech 0.00)  

[transformers] Both max_new_tokens (=128) and max_length`(=200) seem to have been set. `max_new_tokens will take precedence. Please refer to the documentation for more information. (https://huggingface.co/docs/transformers/main/en/main_classes/text_generation)  
[20:38:02]  hy: մենք գնում է է տի դուն։  
           en: We're going to your house.  
           latency: capture 0.25s | vad 0.00s | queue 0.00s | asr 0.33s | mt 0.13s | cli 0.00s | total 0.71s   (logprob -0.56, no_speech 0.00)  

[transformers] Both max_new_tokens (=128) and max_length`(=200) seem to have been set. `max_new_tokens will take precedence. Please refer to the documentation for more information. (https://huggingface.co/docs/transformers/main/en/main_classes/text_generation)  
[20:38:07]  hy: հնդրում եմ եմ ուկ նեքինդ։  
           en: I'd like to ask you to take a look.  
           latency: capture 0.25s | vad 0.00s | queue 0.00s | asr 0.35s | mt 0.17s | cli 0.00s | total 0.78s   (logprob -0.49, no_speech 0.00)  

[transformers] Both max_new_tokens (=128) and max_length`(=200) seem to have been set. `max_new_tokens will take precedence. Please refer to the documentation for more information. (https://huggingface.co/docs/transformers/main/en/main_classes/text_generation)  
[20:38:12]  hy: Վաղը ես կաշխատեմ առավության։  
[10/24/2026 8:45 PM] Kali: en: I'm going to work in the kitchen tomorrow.  
           latency: capture 0.25s | vad 0.00s | queue 0.00s | asr 0.37s | mt 0.16s | cli 0.00s | total 0.77s   (logprob -0.08, no_speech 0.00)  

[transformers] Both max_new_tokens (=128) and max_length`(=200) seem to have been set. `max_new_tokens will take precedence. Please refer to the documentation for more information. (https://huggingface.co/docs/transformers/main/en/main_classes/text_generation)  
[20:38:18]  hy: Երևանը Հայաստանի մայրակ հաղաքն է։  
           en: Yerevan is the capital of Armenia.  
           latency: capture 0.25s | vad 0.00s | queue 0.00s | asr 0.37s | mt 0.13s | cli 0.00s | total 0.75s   (logprob -0.10, no_speech 0.00)  

[transformers] Both max_new_tokens (=128) and max_length`(=200) seem to have been set. `max_new_tokens will take precedence. Please refer to the documentation for more information. (https://huggingface.co/docs/transformers/main/en/main_classes/text_generation)  
[20:38:22]  hy: ཉնոր ཁ ག ཁ ག ག ཤསསསང  
           en: The first is the "Snow White".  
           latency: capture 0.25s | vad 0.00s | queue 0.00s | asr 2.03s | mt 0.13s | cli 0.00s | total 2.41s   (logprob -0.80, no_speech 0.00)  


Stopped. Latency log: logs\latency_20261024_203725.csv  

this is terminal output  
1. Բարև ձեզ, ինչպե՞ս եք։  
2. Իմ անունը Արամ է։  
3. Այսօր եղանակը շատ լավ է։  
4. Ես սիրում եմ սուրճ խմել։  
5. Որտե՞ղ է մոտակա խանութը։  
6. Մենք գնում ենք դեպի տուն։  
7. Խնդրում եմ, օգնեք ինձ։  
8. Վաղը ես կաշխատեմ առավոտյան։  
9. Երևանը Հայաստանի մայրաքաղաքն է։  
10. Շնորհակալություն, ցտեսություն։  

in this text  

---

**Claude** · 2026-10-24 18:59:03 UTC

The first live run works. I'll score it against your 10 sentences, then log the WER/CER and latency in DECISIONS.md.

---

<sub>2026-10-24 19:02:31 UTC</sub>

> **Progress checklist:** Run walking skeleton end to end
>
> ✓ Read PLAN.md, DECISIONS.md, Rules.docx and skeleton.py
> ✓ Fix setup snags: CUDA PyTorch build in requirements.txt, clear error if GPU missing
> ✓ Push skeleton.py + requirements.txt to branch (approved)
> ✓ Hakob runs it live with real models
> ✓ Record live WER/CER and latency in DECISIONS.md
> ✓ Remove the max_new_tokens warning (local, not pushed)
> ○ Next: FLEURS hy_am baseline (PLAN.md step 3)

---

**Claude** · 2026-10-24 19:02:35 UTC · edited

The walking skeleton works end to end, and speed is fine: median **0.72 s** from end of speech to the English line, with the worst at 2.58 s. That's well under the 5 s limit. ASR takes about 0.35 s, MT about 0.13 s, and the steady 0.25 s capture time is the VAD waiting for silence.

Accuracy is the weak part. Scored against your 10 sentences, WER is **69.8%** and CER is **23.7%**. Without the last line, those are 56% and 16%. Most errors are near-miss spellings like սուրջ for սուրճ, which NLLB then turns into confident nonsense ("drink seriously", "the name is a dragon"). Only about 3 of the 10 translations were right. Line 10 came out as Tibetan-script garbage, a Whisper hallucination, though its low logprob (-0.80) makes it easy to spot.

I logged all of this in DECISIONS.md, both the project copy and the one in your local folder. I also removed the `max_new_tokens` warning from your local skeleton.py; that change isn't pushed. The latency CSV wasn't in this folder, so you probably ran from another clone. That's fine, since the terminal output had everything I needed.

Next per PLAN.md is the FLEURS baseline on about 100 clips. Want me to write that script?

---

**Hakob** · 2026-10-24 19:28:54 UTC

Hold on the FLEURS baseline. Before moving forward, we need to fix the ASR accuracy issues. Instead of tuning parameters right now, please do some research and propose alternative ASR models for Armenian to see if we can get cleaner transcripts than Whisper large-v3-turbo. Let's evaluate a few model options and save these results for benchmarking  

---

**Claude** · 2026-10-24 19:29:06 UTC

Understood: pause FLEURS and compare other Armenian ASR models against Whisper turbo. I'll start by researching the candidates.

---

<sub>2026-10-24 19:29:08 UTC</sub>

> **Progress checklist:** Find a cleaner Armenian ASR model
>
> ✱ Research Armenian ASR candidates
> ○ Write benchmark script (runs on the laptop, same clips for every model)
> ○ Record test clips + references
> ○ Hakob runs benchmark; save results for comparison
> ○ Pick a model, log decision in DECISIONS.md

---

<sub>2026-10-24 19:31:18 UTC</sub>

> **Progress checklist:** Find a cleaner Armenian ASR model
>
> ✓ Research Armenian ASR candidates (ArmBench-ASR leaderboard + model cards)
> ✱ Write benchmark script (runs on the laptop, same clips for every model)
> ○ Hakob records test clips and runs the benchmark
> ○ Compare results, pick a model, log decision in DECISIONS.md

---

<sub>2026-10-24 19:33:04 UTC</sub>

> **Progress checklist:** Find a cleaner Armenian ASR model
>
> ✓ Research Armenian ASR candidates (ArmBench-ASR leaderboard + model cards)
> ✓ Write benchmark script + clip recorder (in bench/, not committed)
> ✓ Log decision 7 in DECISIONS.md
> ✱ Hakob records test clips and runs the benchmark
> ○ Compare results, pick a model, log in DECISIONS.md

---

**Claude** · 2026-10-24 19:33:13 UTC

I picked four Armenian ASR models to test against Whisper turbo and wrote a benchmark that runs all of them on the same clips. You need to run it on the laptop. The cloud can't download models from Hugging Face.

The candidates and their published WER on FLEURS (lower is better):
- **nvidia/stt_hy_fastconformer_hybrid_large_pc**: 15.0%. It's the best open model on [ArmBench-ASR](https://metric-ai-armbench-asr.static.hf.space/) and small (115M), so it should be fast. It needs NVIDIA's NeMo toolkit, which only documents Linux installs, so Windows may be bumpy.
- **facebook/seamless-m4t-v2-large**: 14.4%. It can also translate speech straight to English, which would replace NLLB.
- **BuzzASR/armenian**: 11.9%, as reported on [its model card](https://huggingface.co/BuzzASR/armenian). It's whisper-large-v3 fine-tuned for Armenian, and slower than turbo.
- **Chillarmo/whisper-large-v3-turbo-armenian**: 24.7%. It would be a near drop-in replacement for the current model.
- Current turbo, for comparison: plain whisper-large-v3 scores 51.8% there.

I skipped Meta's omniASR, MMS and Gemma, which score 37–53%. I logged this as decision 7 in DECISIONS.md.

From the repo folder:
```
pip install -r bench\requirements-bench.txt
python bench\record_clips.py --mic <index>
python bench\bench_asr.py
python bench\bench_asr.py --no-hakob --fleurs 100
```
The second step records your 10 sentences as WAV files; you can add more lines to `bench\sentences_hakob.tsv` first. The FLEURS run is optional, but 10 clips is a small sample. NeMo needs its own Python 3.12 venv, and the steps are at the top of `bench_asr.py`.

Results add up in `bench\results\summary.csv` as WER, CER and seconds per clip, and I'll read them from there. Nothing is committed yet.

---

**Hakob** · 2026-10-24 19:39:50 UTC

push everything in dev branch for testing  

---

**Claude** · 2026-10-24 19:39:56 UTC

Got it. I'll push the skeleton, the .gitignore and bench/ to a `dev` branch. PLAN.md and DECISIONS.md stay out.

---

**Claude** · 2026-10-24 19:40:28 UTC

Pushed to [dev](https://github.com/hakobabejyan13/hy-live-translate/tree/dev). It went in as one commit on top of the skeleton commit, which `dev` already had, and it has `skeleton.py` (with the warning fix), `requirements.txt`, `.gitignore` and the `bench/` scripts. PLAN.md, DECISIONS.md, `logs/` and your recorded clips are ignored and stay local.

Your local folder already has the same files, so you can test from it as it is. If you want to check out `dev` there, git will refuse until you move the untracked copies out of the way, because the branch has the same files.

---

**Hakob** · 2026-10-24 19:42:54 UTC

I picked four Armenian ASR models to test against Whisper turbo and wrote a benchmark that runs all of them on the same clips. You need to run it on the laptop. The cloud can't download models from Hugging Face.  
The candidates and their published WER on FLEURS (lower is better):  

* nvidia/stt_hy_fastconformer_hybrid_large_pc: 15.0%. It's the best open model on [ArmBench-ASR](https://metric-ai-armbench-asr.static.hf.space/) and small (115M), so it should be fast. It needs NVIDIA's NeMo toolkit, which only documents Linux installs, so Windows may be bumpy.  
* facebook/seamless-m4t-v2-large: 14.4%. It can also translate speech straight to English, which would replace NLLB.  
* BuzzASR/armenian: 11.9%, as reported on [its model card](https://huggingface.co/BuzzASR/armenian). It's whisper-large-v3 fine-tuned for Armenian, and slower than turbo.  
* Chillarmo/whisper-large-v3-turbo-armenian: 24.7%. It would be a near drop-in replacement for the current model.  
* Current turbo, for comparison: plain whisper-large-v3 scores 51.8% there.  

I skipped Meta's omniASR, MMS and Gemma, which score 37–53%. I logged this as decision 7 in DECISIONS.md.  
From the repo folder:  

```
pip install -r bench\requirements-bench.txt
python bench\record_clips.py --mic <index>
python bench\bench_asr.py
python bench\bench_asr.py --no-hakob --fleurs 100

```

The second step records your 10 sentences as WAV files; you can add more lines to `bench\sentences_hakob.tsv` first. The FLEURS run is optional, but 10 clips is a small sample. NeMo needs its own Python 3.12 venv, and the steps are at the top of `bench_asr.py`.  
Results add up in `bench\results\summary.csv` as WER, CER and seconds per clip, and I'll read them from there. Nothing is committed yet.  

---

**Claude** · 2026-10-24 19:42:58 UTC

That's my earlier message pasted back with nothing added. Did you mean to ask something about it? One line in it is out of date: everything is now on `dev`, so "nothing is committed yet" no longer holds. Otherwise the steps still apply. Record your clips, run `python bench\bench_asr.py`, and tell me when `bench\results\summary.csv` has results, or paste any error you hit.

---

**Hakob** · 2026-10-24 19:44:18 UTC

i now check in second laptop with rtx 5070 and send you resluts  

---

**Claude** · 2026-10-24 19:44:21 UTC

Sounds good. On that laptop, run `git clone -b dev https://github.com/hakobabejyan13/hy-live-translate` and then follow the same steps. I can't reach that folder from here, so paste the summary table the script prints at the end (or `bench\results\summary.csv`).

---

**Hakob** · 2026-10-24 19:44:53 UTC

you give me steps for testing  

---

**Claude** · 2026-10-24 19:45:02 UTC

Here are the steps for a fresh laptop, in PowerShell. You'll need Python 3.12, git, and about 15 GB of free disk for the models.

**1. Get the code and install**
```
git clone -b dev https://github.com/hakobabejyan13/hy-live-translate
cd hy-live-translate
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt -r bench\requirements-bench.txt
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```
The last line should print `True` and the RTX 5070's name.

**2. Record your test clips**
```
python skeleton.py --list-devices
python bench\record_clips.py --mic <index>
```
For each sentence, press Enter, read it, then press Enter again. Use `--only 03 07` to redo specific ones.

**3. Run the benchmark** (4 models: turbo, BuzzASR, Chillarmo, Seamless)
```
python bench\bench_asr.py
python bench\bench_asr.py --no-hakob --fleurs 100
```
The first run downloads the models, so it's slow. The second run is optional and uses 100 FLEURS clips.

**4. NVIDIA model** (separate venv, may fail on Windows)
```
deactivate
py -3.12 -m venv .venv-nemo
.venv-nemo\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install "nemo-toolkit[asr]" soundfile huggingface_hub
python bench\bench_asr.py --models nvidia-fastconformer
```
If NeMo won't install, send me the error and skip this step.

**5. Send me** the table printed at the end, or the contents of `bench\results\summary.csv`.

---

**Hakob** · 2026-10-26 22:42:04 UTC

this all result(also in my own test)  

---

**Claude** · 2026-10-26 22:42:12 UTC

Got the 8 result files. I'll score them on equal terms and post a comparison.

---

<sub>2026-10-26 22:43:19 UTC</sub>

> **Progress checklist:** Find a cleaner Armenian ASR model
>
> ✓ Research Armenian ASR candidates (ArmBench-ASR leaderboard + model cards)
> ✓ Write benchmark script + clip recorder
> ✓ Hakob ran the benchmark (4 of 5 models; BuzzASR not run)
> ✓ Score fairly, save results to bench/results/ and DECISIONS.md
> ✱ Hakob picks the ASR model
> ○ Swap it into skeleton.py and re-run live

---

**Claude** · 2026-10-26 22:43:26 UTC

The NVIDIA FastConformer is the clear winner. It's the most accurate and about 10× faster than the others.

| Model | FLEURS WER / CER | Your clips WER | Time per clip |
|---|---|---|---|
| **nvidia FastConformer** | **10.6% / 3.3%** | **0%** | **0.08 s** |
| Seamless M4T v2 | 12.1% / 4.1% | 4.9% | 0.78 s |
| Chillarmo turbo | 17.2% / 7.0% | 4.9% | 0.80 s |
| Whisper turbo (current) | 42.9% / 13.0% | 90% | 0.70 s |

The Whisper rows also show why we're switching. Turbo hallucinated Tibetan script on your clips again, and Chillarmo got stuck repeating "մմմմ" on one long clip. The NVIDIA model had no hallucinations. One caveat is that it was trained on FLEURS's training split, so FLEURS flatters it a little. BuzzASR wasn't in your results, but nothing here suggests it would change the pick.

I scored every model the same way and treated `և` and `եւ` as the same, since NeMo and Seamless write `եւ`. I added that rule to `bench_asr.py`. The results are saved in `bench\results\` and DECISIONS.md, on your main laptop only, not pushed.

NeMo installed on your second laptop, so the hard part is done. The next step is to swap the NVIDIA model into `skeleton.py` and run the live test again.

---

**Decision card** · 2026-10-26 22:43:29 UTC

> Which ASR model should the skeleton use from now on?
>
> 1. **NVIDIA FastConformer** (recommended): I swap it into skeleton.py (NeMo venv, Python 3.12) and you re-run the live test; NLLB stays for translation.
> 2. **Seamless M4T v2**: Slightly less accurate and ~10x slower, but it could also replace NLLB by translating speech straight to English.
> 3. **Keep Whisper turbo**: No change; we'd tune its parameters instead, with ~43% WER as the starting point.
>
> Reason: Best WER and CER on both test sets, no hallucinations, 0.08 s per clip leaves lots of room in the 5 s budget.

---

<sub>2026-10-26 22:44:10 UTC</sub>

> **Progress checklist:** Find a cleaner Armenian ASR model
>
> ✓ Research Armenian ASR candidates (ArmBench-ASR leaderboard + model cards)
> ✓ Write benchmark script + clip recorder
> ✓ Hakob ran the benchmark (4 of 5 models; BuzzASR not run)
> ✓ Score fairly, save results to bench/results/ and DECISIONS.md
> ✓ Draft NVIDIA version of skeleton.py (ready, not applied to your folder yet)
> ✱ Hakob picks the ASR model
> ○ Apply the swap and re-run live

---

**Hakob** · 2026-10-26 22:53:30 UTC

Good results. Before we lock this into skeleton.py, can we check the parameter counts and VRAM/CPU footprint for these models? I want to make sure the final choice runs well on lower-spec hardware too. Let's compare their sizes and pick the best lightweight yet accurate option  

---

**Claude** · 2026-10-26 22:53:43 UTC

Makes sense. I'll add parameter count, GPU memory, RAM and CPU-only speed to the benchmark so the same script measures them on your laptop.

---

_2026-10-26 22:53:45 UTC · Hakob chose option 1_

---

<sub>2026-10-26 22:53:46 UTC</sub>

> **Progress checklist:** Pick a lightweight, accurate ASR model
>
> ✓ Accuracy benchmark (NVIDIA best: 10.6% WER FLEURS)
> ✱ Add footprint measurement to bench_asr.py: params, peak VRAM, peak RAM, CPU-only speed
> ○ Hakob runs the footprint benchmark (GPU + CPU-only)
> ○ Compare size vs accuracy, pick model, log in DECISIONS.md
> ○ Apply the swap to skeleton.py and re-run live

---

<sub>2026-10-26 23:01:41 UTC</sub>

> **Progress checklist:** Pick a lightweight, accurate ASR model
>
> ✓ Accuracy benchmark (NVIDIA best: 10.6% WER FLEURS)
> ✓ Add footprint measurement to bench_asr.py: params, peak VRAM, peak RAM, --device cpu, --threads
> ✱ Smoke-test the new script with a stand-in model (installing torch here)
> ○ Hakob runs the footprint benchmark (GPU + CPU-only)
> ○ Compare size vs accuracy, pick model, log in DECISIONS.md
> ○ Apply the swap to skeleton.py and re-run live

---

<sub>2026-10-26 23:03:19 UTC</sub>

> **Progress checklist:** Pick a lightweight, accurate ASR model
>
> ✓ Accuracy benchmark (NVIDIA best: 10.6% WER FLEURS)
> ✓ Add footprint measurement to bench_asr.py: params, peak VRAM, peak RAM, --device cpu, --threads
> ✓ Smoke-tested the new script
> ✱ Hakob runs the footprint benchmark (GPU + CPU-only)
> ○ Compare size vs accuracy, pick model, log in DECISIONS.md
> ○ Apply the swap to skeleton.py and re-run live

---

**Claude** · 2026-10-26 23:03:25 UTC

**Should I push the updated benchmark to `dev`?** Your second laptop needs it, and I won't push without your OK.

The benchmark now records each model's parameter count, peak GPU memory and peak RAM. It can also run without a GPU (`--device cpu`), and `--threads 4` mimics a weaker CPU. I tested the script with a stand-in model.

Published sizes, so you know what to expect:

| Model | Params | Rough VRAM (fp16) | FLEURS WER |
|---|---|---|---|
| **nvidia FastConformer** | **115M** | **~0.5 GB** | **10.6%** |
| Whisper turbo / Chillarmo | 809M | ~2 GB | 42.9% / 17.2% |
| BuzzASR | 1.55B | ~3.5 GB | not run |
| Seamless M4T v2 | 2.3B in total (speech-to-text is a part of that) | ~5 GB | 12.1% |

The NVIDIA model is the smallest by 7× and also the most accurate, so I expect it to win here too. The CPU run will show whether it keeps up in real time without a GPU.

Once it's on that laptop, run this from the repo folder:
```
python bench\bench_asr.py --models nvidia-fastconformer --no-hakob --fleurs 30
python bench\bench_asr.py --models nvidia-fastconformer --no-hakob --fleurs 30 --device cpu --threads 4
python bench\bench_asr.py --models whisper-turbo chillarmo-turbo seamless-m4t-v2 --no-hakob --fleurs 30
python bench\bench_asr.py --models whisper-turbo chillarmo-turbo seamless-m4t-v2 --no-hakob --fleurs 30 --device cpu --threads 4
```
Run the first two in your NeMo venv and the last two in your main venv. If the script complains about an old `summary.csv`, rename that file and run again. Then paste me the final tables.

---

**Hakob** · 2026-10-26 23:04:14 UTC

Instead of updating and re-running the benchmark script, can you just provide the parameter counts, VRAM, and CPU estimates theoretically based on known model specs?  

---

<sub>2026-10-26 23:04:59 UTC</sub>

> **Progress checklist:** Pick a lightweight, accurate ASR model
>
> ✓ Accuracy benchmark (NVIDIA best: 10.6% WER FLEURS)
> ✓ Size, VRAM and CPU estimates from model specs (in DECISIONS.md)
> ✓ Pick: NVIDIA FastConformer (decision 8)
> ✓ Swap applied to skeleton.py + requirements.txt in your local folder (not pushed)
> ○ Hakob re-runs skeleton.py live with the new model

---

**Claude** · 2026-10-26 23:05:06 UTC

Here are the estimates, worked out from each model's published specs rather than measured. The NVIDIA model is still the pick. It's the smallest and the most accurate, and it's the only one likely to run in real time without a GPU.

| Model | Params | Est. VRAM | Est. CPU per 5 s clip (4 cores) | FLEURS WER |
|---|---|---|---|---|
| **nvidia FastConformer** | **115M** | **~0.6–1 GB** | **~0.3–0.8 s** | **10.6%** |
| Whisper turbo | 809M | ~2–2.5 GB | ~2–5 s | 42.9% |
| Chillarmo turbo | 809M | ~2–2.5 GB | ~4–10 s | 17.2% |
| BuzzASR | 1.55B | ~3.5–4 GB | ~10–20 s | not run |
| Seamless M4T v2 | ~1.5B of 2.3B | ~4–5 GB | ~5–15 s | 12.1% |

The estimates use 2 bytes per parameter at fp16, plus about 0.5 GB of GPU overhead. Whisper-based models always process a padded 30 s window, so short clips save nothing on CPU. The NVIDIA model's cost grows with clip length instead. With NLLB added (about 1.2 GB), the whole pipeline should fit on a 4 GB GPU.

I logged this as decision 8 in DECISIONS.md and switched `skeleton.py` and `requirements.txt` in your local folder to the NVIDIA model. It needs Python 3.12 and NeMo, the same setup as your NeMo venv. Nothing is pushed. Next, run `python skeleton.py --mic <index>` there and send me the output.

---

**Hakob** · 2026-10-26 23:11:24 UTC

We have decided on NVIDIA FastConformer as our primary ASR model. The ASR benchmark phase is officially complete. Let's start a fresh thread/context for Step 2: NLLB MT integration and latency optimization for the full VAD-ASR-MT pipeline. Please outline the exact code updates needed for Step 2.  

---

**Claude** · 2026-10-26 23:11:37 UTC

I've asked for a new thread for Step 2, NLLB integration and pipeline latency, and passed along where things stand. It will start with the outline of code changes you asked for. The ASR choice is logged as decision 8 in DECISIONS.md, and your local `skeleton.py` already uses the NVIDIA model, though it's not pushed yet. I'm closing this thread.

---

<sub>2026-10-26 23:11:37 UTC</sub>

> **Progress checklist:** Pick a lightweight, accurate ASR model
>
> ✓ Accuracy benchmark (NVIDIA best: 10.6% WER FLEURS)
> ✓ Size, VRAM and CPU estimates from model specs (in DECISIONS.md)
> ✓ Pick: NVIDIA FastConformer (decision 8)
> ✓ Swap applied to skeleton.py + requirements.txt in your local folder (not pushed)
> ✓ Handed off to a new thread for Step 2 (MT integration + latency)

---

**Hakob** · 2026-10-26 23:13:05 UTC · edited

push and merge dev into main  

---

**Claude** · 2026-10-26 23:13:11 UTC

Got it. I'll push the NVIDIA skeleton, the footprint benchmark and the results to `dev`, then merge `dev` into `main`.

---

**Claude** · 2026-10-26 23:13:51 UTC

Done. I pushed `dev` and merged it into [main](https://github.com/hakobabejyan13/hy-live-translate/commits/main) as a fast-forward, so the two branches are now identical (`ee413a0`). Main now has the NVIDIA FastConformer skeleton, the benchmark that measures model footprint, and the saved results in `bench/results/`. PLAN.md and DECISIONS.md stay out of the repo.

Your local folder still has these files as untracked copies, so `git pull` will refuse to overwrite them. Move or delete those copies first, then pull. The local files match what's on main, so you won't lose anything.
