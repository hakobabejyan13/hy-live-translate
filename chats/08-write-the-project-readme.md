# Write the project README

Thread transcript. Started 2026-10-30, last activity 2026-10-30.

<sub>2026-10-30 13:55:57 UTC</sub>

> **Progress checklist:** Write the project README
>
> ✱ Read code, plan and decisions for context
> ○ Draft README.md
> ○ Show draft to Hakob for approval
> ○ Commit and push after approval

---

**Note from the coordinator** · 2026-10-30 13:56:04 UTC

> Extra details from the audit thread for the README: Python 3.12+ venv .venv-nemo, CUDA torch from requirements.txt, models download on first run. Flags: --sources both|mic|loopback, --list-devices, --mic/--speaker, --save-audio, --boost. Also say there is no echo handling, which is why headphones are needed.

---

<sub>2026-10-30 13:57:13 UTC</sub>

> **Progress checklist:** Write the project README
>
> ✓ Read code, plan and decisions for context
> ✓ Draft README.md (committed locally, not pushed)
> ✱ Show draft to Hakob for approval
> ○ Push to dev after approval

---

**Claude** · 2026-10-30 13:57:17 UTC

The README draft is ready for you to read. It's committed on my side but not pushed yet, so tell me if it's okay to push it to `dev`, or what you'd like changed.

What it covers: what the program does, a "Use headphones" section near the top (no echo handling, so without headphones the mic picks up the call and lines show up twice), setup on Windows 11 with `.venv-nemo`, every command-line flag, what ME / SPEAKER N / SPEAKER ? mean, the logs and CSVs, tests and benchmarks, the latency and accuracy results (Meet call median 0.51 s, max 2.03 s), editing the glossary, and limitations.

Two things to check:
- The two example output lines at the top are made up to show the format, not taken from a real run. I can swap in lines from one of your real logs if you'd rather.
- The setup steps use `py -3.12 -m venv .venv-nemo`. If you created your venv another way, tell me and I'll match it.

---

**Hakob** · 2026-10-30 14:24:54 UTC

Overall, the README looks good and covers everything clearly! However, please make a few adjustments before committing:  

Softened Headphones Requirement: Change 'Use headphones' from a strict requirement to a recommendation. I've tested running it without headphones and it works totally fine. Mention that lack of echo cancellation is just a known limitation / future improvement area rather than a strict blocker.  

Clearer CPU Run Details: Make the instructions and examples for running on CPU clearer (e.g., explicitly showing python skeleton.py --device cpu --threads N and explaining how --threads helps tune performance on CPU).  

Repository Context: Briefly mention in a note that exported AI chat logs are saved in the chats/ folder, as required by the challenge spec.  

Please update the README draft with these points and push it to dev  

---

**Claude** · 2026-10-30 14:26:00 UTC

The README is on `dev` now ([bda29bf](https://github.com/hakobabejyan13/hy-live-translate/commit/bda29bf)), with your three changes:

- Headphones are now "recommended", and it says you tested without them and it worked fine. The missing echo cancellation is listed as a known limitation and future improvement.
- There's a new "Running on the CPU" section with `--device cpu --threads N` examples. It explains how to choose a thread count by looking at the `asr`/`mt` timings, and gives your numbers: 0.75 s median with 20 threads vs 1.08 s with 1.
- A "Repository notes" section at the end says the exported AI chat logs are in `chats/`.

One thing to know: `chats/` isn't on `dev` yet, so the README currently points to a folder that doesn't exist until you add it.

---

<sub>2026-10-30 14:26:00 UTC</sub>

> **Progress checklist:** Write the project README
>
> ✓ Read code, plan and decisions for context
> ✓ Draft README.md
> ✓ Show draft to Hakob for approval
> ✓ Apply Hakob's changes (headphones optional, CPU section, chats/ note)
> ✓ Push to dev (bda29bf)
