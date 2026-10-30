import pytest

from short_lines import FRAGMENT, REPLY, SENTENCE, classify


@pytest.mark.parametrize("text, expected", [
    # Seen on the 2026-10-30 Meet call, where NLLB made "John: I know." and "A: I have a problem with this."
    ("Հովհ.", (FRAGMENT, "")),
    ("Հ։", (FRAGMENT, "")),
    ("", (FRAGMENT, "")),
    ("Այո։", (REPLY, "Yes.")),
    ("Լա՞վ։", (REPLY, "Okay?")),
    ("Ոչ։", (REPLY, "No.")),
    ("okay։", (REPLY, "Okay.")),
    ("Բալեքս։", (SENTENCE, "")),  # unknown single word: NLLB as usual
    ("֊ Լավ, դու ի՞նչպես ես։", (SENTENCE, "")),
])
def test_classify(text, expected):
    assert classify(text) == expected
