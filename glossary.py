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
    target<TAB>spelling, spelling<TAB>optional note
Spellings are matched case-insensitively against whole words; a spelling followed by one of SUFFIXES also
matches. Edit the file to add your own words; it is read once at startup.
"""

import re
from dataclasses import dataclass
from pathlib import Path

GLOSSARY_FILE = Path(__file__).parent / "glossary.tsv"

# Common Armenian case/number/article and verb endings, longest first so "ները" wins over "ը". The possessive
# endings -ս / -դ are left out: with them պակա (пока) + ս would turn the common word պակաս ("less") into a match.
SUFFIXES = sorted({"ը", "ն", "ի", "ին", "ից", "ով", "ում", "եր", "երը", "երի", "երով", "ները", "ներ", "ներին",
                   "ներից", "ներով", "ներում", "ա", "ել", "ենք", "եցի", "եց", "ես", "եմ", "ելու",
                   "ելը", "ած", "եցին", "եցիր", "եք", "են",
                   "յի", "յին", "յից", "յով", "յում"},  # after a vowel: մաշինայի
                  key=len, reverse=True)
WORD = re.compile(r"[Ա-ևﬓ-ﬗ]+")  # a run of Armenian letters
LATIN = re.compile(r"[A-Za-z]")
VOWELS = "աեէիոօու"


@dataclass
class Fixed:
    shown: str  # Armenian line for the screen: English words in Latin, everything else as spoken
    for_mt: str  # text sent to NLLB: English words in Latin, Russian words replaced by Armenian


def load(path=GLOSSARY_FILE):
    """{armenian spelling (lowercase): target}. Duplicate spellings are an error, never a silent pick."""
    table = {}
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            raise ValueError(f"{path}:{n}: expected 'target<TAB>spelling, spelling', got {line!r}")
        target, spellings = parts[0].strip(), parts[1]
        for s in (s.strip().lower() for s in spellings.split(",")):
            if not s:
                continue
            if not WORD.fullmatch(s):
                raise ValueError(f"{path}:{n}: spelling {s!r} is not one Armenian word")
            if s in table and table[s] != target:
                raise ValueError(f"{path}:{n}: {s!r} is listed for both {table[s]!r} and {target!r}")
            table[s] = target
    return table


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


class Glossary:
    def __init__(self, table):
        self.table = table

    @classmethod
    def from_file(cls, path=GLOSSARY_FILE):
        return cls(load(path))

    def _lookup(self, word):
        """(target, matched ending) for a listed word, else None."""
        low = word.lower()
        if low in self.table:
            return self.table[low], ""
        for suffix in SUFFIXES:
            if low.endswith(suffix) and low[:-len(suffix)] in self.table:
                return self.table[low[:-len(suffix)]], word[-len(suffix):]
        return None

    def _sub(self, text, english_only):
        def replace(m):
            hit = self._lookup(m.group(0))
            if hit is None or (english_only and not LATIN.search(hit[0])):
                return m.group(0)
            target, suffix = hit
            out = attach(target, suffix) if suffix else target
            if m.group(0)[0].isupper() and not LATIN.search(target):
                out = out[0].upper() + out[1:]  # keep the capital at the start of a sentence
            return out
        return WORD.sub(replace, text)

    def apply(self, text_hy):
        return Fixed(shown=self._sub(text_hy, english_only=True), for_mt=self._sub(text_hy, english_only=False))
