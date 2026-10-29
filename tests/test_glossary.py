import pytest

from glossary import GLOSSARY_FILE, Glossary, attach, load


@pytest.fixture
def g(tmp_path):
    p = tmp_path / "g.tsv"
    p.write_text("# comment\ncommit\tքոմիթ, կոմիթ\npush\tփուշ\t# also thorn\nremote\tռիմոթ\nstash\tսթեշ\n"
                 "ընդհանրապես\tվաբշե\nմեքենա\tմաշին, մաշինա\nհաջող\tպակա\n", encoding="utf-8")
    return Glossary.from_file(p)


def test_hakob_examples(g):
    assert (g.apply("Կոդը գրել, վերջացրել եմ, արդեն քոմիթ ու փուշ եմ արել ռիմոթ։").shown
            == "Կոդը գրել, վերջացրել եմ, արդեն commit ու push եմ արել remote։")
    assert (g.apply("Փոփոխություններդ դեռ մի կոմիթ արա, ուղղակի սթեշ արա, հետո կնայենք։").for_mt
            == "Փոփոխություններդ դեռ մի commit արա, ուղղակի stash արա, հետո կնայենք։")


def test_english_ending_kept_with_hyphen(g):
    assert g.apply("ռիմոթին ուղարկիր").shown == "remote-ին ուղարկիր"
    assert g.apply("քոմիթները նայիր").shown == "commit-ները նայիր"


def test_russian_word_shown_as_spoken_but_translated_from_armenian(g):
    f = g.apply("Վաբշե մաշինով եկա։")
    assert f.shown == "Վաբշե մաշինով եկա։"
    assert f.for_mt == "Ընդհանրապես մեքենայով եկա։"


def test_armenian_endings_reattached():
    assert attach("մեքենա", "ը") == "մեքենան"
    assert attach("մեքենա", "ով") == "մեքենայով"
    assert attach("մեքենա", "յի") == "մեքենայի"
    assert attach("տոմս", "ը") == "տոմսը"
    assert attach("commit", "ը") == "commit-ը"


def test_case_insensitive_and_whole_words_only(g):
    assert g.apply("Քոմիթ արա").shown == "commit արա"
    assert g.apply("անքոմիթ").shown == "անքոմիթ"  # spelling inside a longer word is not touched
    assert g.apply("փուշը").shown == "push-ը"


def test_common_word_ending_like_a_loan_is_left_alone(g):
    assert g.apply("պակաս ժամանակ").for_mt == "պակաս ժամանակ"  # պակա + possessive -ս is not matched


def test_text_without_loans_unchanged(g):
    text = "Երևանը Հայաստանի մայրաքաղաքն է։"
    f = g.apply(text)
    assert f.shown == text and f.for_mt == text


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
    table = load(GLOSSARY_FILE)
    assert table["քոմիթ"].target == "commit" and table["վաբշե"].target == "ընդհանրապես"
    assert table["փուլ"].conditional and table["փուշ"].conditional


@pytest.mark.parametrize("spoken, shown", [
    ("Իսկ որ մտար գիթ, փուլ արա։", "Իսկ որ մտար git, pull արա։"),  # git nearby
    ("Փուլ արա, հետո փուշ արա։", "pull արա, հետո push արա։"),  # bare word + արա
    ("Քոմիթ ու փուշ եմ արել ռիմոթ։", "commit ու push եմ արել remote։"),  # commit/remote nearby
    ("Մեյն բրենչից փուլ արեցի։", "main branch-ից pull արեցի։"),
    ("Առաջին փուլը արդեն ավարտեցինք։", "Առաջին փուլը արդեն ավարտեցինք։"),  # stage
    ("Երկրորդ փուլ, երրորդ փուլ։", "Երկրորդ փուլ, երրորդ փուլ։"),  # stage next to stage
    ("Այդ փուլը արեցինք։", "Այդ փուլը արեցինք։"),  # "we did that stage": `then` needs the bare word
    ("Ձեռքս փուշ մտավ։", "Ձեռքս փուշ մտավ։"),  # thorn
    ("Ձեռքս փուշ մտավ, բայց քոմիթից հետո փուշ արեցի։", "Ձեռքս փուշ մտավ, բայց commit-ից հետո push արեցի։"),  # comma ends context
])
def test_ambiguous_words_follow_context(spoken, shown):
    g = Glossary.from_file()
    assert g.apply(spoken).shown == shown


def test_bad_context_rule_fails_loudly(tmp_path):
    p = tmp_path / "g.tsv"
    p.write_text("pull\tփուլ\tclose=գիթ\n", encoding="utf-8")
    with pytest.raises(ValueError, match="context must look like"):
        load(p)
