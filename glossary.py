"""English jargon inside Armenian speech: put the English word back before translation.

The Armenian ASR model only writes Armenian script, so an English word said inside an Armenian sentence
comes out spelled phonetically ("commit" -> "քոմիթ"). glossary.tsv lists, per English term, the Armenian
spellings the model produces for it. Those words are replaced by the English term in the Armenian line,
which NLLB then carries into the English line. Armenian endings stay attached with a hyphen, the way they
are written in text: "ռիմոթին" -> "remote-ին".

glossary.tsv format, one term per line (# starts a comment):
    commit<TAB>քոմիթ, կոմիթ
Spellings are matched case-insensitively against whole words; a spelling followed by one of SUFFIXES
also matches. Edit the file to add your own terms; it is read once at startup.
"""

import re
from pathlib import Path

GLOSSARY_FILE = Path(__file__).parent / "glossary.tsv"

# Common Armenian case/number/article endings, longest first so "ները" wins over "ը".
SUFFIXES = sorted(["ը", "ն", "ի", "ին", "ից", "ով", "ում", "եր", "երը", "երի", "երով", "ները", "ներ", "ներին",
                   "ներից", "ներով", "ներում", "ս", "դ", "ա", "ել", "ենք", "եցի", "եց", "ես", "եմ"],
                  key=len, reverse=True)
WORD = re.compile(r"[Ա-ևﬓ-ﬗ]+")  # a run of Armenian letters


def load(path=GLOSSARY_FILE):
    """{armenian spelling (lowercase): english term}. Duplicate spellings are an error, never a silent pick."""
    table = {}
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if "\t" not in line:
            raise ValueError(f"{path}:{n}: expected 'english<TAB>spelling, spelling', got {line!r}")
        english, spellings = line.split("\t", 1)
        for s in (s.strip().lower() for s in spellings.split(",")):
            if not s:
                continue
            if not WORD.fullmatch(s):
                raise ValueError(f"{path}:{n}: spelling {s!r} is not one Armenian word")
            if s in table and table[s] != english.strip():
                raise ValueError(f"{path}:{n}: {s!r} is listed for both {table[s]!r} and {english.strip()!r}")
            table[s] = english.strip()
    return table


class Glossary:
    def __init__(self, table):
        self.table = table

    @classmethod
    def from_file(cls, path=GLOSSARY_FILE):
        return cls(load(path))

    def _replace_word(self, m):
        word = m.group(0)
        low = word.lower()
        if low in self.table:
            return self.table[low]
        for suffix in SUFFIXES:
            if low.endswith(suffix) and low[:-len(suffix)] in self.table:
                return f"{self.table[low[:-len(suffix)]]}-{word[-len(suffix):]}"
        return word

    def apply(self, text_hy):
        """Armenian text with listed jargon spellings replaced by the English term."""
        return WORD.sub(self._replace_word, text_hy)
