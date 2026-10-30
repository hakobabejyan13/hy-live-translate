"""Loanwords in Armenian speech: English jargon and Russian colloquialisms, fixed before translation.

The Armenian ASR model only writes Armenian script, so a foreign word said inside an Armenian sentence comes
out spelled by sound ("commit" -> "քոմիթ", "вообще" -> "վաբշե"). NLLB often mistranslates such spellings.
glossary.tsv lists, per word, the Armenian spellings and what to put in their place. There are two kinds:

  English target (Latin letters), e.g.  commit  <- քոմիթ
      Shown in the Armenian line and sent to NLLB as the English word. Armenian endings stay attached with
      a hyphen, the way they are written in text: "ռիմոթին" -> "remote-ին".
  Armenian target, e.g.  ընդհանրապես  <- վաբշե
      For Russian words that have a plain Armenian equivalent. The Armenian line still shows the word as
      spoken (it is what was said); only the text sent to NLLB gets the Armenian equivalent, with the
      ending re-attached ("մաշինով" -> "մեքենայով").

glossary.tsv format, one word per line (# starts a comment):
    target<TAB>spelling, spelling
    target<TAB>spelling, spelling<TAB>near=word, word; then=word, word
    target<TAB>spelling<TAB>noboost      (replace, but do not boost the spelling in the ASR)
Spellings are matched case-insensitively against whole words; a spelling followed by one of SUFFIXES also
matches. Edit the file to add your own words; it is read once at startup.

Context rules (third column) are for spellings that are also ordinary Armenian words, like փուլ ("stage", but
also "pull") or փուշ ("thorn", but also "push"). Such a word is only replaced when one of the `near` words is
within NEAR_WORDS words of it in the same clause (no comma or full stop in between) (git, branch, commit...), or when the very next word is one of the `then` words
(արա, անել, արեցի...: "փուլ արա" is "do a pull", never "do a stage"; bare word only, since "փուլը արեցինք"
is "we did the stage"). Otherwise it is left as Armenian.
Context words match a whole word or the start of one, so "գիթ" also matches "գիթում".

The ASR often glues the verb "անել" (to do) onto the loanword before it: "review անի" comes out as "ռիվանի",
"push անենք" as "փուշանենք". A spelling followed by one of VERB_ENDINGS is split back into two words
("review անի"); for a context-rule spelling the glued verb counts as the `then` word after it.
"""

import re
from dataclasses import dataclass
from pathlib import Path

GLOSSARY_FILE = Path(__file__).parent / "glossary.tsv"

# Common Armenian case/number/article and verb endings, longest first so "ները" wins over "ը". The possessive
# endings -ս / -դ are left out: with them պակա (пока) + ս would turn the common word պակաս ("less") into a match.
SUFFIXES = sorted({"ը", "ն", "ի", "ին", "ից", "ով", "ում", "եր", "երը", "երի", "երով", "ները", "ներ", "ների", "ներին",
                   "ներից", "ներով", "ներում", "ա", "ել", "ենք", "եցի", "եց", "ես", "եմ", "ելու",
                   "ելը", "ած", "եցին", "եցիր", "եք", "են",
                   "յի", "յին", "յից", "յով", "յում"},  # after a vowel: մաշինայի
                  key=len, reverse=True)
# Forms of անել ("to do") that the ASR glues onto a loanword; only the ան- forms, since արա- endings would also
# split real words (գիթ + արա = "guitar").
VERB_ENDINGS = sorted({"անի", "անենք", "անեմ", "անես", "անեք", "անեն", "անել", "անելու", "անում"},
                      key=len, reverse=True)
WORD = re.compile(r"[Ա-ևﬓ-ﬗ]+")  # a run of Armenian letters
LATIN = re.compile(r"[A-Za-z]")
TOKEN = re.compile(r"[\u0531-\u0587\uFB13-\uFB17A-Za-z]+")  # Armenian or Latin word, for context checks
NEAR_WORDS = 3
CLAUSE_END = re.compile(r"[,.;:!?\u0589\u055D\u055E\u055C]")  # also Armenian ։ ՝ ՞ ՜: context stops here
VOWELS = "աեէիոօու"


@dataclass(frozen=True)
class Entry:
    target: str
    near: tuple = ()  # replace only if one of these is within NEAR_WORDS words...
    then: tuple = ()  # ...or the next word is one of these; both empty = always replace
    boost: bool = True  # also boost this spelling in the ASR (asr.Recognizer.set_boosting)

    @property
    def conditional(self):
        return bool(self.near or self.then)


@dataclass
class Fixed:
    shown: str  # Armenian line for the screen: English words in Latin, everything else as spoken
    for_mt: str  # text sent to NLLB: English words in Latin, Russian words replaced by Armenian


def load(path=GLOSSARY_FILE):
    """{armenian spelling (lowercase): Entry}. Duplicate spellings are an error, never a silent pick."""
    table = {}
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            raise ValueError(f"{path}:{n}: expected 'target<TAB>spelling, spelling', got {line!r}")
        target, spellings = parts[0].strip(), parts[1]
        entry = Entry(target, **parse_context(parts[2] if len(parts) > 2 else "", f"{path}:{n}"))
        for s in (s.strip().lower() for s in spellings.split(",")):
            if not s:
                continue
            if not WORD.fullmatch(s):
                raise ValueError(f"{path}:{n}: spelling {s!r} is not one Armenian word")
            if s in table and table[s] != entry:
                raise ValueError(f"{path}:{n}: {s!r} is listed for both {table[s].target!r} and {target!r}")
            table[s] = entry
    return table


def parse_context(text, where):
    """'near=a, b; then=c; noboost' -> {"near": ("a", "b"), "then": ("c",), "boost": False}."""
    out = {}
    for part in filter(None, (p.strip() for p in text.split(";"))):
        if part == "noboost":
            out["boost"] = False
            continue
        key, _, words = part.partition("=")
        key = key.strip()
        if key not in ("near", "then") or not words.strip():
            raise ValueError(f"{where}: context must look like 'near=word, word; then=word; noboost', got {part!r}")
        out[key] = tuple(w.strip().lower() for w in words.split(",") if w.strip())
    return out


def attach(target, suffix):
    """Put an Armenian ending back on the replacement word."""
    if LATIN.search(target):
        return f"{target}-{suffix}"
    if target[-1] in VOWELS:
        if suffix == "ը":
            return target + "ն"  # the article is -ն after a vowel
        if suffix[0] in VOWELS and target[-1] in "աո":
            return target + "յ" + suffix  # մեքենա + ով -> մեքենայով
    return target + suffix


def _clauses(text):
    """(start, end) spans of text between punctuation; context rules only look inside one span."""
    pos = 0
    for m in CLAUSE_END.finditer(text):
        yield pos, m.start()
        pos = m.end()
    yield pos, len(text)


class Glossary:
    def __init__(self, table):
        self.table = table

    @classmethod
    def from_file(cls, path=GLOSSARY_FILE):
        return cls(load(path))

    def _lookup(self, word):
        """(Entry, matched ending, glued verb) for a listed word, else None."""
        low = word.lower()
        if low in self.table:
            return self.table[low], "", ""
        for suffix in SUFFIXES:
            if low.endswith(suffix) and low[:-len(suffix)] in self.table:
                return self.table[low[:-len(suffix)]], word[-len(suffix):], ""
        for verb in VERB_ENDINGS:
            if low.endswith(verb) and low[:-len(verb)] in self.table:
                return self.table[low[:-len(verb)]], "", word[-len(verb):]
        return None

    def boost_phrases(self):
        """Spellings to boost in the ASR. Not the context-rule ones (փուլ, փուշ...): they are ordinary Armenian
        words too, and boosting them would push the model toward them everywhere. Not entries marked noboost."""
        return sorted(s for s, e in self.table.items() if e.boost and not e.conditional)

    @staticmethod
    def _context_ok(entry, words, i, suffix, verb):
        """True if the word at index i of `words` (lowercase) has the context its entry needs."""
        if not entry.conditional or verb.lower() in entry.then:
            return True
        # `then` only for the bare word: "փուլ արա" is a pull, but "փուլը արեցինք" is "we did the stage".
        if not suffix and i + 1 < len(words) and words[i + 1] in entry.then:
            return True
        around = words[max(i - NEAR_WORDS, 0):i] + words[i + 1:i + 1 + NEAR_WORDS]
        return any(w.startswith(c) for w in around for c in entry.near)

    def _sub(self, text, english_only):
        out, pos = [], 0
        for start, end in _clauses(text):
            tokens = list(TOKEN.finditer(text, start, end))
            words = [t.group(0).lower() for t in tokens]
            for i, t in enumerate(tokens):
                word = t.group(0)
                hit = self._lookup(word) if WORD.fullmatch(word) else None
                if hit is None or (english_only and not LATIN.search(hit[0].target)):
                    continue
                entry, suffix, verb = hit
                if not self._context_ok(entry, words, i, suffix, verb):
                    continue
                new = attach(entry.target, suffix) if suffix else entry.target
                if verb:
                    new = f"{new} {verb}"
                if word[0].isupper() and not LATIN.search(entry.target):
                    new = new[0].upper() + new[1:]  # keep the capital at the start of a sentence
                out += [text[pos:t.start()], new]
                pos = t.end()
        out.append(text[pos:])
        return "".join(out)

    def apply(self, text_hy):
        return Fixed(shown=self._sub(text_hy, english_only=True), for_mt=self._sub(text_hy, english_only=False))
