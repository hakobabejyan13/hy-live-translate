"""Very short ASR lines: drop the fragments, translate the common one-word replies without NLLB.

On a Meet call the VAD sometimes closes on half a word ("Հ։", "Հովհ.") just above the vad.SHORT_S limit, and NLLB
makes a whole sentence out of it ("John: I know."). Common one-word replies ("Այո։", "Լա՞վ։") come out wrong too
("Yes, you did.", "Is that right?"), because NLLB has no context. So, before translation:
  fragment  a single word of one letter, or a single word ending in "." (the model writes "։" at the end of a
            sentence and "." only after a cut-off word) -> not printed, logged with an empty translation.
  filler    a single "hm" / "uh" sound ("Հը՞", "Հհը՞", "Էէ") -> dropped like a fragment; NLLB made them
            "I'm going to go." and "What is it?" (2026-10-31)
  reply     a single word listed in REPLIES -> its English is used as is; a question mark (՞ or ?) is kept.
Anything else goes to NLLB as usual.
"""

import re

WORD = re.compile(r"[\u0531-\u0587\uFB13-\uFB17A-Za-z]+")  # also takes ՞ (U+055E) inside a word: Լա՞վ
QUESTION = "\u055e"
MARKS = "\u055b\u055c\u055e"  # ՛ (stress) ՜ (exclamation) ՞ (question), written inside the word: Լա՛վ, Լա՞վ

REPLIES = {
    "այո": "Yes", "հա": "Yeah", "ահա": "Yeah", "ոչ": "No", "չէ": "No", "չե": "No",
    "լավ": "Okay", "լավը": "Okay", "okay": "Okay", "ok": "Okay",
    "ապրես": "Thanks", "մերսի": "Thanks", "շնորհակալություն": "Thank you", "բարև": "Hi", "բարեւ": "Hi",
    "հաջող": "Bye", "բայ": "Bye", "բայբայ": "Bye", "բապայ": "Bye", "իհարկե": "Of course", "ճիշտ": "Right", "ճիշտա": "Right",
    "դե": "Well", "հլա": "Hold on", "հլը": "Hold on", "սպասի": "Wait", "սպասիր": "Wait",  # NLLB: "I'm going to go.", "I'm going to wait."
}
# Hesitation sounds: only the letters հ ը մ է, up to 4 of them (հը, հհը, հըմ, էէ, ըըը...), plus a few others.
# Not ե: "եմ" is "I am". Not հա / ահա: those are "yes" (REPLIES).
FILLER = re.compile(r"[\u0570\u0568\u0574\u0567]{1,4}")  # հ ը մ է
FILLERS = {"ըհը", "ահ", "օհ", "էհ", "ըհ"}
FRAGMENT, REPLY, SENTENCE = "fragment", "reply", "sentence"


def classify(text_hy):
    """(kind, English for a reply or ""). text_hy is the glossary-fixed Armenian line (okay may be in Latin)."""
    words = WORD.findall(text_hy)
    if len(words) != 1:
        return (FRAGMENT, "") if not words else (SENTENCE, "")
    word = words[0]
    key = word.translate({ord(m): None for m in MARKS}).lower()
    if len(key) == 1 or text_hy.rstrip().endswith(".") or FILLER.fullmatch(key) or key in FILLERS:
        return FRAGMENT, ""
    if key in REPLIES:
        question = QUESTION in word or "?" in text_hy
        return REPLY, REPLIES[key] + ("?" if question else ".")
    return SENTENCE, ""
