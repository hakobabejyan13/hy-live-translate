import pytest

from glossary import GLOSSARY_FILE, Glossary, load


@pytest.fixture
def g(tmp_path):
    p = tmp_path / "g.tsv"
    p.write_text("# comment\ncommit\tքոմիթ, կոմիթ\npush\tփուշ\nremote\tռիմոթ\nstash\tսթեշ\n", encoding="utf-8")
    return Glossary.from_file(p)


def test_hakob_examples(g):
    assert (g.apply("Կոդը գրել, վերջացրել եմ, արդեն քոմիթ ու փուշ եմ արել ռիմոթ։")
            == "Կոդը գրել, վերջացրել եմ, արդեն commit ու push եմ արել remote։")
    assert (g.apply("Փոփոխություններդ դեռ մի կոմիթ արա, ուղղակի սթեշ արա, հետո կնայենք։")
            == "Փոփոխություններդ դեռ մի commit արա, ուղղակի stash արա, հետո կնայենք։")


def test_armenian_ending_kept_with_hyphen(g):
    assert g.apply("ռիմոթին ուղարկիր") == "remote-ին ուղարկիր"
    assert g.apply("քոմիթները նայիր") == "commit-ները նայիր"


def test_case_insensitive_and_whole_words_only(g):
    assert g.apply("Քոմիթ արա") == "commit արա"
    assert g.apply("անքոմիթ") == "անքոմիթ"  # spelling inside a longer word is not touched
    assert g.apply("փուշը") == "push-ը"


def test_text_without_jargon_unchanged(g):
    text = "Երևանը Հայաստանի մայրաքաղաքն է։"
    assert g.apply(text) == text


def test_bad_lines_fail_loudly(tmp_path):
    p = tmp_path / "g.tsv"
    p.write_text("commit քոմիթ\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expected"):
        load(p)
    p.write_text("commit\tքոմիթ\npush\tքոմիթ\n", encoding="utf-8")
    with pytest.raises(ValueError, match="listed for both"):
        load(p)
    p.write_text("commit\tcommit\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not one Armenian word"):
        load(p)


def test_shipped_glossary_loads():
    assert load(GLOSSARY_FILE)["քոմիթ"] == "commit"
