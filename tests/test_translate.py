import pytest
import torch

from translate import Translator, max_new_tokens

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def test_max_new_tokens_grows_with_input():
    assert max_new_tokens(1) == 18
    assert max_new_tokens(40) == 96


@pytest.fixture(scope="module")
def mt():
    return Translator(DEVICE)


@pytest.mark.slow
def test_known_sentence_translates_to_english(mt):
    out = mt.translate("Երևանը Հայաստանի մայրաքաղաքն է։")
    assert "Yerevan" in out.text_en
    assert "capital" in out.text_en.lower()
    assert out.tokens_in > 2 and out.tokens_out > 2
    assert not out.capped


@pytest.mark.slow
def test_empty_input_gives_empty_output(mt):
    out = mt.translate("   ")
    assert (out.text_en, out.tokens_in, out.tokens_out, out.capped) == ("", 0, 0, False)
