# Fix poor transcription of tech terms

Thread transcript. Started 2026-10-31, last activity 2026-11-01.

**Hakob** · 2026-10-31 10:57:14 UTC

These are all the results for which the term (telegram, requirements) is not understood, and this time the transcription was even worse than in previous instances.  

_Attached: `glossary-fix.patch`, `glossary.tsv`, `vad-cut-fix.patch`, `meeting-run-fix.patch`, `evening-run-fix.patch`, `run-20261101-fix.patch`_

---

**Claude** · 2026-10-31 10:57:27 UTC

First I'll compare the failed lines in this run against the glossary and boosting setup, and check the forced audio cuts.

---

<sub>2026-10-31 10:57:40 UTC</sub>

> **Progress checklist:** Fix tech-term transcription
>
> ✱ Read the Meet test logs and the glossary code
> ○ Find why terms failed (glossary coverage, boosting active, cuts, loopback)
> ○ Implement fixes and test them
> ○ Report results

---

<sub>2026-10-31 11:00:55 UTC</sub>

> **Progress checklist:** Fix tech-term transcription
>
> ✓ Read the Meet test logs and the glossary code
> ✓ Find why terms failed (glossary coverage, boosting active, cuts, loopback)
> ✱ Add glossary entries, two-word spellings and name handling, with tests
> ○ Check the new entries against this run's text and FLEURS (no false hits)
> ○ Report results

---

<sub>2026-10-31 11:03:04 UTC</sub>

> **Progress checklist:** Fix tech-term transcription
>
> ✓ Read the Meet test logs and the glossary code
> ✓ Find why terms failed (glossary coverage, boosting active, cuts, loopback)
> ✓ Add glossary entries, two-word spellings and name handling, with tests (57 pass)
> ✓ Check the new entries against this run's text and FLEURS (0 of 377 sentences changed)
> ✓ Report results (not pushed, waiting for your OK)

---

**Claude** · 2026-10-31 11:03:14 UTC

**Can I push this fix to `dev`?** It's committed locally on the work branch but nothing is on GitHub yet, and `main` is untouched.

**Why the terms failed:** telegram, requirements, terminal, GitHub, local and browser were never in `glossary.tsv`. Boosting only helps words that are listed, so it couldn't do anything for them whether it was on or off. The log doesn't record whether boosting was on. Your startup line "Boosting N loanword spellings" would show it.

**Other things I checked:**
- The 5s cuts didn't cause the drop. Lines that were cut actually had better ASR confidence than the others. They did split a couple of words in half (`հանդիպ` | `ման`).
- Loopback audio is clearly harder to recognise than your mic. The model's median confidence score was −0.21 on loopback and −0.08 on the mic (closer to 0 is more confident). On top of that, this call had two fast remote speakers using lots of jargon.
- `Հովհ.` is what the model writes for noise and breaths. Those lines were already being dropped, and it was never a misheard "Hakob". Your name was transcribed correctly, but NLLB translated it as "Jacob".
- "Բայց ես մահացել եմ" came out the same from the loopback and later from your mic, so it was probably really said. It doesn't look made up.

**What changed:**
- Each new term now has a line for the normal spelling, which is boosted, and a line for the odd spellings the model really wrote, which isn't boosted. Examples: `ծելեգրամոգոտ` → Telegram bot, `ռեքորմենտ` → requirements, `քիթհաբ` → GitHub.
- Words the model splits in two are now joined back, for example `աուտենտի ֆիկացի` → authentication.
- Հակոբ now reaches NLLB as "Hakob" and still shows in Armenian on screen.

**How I tested it:** I ran the new glossary over the text from this call, and 17 lines now send the right English term to NLLB. It changed 0 of 377 plain-Armenian FLEURS sentences, and all 57 unit tests pass. I couldn't test the boosting on real audio because this run was recorded without `--save-audio`. If you have time before the meeting, read sentences 16–20 in `bench/sentences_loanwords.tsv` with `--save-audio`, then run `bench/bench_boost.py` on them.

The updated files and a patch are in [glossary-fix-20261031](/mnt/project-files/glossary-fix-20261031/).

---

**Note from the coordinator** · 2026-10-31 11:21:13 UTC

> Hakob approved pushing the glossary fix to dev (attached). Leave main untouched.

---

**Claude** · 2026-10-31 11:21:26 UTC

I pushed the fix to `dev` as commit e79557f, and `main` is untouched. On your laptop, run `git pull origin dev` before the meeting. Your startup line should then say "Boosting 255 loanword spellings", up from 221.

---

**Note from the coordinator** · 2026-10-31 11:43:32 UTC

> Hakob's follow-up is attached. He wants two things. First, add the terms he listed: task (Թասը), telegram bot, site (սայտ), and transcription (Տրանսսկիականի / transcriptia). Second, stop forced cuts from splitting a word in half, as in հանդիպ|ման. A word should be finished before the next line starts, for example by cutting at the nearest short pause instead of at a hard 5s limit. Ask him there if anything is unclear. Push only with his approval. main stays untouched.

---

<sub>2026-10-31 11:44:21 UTC</sub>

> **Progress checklist:** Fix word splits and more terms
>
> ✱ Add task, transcription spellings (Telegram bot and site are already in)
> ○ Cut long speech only at a real pause, so words are not split
> ○ Test on synthetic audio and the unit tests
> ○ Report and ask before pushing to dev

---

<sub>2026-10-31 11:48:20 UTC</sub>

> **Progress checklist:** Fix word splits and more terms
>
> ✓ Add task, transcription spellings (Telegram bot and site are already in)
> ✓ Cut long speech only at a real pause, so words are not split
> ✓ Test on synthetic audio and the unit tests (71 pass)
> ✱ Report and ask before pushing to dev

---

**Claude** · 2026-10-31 11:48:21 UTC

**Can I push this second fix to `dev` too?** It's committed locally, and `main` is untouched.

**Split words:** before, a cut at 5 s went into the single quietest 50 ms of the last 2 s. That is often the short silence inside a word, for example before the պ in `հանդիպ|ման`. Now, from 5 s on, the cut waits for a real gap between words, at least 150 ms of quiet. If the speaker doesn't pause at all, it cuts at 7 s. It still never looks more than 2 s back, so the line still appears well inside the 5 s limit.

I tested it on simulated fast speech, since I don't have your recordings. Cuts inside a word fell from 46% to 13%. The remaining splits happen when someone talks for 7 s without any pause. On screen the flag now reads `[cut]`.

**Words:**
- `Թասը` and `Թաասի` now become task. One risk: թաս also means "bowl", but that word is rare on a work call.
- `Տրանսսկիականի` now becomes "transcription կանի".
- Telegram bot and site were already in the first fix.

All three lines from this call now send the right English to NLLB. Plain-Armenian FLEURS sentences are still unchanged, and all 71 unit tests pass.

Updated files are in [glossary-fix-20261031](/mnt/project-files/glossary-fix-20261031/).

---

**Hakob** · 2026-10-31 11:56:31 UTC

Yes, push it to ⁠dev⁠. I'll check it with the 3-person meeting later and send you the results  

---

**Claude** · 2026-10-31 11:56:51 UTC

I pushed it to `dev` as commit 10e5516, and `main` is untouched. Run `git pull origin dev` before the meeting. If you add `--save-audio`, I can check the cuts and terms against the real recordings when you send the results.

---

**Note from the coordinator** · 2026-10-31 13:32:45 UTC

> Hakob sent a new log from the meeting run (latency_20261031_165728.csv, with wavs saved) and sessions 7.csv. His request is attached. Analyse the whole log for ASR misrecognitions, odd loanwords and fragment/short-line emission bugs, then fix them in glossary.tsv, short_lines.py or wherever else needed.
>
> Examples I noticed:
> - requirements: ռեյվորման, ռեյվքորմենտ, Ռեյգ ֆորմենս
> - telegram bot: էգրան բողոտ, տելեգրամ բորդ, Տելեգրան բ՞րդ, օրկրամոտ, Դելեկտեմբոտ, դելեգման/դելեգրան bot
> - LLM: Էլեմ, էլմ, Էլլմ ստուդիա (LM Studio)
> - ChatGPT: ջիպիտի
> - comp/computer: կոմպիտ
> - localhost / port: սպորտի
> - glossary: գլոսորեր
> - task: թազը
>
> Bugs:
> - կլուբնիկա is wrongly normalised to ելակ (strawberry). It is likely a misheard word, perhaps "Claude", so check it.
> - Filler lines like Հը։ and Հհը՞։ are emitted as sentences and translated as "I'm going to go." and "What is it?". These should be dropped as fragments.
> - սեյվ վայություն should be "save".
>
> Tell Hakob what you fixed. Do not push without his approval. main stays untouched.

---

<sub>2026-10-31 13:32:52 UTC</sub>

> **Progress checklist:** Fix issues from the meeting log
>
> ✱ Read every line of the meeting log
> ○ Fix glossary words and fragment lines
> ○ Test against this log and FLEURS
> ○ Report and ask before pushing

---

<sub>2026-10-31 13:34:38 UTC</sub>

> **Progress checklist:** Fix issues from the meeting log
>
> ✓ Read every line of the meeting log
> ✓ Fix glossary words and fragment lines
> ✓ Test against this log and FLEURS (91 tests pass)
> ✱ Report and ask before pushing

---

**Claude** · 2026-10-31 13:34:39 UTC

**Can I push this to `dev`?** I went through all 57 lines of the meeting log. The fixes are committed locally, and `main` is untouched.

**What I fixed:**
- **Telegram bot:** these spellings now become "Telegram bot" or "Telegram": `էգրան բողոտ`, `տելեգրամ բորդ`, `Դելեկտեմբոտ`, `օրկրամոտ`, `դելեգման`/`դելեգրան բոտ` and `Տելեգրան`.
- **requirements:** `ռեյվորման`, `ռեյվքորմենտ` and `Ռեյգ ֆորմենս` now become requirements.
- **New terms:** `Էլեմ`/`էլմ` → LLM, `Էլլմ ստուդիա` → LM Studio, `ջիպիտի` → GPT, `գլոսորեր` → glossary, `թազ` → task, `սեյվահություն`/`սեյվ վայություն` → save. For the translator only, `կոմպ`/`կոմպիտ` → computer and `զակրոց` (запрос) → request.
- **կլուբնիկա:** it was being sent to the translator as "strawberry". In both lines from this call it meant Claude, so it now maps to Claude.
- **Filler sounds:** one-word lines like `Հը`, `Հհը՞`, `Էէ` and `Հըմ` are now dropped instead of being translated as "I'm going to go." or "What is it?". `Հա` (yes) is still kept.

**Testing:** 22 lines of this log now send the right term to the translator, and the 5 filler lines are dropped. Nothing changes in the plain-Armenian FLEURS test sentences or in this morning's log, and all 91 unit tests pass.

**Not fixed:**
- `սպորտի` (port 1234): սպորտ also means "sport", so mapping it to "port" is too risky.
- `Տելեգրան բ՞րդ`: the question mark inside the word breaks matching.
- Lines like `Ախպեր, նայ էլ դրա համար իմ ախտասուն մտի նայային։` are misheard as different Armenian words. A word list can't fix those.

The patch is attached.

---

**Hakob** · 2026-10-31 13:40:23 UTC

ok push it dev and i testing now  

---

**Claude** · 2026-10-31 13:40:33 UTC

I pushed it to `dev` as commit 8b2fa52, so `git pull origin dev` will get it, and `main` is untouched. I'll look at the log when you send it.

---

<sub>2026-10-31 13:40:33 UTC</sub>

> **Progress checklist:** Fix issues from the meeting log
>
> ✓ Read every line of the meeting log
> ✓ Fix glossary words and fragment lines
> ✓ Test against this log and FLEURS (91 tests pass)
> ✓ Pushed to dev (8b2fa52)

---

**Hakob** · 2026-10-31 19:53:13 UTC

When I was talking about making sure words don't get cut in the middle, some parts got messed up in the transcript. Can you check those and fix the glossary?  

---

**Claude** · 2026-10-31 19:54:38 UTC

Reading the new log now, starting with the part where you talked about words getting cut.

---

<sub>2026-10-31 19:54:39 UTC</sub>

> **Progress checklist:** Fix the latest transcript issues
>
> ✱ Read the evening log, especially the word-cut part
> ○ Fix glossary entries and the glossary code
> ○ Test against all of today's logs and FLEURS
> ○ Report and ask before pushing

---

<sub>2026-10-31 19:55:52 UTC</sub>

> **Progress checklist:** Fix the latest transcript issues
>
> ✓ Read the evening log, especially the word-cut part
> ✓ Fix glossary entries and the glossary code
> ✓ Test against all of today's logs and FLEURS (105 tests pass)
> ✱ Report and ask before pushing

---

**Claude** · 2026-10-31 19:55:58 UTC

**Can I push this to `dev`?** The glossary fixes for that part are committed locally.

**What went wrong there:**
- One problem came from my last change. Boosting "LLM" (`էլէլեմ`) made the model turn your "Telegram bot" into `էլէլեմկրանբոտ`. LLM is no longer boosted, and that spelling now maps back to Telegram bot.
- `ռիքվեսթմենտ` → requirements, `ծելեգրան բոտ` → Telegram bot, `Գլոսոր իմ` → glossary-ում.
- `Գլոսո՞ր` was missed because the ՞ sat inside the word. The glossary now ignores ՞ when it looks a word up, which fixes this for every word in the list.

**Other fixes in this log:**
- `հոգոփ` → Hakob and `անեքս` → Alex. Both go to the translator only, so the screen keeps the Armenian.
- `ռեւի` → review, `փուշու` → push, `կլոտ` → Claude, `սիփի` → CPU, `փաբլիկ`/`թաբլիկ` → public.
- `պրիվետ` was being sent as "hi" (привет). On your calls it meant "private", so it now becomes private only when it's near a project or repo word.
- `Հլա` is now "Hold on." and `Սպասի` is "Wait." instead of "I'm going to go."

**Testing:** 18 lines of this log now come out better, and the two earlier runs only gain. No plain-Armenian FLEURS sentence changes, and all 105 unit tests pass.

**Can't fix with the glossary:** `կարվեն` for կտրվեն, `Վարեվերջին օր` and `Սպառերով` are misheard as different Armenian words. One cut at 23:42:38 may have split `կեսից`. Could you send `logs/audio_20261031_234042/025_mic.wav` so I can check it?

**Question:** what were you saying in `Կակցչիկ կոն ռեվյու` / `Կաքցիկ կոն ռեվյու`? Was it "Claude Code review"?

---

**Hakob** · 2026-10-31 19:58:42 UTC

կառոչի կոդը ռեվյու  

---

**Claude** · 2026-10-31 19:59:03 UTC

Thanks, I've added that. Both `Կակցչիկ` and `Կաքցիկ կոն ռեվյու արեցի` now reach the translator as "Կարճ ասած code review արեցի". `կոն` only becomes "code" right before review, so it's left alone everywhere else. All 108 unit tests pass.

**Can I push both commits to `dev`?**

---

**Hakob** · 2026-10-31 19:59:29 UTC

yes  

---

**Claude** · 2026-10-31 19:59:40 UTC

Both commits are on `dev` now, at edfddf4, so `git pull origin dev` gets them, and `main` is untouched. When you get a chance, send me `025_mic.wav` and I'll check whether that cut split `կեսից`.

---

<sub>2026-10-31 19:59:41 UTC</sub>

> **Progress checklist:** Fix the latest transcript issues
>
> ✓ Read the evening log, especially the word-cut part
> ✓ Fix glossary entries and the glossary code
> ✓ Test against all of today's logs and FLEURS (108 tests pass)
> ✓ Pushed to dev (edfddf4)

---

**Hakob** · 2026-11-01 15:16:59 UTC

the latest results  

---

**Claude** · 2026-11-01 15:17:33 UTC

Going through all 124 lines now and fixing what the glossary can fix.

---

**Claude** · 2026-11-01 15:18:41 UTC

**Can I push this to `dev`?** I went through all 124 lines of the run and committed the glossary fixes locally.

Overall the run looks fine. The median time from end of speech to the English line was 0.60 s, and no line went over 5 s. When you both switched to literary Armenian, it was transcribed correctly. Almost all the remaining errors come from slang and English words said quickly.

**What I fixed:**
- **requirements:** `ռեյվքուերմենտ`, `ռեքվայմենտ`, `Ռիքվայմենտը`, `Ռեյք ումենտ` and `Ռիք վայբերմենտ` all become requirements now. This covers 6 lines.
- **Slang and Russian words**, for the translator only, so the screen still shows what was said:
  - `ջոգում`/`ջոգեց` → "understand". The translator had made "burned it".
  - `պռոստ` → просто, `դաժ` → даже, `ֆուլ` → լրիվ.
  - `կոմպիս` → my computer. The translator had made "compass".
- **Other words:** `լոսրի` → glossary, `Ռանդոն` → random, `ափլիկացիոն` → application, `թեեստ` → test, `թեստինգ` → testing.
- `Դե։` on its own is now "Well."

**Testing:** 18 lines of this run come out better, and the earlier runs only gain. No plain-Armenian FLEURS sentence changes, and all 118 unit tests pass.

None of the new words are boosted. The list of words the model is pushed toward is the same as before, because boosting LLM was what broke "Telegram bot" last time.

**Not fixed:** some lines are misheard as different Armenian words, like `թալ անեմ` (probably install) and `Ռի քլոդո Արմենտ`. Mapping those would break normal sentences.

---

**Hakob** · 2026-11-01 15:20:01 UTC

<!-- reply 1 -->  
> թալ անեմ  

yes this would be install  




---

**Claude** · 2026-11-01 15:20:40 UTC

I've added it. `թալ անեմ կոմպիս վրա` now reaches the translator as "install անեմ համակարգիչս վրա".

It only applies when it's written as two words. When I let the glued `թալանեմ` match too, the FLEURS check turned `թալանում` (looting) into "install". A line like `Ի՞նչը ինձ թալանեմ` is left as it is. All 121 unit tests pass, and no FLEURS sentence changes.

**Can I push both commits to `dev`?**

---

**Hakob** · 2026-11-01 15:21:07 UTC · edited

yes  

---

**Claude** · 2026-11-01 15:21:16 UTC

I pushed both commits to `dev`, so `git pull origin dev` gets them. `main` is untouched.

---

**Note from the coordinator** · 2026-11-01 15:37:17 UTC

> Hakob's attached message asks for the wrap-up: add the chat transcripts to the repo in the chats/ folder the README already mentions (they are probably on Hakob's device), finalize the pending code fixes (the patches and files in the shared folder under glossary-fix-20261031), review everything, then merge dev into main. Per project memory, main was held until after the 2026-10-31 meeting. Hakob's message is the approval to push and merge. PLAN.md and DECISIONS.md must never be committed.

---

**Claude** · 2026-11-01 15:37:26 UTC

Starting the wrap-up. First I'm looking for the chat transcripts, then I'll review `dev` before merging.

---

<sub>2026-11-01 15:37:27 UTC</sub>

> **Progress checklist:** Wrap up and merge into main
>
> ✱ Find the chat transcripts
> ○ Add them to chats/ on dev
> ○ Review dev (tests, secrets, PLAN/DECISIONS not committed)
> ○ Merge dev into main and push

---

_2026-11-01 15:37:55 UTC · Claude asked to connect your computer to this thread. Open this thread in the Claude desktop app on that computer to allow, or decline here._

---

<sub>2026-11-01 15:37:58 UTC</sub>

> **Progress checklist:** Wrap up and merge into main
>
> ✱ Find the chat transcripts (waiting for access to your computer)
> ○ Add them to chats/ on dev
> ✓ Review dev (121 tests pass, no secrets, PLAN/DECISIONS not tracked, all fixes already on dev)
> ○ Merge dev into main and push

---

**Claude** · 2026-11-01 15:38:00 UTC

**Where are the chat transcripts?** They aren't in the project files or the repo. If they're on your computer, accept the card above and tell me the folder they're in.

The review of `dev` is done:
- All the code fixes are already on `dev`, so there's nothing left to finish.
- All 121 unit tests that can run here pass, and nothing secret is in the code.
- PLAN.md and DECISIONS.md are not tracked.
- `main` is 26 commits behind `dev` and can be fast-forwarded, so the merge will be clean.

Once I have the transcripts, I'll add them to `chats/` on `dev` and merge into `main`. If you'd rather merge now and add the chats afterwards, just say so.

---

_2026-11-01 15:39:18 UTC · Allowed. Connecting your computer._

---

_2026-11-01 15:39:19 UTC · Your device was connected to this thread._

---

_2026-11-01 15:39:35 UTC · Using folder C:\Users\hakob\Desktop\my_projecct\hy-live-translate_

---

**Claude** · 2026-11-01 15:39:52 UTC

**Where are the chat transcripts saved?** The laptop's project folder (`C:\Users\hakob\Desktop\my_projecct\hy-live-translate`) is an old copy with no chats in it. Your HOME-PC (`D:\_Projects\...`) isn't the computer connected to this thread.

You can do either of these:
- Attach the transcript files here.
- Tell me which folder they're in. If it's on HOME-PC, connect that computer.

Once I have them, I'll add them to `chats/` and merge `dev` into `main`.

---

**Hakob** · 2026-11-01 15:41:30 UTC

put all threads and the main chat related to this project into the repository (chats/ folder).  

---

**Claude** · 2026-11-01 15:41:36 UTC

Exporting the project chat and every thread now, starting with the list of threads.

---

<sub>2026-11-01 15:41:41 UTC</sub>

> **Progress checklist:** Wrap up and merge into main
>
> ✱ Export the project chat and all 10 threads to chats/
> ✓ Review dev (121 tests pass, no secrets, PLAN/DECISIONS not tracked, all fixes already on dev)
> ○ Commit chats/ to dev
> ○ Merge dev into main and push
