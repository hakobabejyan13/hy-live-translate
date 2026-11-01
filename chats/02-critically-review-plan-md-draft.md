# Critically review PLAN.md draft

Thread transcript. Started 2026-10-24, last activity 2026-10-24.

**Hakob** · 2026-10-24 13:06:53 UTC

I want you to review the draft of PLAN.md. You didn't write it, so look at it critically, without being polite, with new thread  
What to check:  

1. Are all the requirements from rules.docx present in the plan? What is missing or incomplete?  
2. Are there any contradictions between the plan, rules.docx, and my answers?  
3. Is there anything rules.docx does not require, but the plan added which complicates things?  
4. Which claims about models and libraries are you uncertain about, and how can I check them myself?  

At the end, give the 5 most important issues by risk, with a concrete recommendation for each.  
Do not change the plan, only write down the issues. I will decide what to change."  

_Attached: `PLAN.md critical review`_

---

**Claude** · 2026-10-24 13:07:02 UTC

First I'll get the latest unpushed PLAN.md and the rules, then check them against each other.

---

**Note from the coordinator** · 2026-10-24 13:07:07 UTC

> Note: current copies of PLAN.md and DECISIONS.md may also be in /mnt/project-files/plan/, and Rules.docx is in the project files. Confirm they match the planning thread's latest before reviewing.

---

<sub>2026-10-24 13:07:15 UTC</sub>

> **Progress checklist:** Critical review of PLAN.md
>
> ✱ Get the latest PLAN.md, DECISIONS.md and Rules.docx
> ○ Check rules coverage and contradictions
> ○ Flag added complexity and uncertain model/library claims
> ○ Write the review with top 5 risks

---

<sub>2026-10-24 13:09:05 UTC</sub>

> **Progress checklist:** Critical review of PLAN.md
>
> ✓ Get the latest PLAN.md, DECISIONS.md and Rules.docx
> ✓ Check rules coverage and contradictions
> ✓ Flag added complexity and uncertain model/library claims
> ✱ Write the review with top 5 risks

---

<sub>2026-10-24 13:10:11 UTC</sub>

> **Progress checklist:** Critical review of PLAN.md
>
> ✓ Get the latest PLAN.md, DECISIONS.md and Rules.docx
> ✓ Check rules coverage and contradictions
> ✓ Flag added complexity and uncertain model/library claims
> ✓ Write the review with top 5 risks

---

**Claude** · 2026-10-24 13:10:18 UTC

I've written the review in [PLAN.md critical review](https://claude.ai/artifact/Ans1mqQ9XudCdGfkKhj8HP). I didn't change the plan and didn't push anything.

The five biggest risks:

1. **The test data won't pick the right model for Meet calls.** FLEURS and Common Voice are clean read speech. The leading fine-tune, BuzzASR, was trained on both, so its scores there are inflated. NVIDIA's Armenian model goes from 7.7% WER on Common Voice to 61% on film dialogue.
2. **The stack may not install on Windows 11 with the RTX 5070.** NeMo, the toolkit for the best open model, is built for Linux, and the 50-series card needs very recent CUDA builds. Colab runs Linux, so testing there won't catch either problem.
3. **The build order goes against the rules.** The plan runs a 10-model study before the walking skeleton. The skeleton also uses plain Whisper, which gets 52% WER on Armenian.
4. **There's no latency budget.** The plan never splits the 5 s across stages, and its threading design contradicts itself.
5. **Remote speaker labels have no test recordings.** The plan also never says what a short segment prints.

Each risk comes with a concrete fix. The doc also covers rules coverage, contradictions, extra complexity, and a table of claims with how to check each one yourself.
