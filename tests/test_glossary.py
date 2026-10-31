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
    with pytest.raises(ValueError, match="not Armenian words"):
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


def test_boost_phrases_skip_context_and_noboost_spellings(tmp_path):
    p = tmp_path / "g.tsv"
    p.write_text("commit\tքոմիթ\npull\tփուլ\tnear=գիթ\ncool\tքուլ\tnoboost\n", encoding="utf-8")
    g = Glossary.from_file(p)
    assert g.boost_phrases() == ["քոմիթ"]
    assert g.apply("քուլ ա").shown == "cool ա"  # noboost still replaces


def test_shipped_boost_list_has_no_ordinary_armenian_words():
    phrases = set(Glossary.from_file().boost_phrases())
    assert "քոմիթ" in phrases
    assert not phrases & {"փուլ", "փուշ", "բակ", "քոլ", "քուլ"}


@pytest.mark.parametrize("spoken, shown", [
    # Seen on the 2026-10-30 Meet call: Hakob said "review անի, pull լինենք ու push անենք".
    ("Ռիվանի եւ փուշանի մեր ռեպորտո։", "review անի եւ push անի մեր ռեպորտո։"),
    ("Գիթում փուշանենք։", "git-ում push անենք։"),
    ("Կառոչե սիեսբիների մեջ։", "Կառոչե CSV-ների մեջ։"),
    ("Տանք կլոդին։", "Տանք Claude-ին։"),
    ("Ձեռքս փուշ մտավ։", "Ձեռքս փուշ մտավ։"),  # thorn, no verb glued on
])
def test_glued_verb_and_new_spellings(spoken, shown):
    assert Glossary.from_file().apply(spoken).shown == shown


def test_split_spelling_is_joined_and_keeps_its_ending(tmp_path):
    p = tmp_path / "g.tsv"
    p.write_text("authentication\tաուտենտիֆիկացիա\nauthentication\tաուտենտի ֆիկացիա, աուտենտի ֆիկացի\tnoboost\n",
                 encoding="utf-8")
    g = Glossary.from_file(p)
    assert g.apply("Աուտենտի  ֆիկացիան չկար։").shown == "authentication-ն չկար։"
    assert g.apply("աուտենտի ֆիկացի եւ").shown == "authentication եւ"
    assert g.apply("աուտենտիֆիկացիա").shown == "authentication"
    assert g.boost_phrases() == ["աուտենտիֆիկացիա"]  # split forms are never boosted
    assert g.apply("մաուտենտի ֆիկացի").shown == "մաուտենտի ֆիկացի"  # must start a word


def test_split_spelling_of_another_word_fails_loudly(tmp_path):
    p = tmp_path / "g.tsv"
    p.write_text("commit\tքոմիթ\npush\tքո միթ\n", encoding="utf-8")
    with pytest.raises(ValueError, match="listed for another word"):
        Glossary.from_file(p)


def test_mtonly_name_keeps_armenian_on_screen(tmp_path):
    p = tmp_path / "g.tsv"
    p.write_text("Hakob\tհակոբ\tmtonly; noboost\n", encoding="utf-8")
    g = Glossary.from_file(p)
    f = g.apply("Հակոբին ասա։")
    assert f.shown == "Հակոբին ասա։" and f.for_mt == "Hakob-ին ասա։"
    assert g.boost_phrases() == []


@pytest.mark.parametrize("spoken, for_mt", [
    # Lines from the 2026-10-31 Meet call, as the ASR wrote them.
    ("Թասը պետք է սարքվի, որ ծելեգրամոգոտը լինի պլիզ միաց սայտ։",
     "task-ը պետք է սարքվի, որ Telegram bot-ը լինի please միաց site։"),
    ("Ծերամ է աուտենտի ֆիկացիա եւ տենց։", "Telegram է authentication եւ տենց։"),
    ("Բան չկար ռեքուորմենտի մեջ։", "Բան չկար requirements-ի մեջ։"),
    ("Մի հատ չոգեմ, բագ չ տերմալ ոնց կհասնեն, տերմալոգեն հիմնականում քիթհաբին։",
     "Մի հատ չոգեմ, bug չ terminal ոնց կհասնեն, տերմալոգեն հիմնականում GitHub-ին։"),
    ("Որովհետեւ էս լայվը, եթե պերմինալը նայես։", "Որովհետեւ էս live-ը, եթե terminal-ը նայես։"),
    ("Կարելի ա բրավազերի համար։", "Կարելի ա browser-ի համար։"),
    ("Կարողանք լոգալ պրոցեսին ավելի ուժեղ մոդել օգտագործենք։",
     "Կարողանք local պրոցեսին ավելի ուժեղ մոդել օգտագործենք։"),
    ("Տերմալ ջրերում լողացինք։", "Տերմալ ջրերում լողացինք։"),  # thermal waters: no tech word nearby
    ("Թասը պետք է սարքվի։", "task-ը պետք է սարքվի։"),
    ("Թաասի միտքն էր։", "task-ի միտքն էր։"),
    ("Տրանսսկիականի։", "transcription կանի։"),
])
def test_meet_call_2026_10_31(spoken, for_mt):
    assert Glossary.from_file().apply(spoken).for_mt == for_mt


@pytest.mark.parametrize("spoken, for_mt", [
    # Lines from the 2026-10-31 meeting run (latency_20261031_165728.csv), as the ASR wrote them.
    ("Հիմա պետք ա, որ էգրան բողոտ։", "Հիմա պետք ա, որ Telegram bot։"),
    ("Բելետ տելեգրամ բորդ ռեյվքորմենտը չի հասկանում։", "Բելետ Telegram bot requirements-ը չի հասկանում։"),
    ("Ռեյգ ֆորմենսը չի հասկանում։", "requirements-ը չի հասկանում։"),
    ("Դելեկտեմբոտ։", "Telegram bot։"),
    ("Էս դելեգման բոտը, որ եթե մտնի Էլեմ, կարա դառնա դելեգրան բոտ։",
     "Էս Telegram bot-ը, որ եթե մտնի LLM, կարա դառնա Telegram bot։"),
    ("Նա է, Էլլմ ստուդիա։", "Նա է, LM Studio։"),
    ("Խոսքիս Արմինեն ջիպիտի։", "Խոսքիս Արմինեն GPT։"),
    ("Գլոսորերի մեջ գրել։", "glossary-երի մեջ գրել։"),
    ("Այս թազը ավելացրեց։", "Այս task-ը ավելացրեց։"),
    ("Կլուբնիկա հետ քննարկել։", "Claude հետ քննարկել։"),
    ("Սեյվահությունը եղել ա, չէ՞։", "save-ը եղել ա, չէ՞։"),
    ("Իմ կոմպիտ աշխատում ա։", "Իմ համակարգիչդ աշխատում ա։"),
    ("Զակրոցները սրան ա գալիս։", "Հարցումները սրան ա գալիս։"),
])
def test_meeting_run_2026_10_31(spoken, for_mt):
    assert Glossary.from_file().apply(spoken).for_mt == for_mt


@pytest.mark.parametrize("spoken, for_mt", [
    # Evening run 2026-10-31 (latency_20261031_234042.csv), the part about words cut in half.
    ("Գլոսոր իմ ավելացվել էր։", "glossary-ում ավելացվել էր։"),
    ("Գլոսո՞ր։", "glossary?։"),  # ՞ inside the word no longer hides it
    ("Նոր բառեր հասկացություններ ռիքվեսթմենտը հասկացել ա, էլէլեմկրանբոտ բառերը հասկացվեն։",
     "Նոր բառեր հասկացություններ requirements-ը հասկացել ա, Telegram bot բառերը հասկացվեն։"),
    ("Խնդիրը ոչ թե ծելեգրան բոտ կամ ռիքվեսթ բառերի։", "Խնդիրը ոչ թե Telegram bot կամ request բառերի։"),
    ("Իսկ վերջի կոդը ռեւի արել ե՞ս։", "Իսկ վերջի կոդը review արել ե՞ս։"),
    ("Բարեւ հոգոփ, ոնց ես։", "Բարեւ Hakob, ոնց ես։"),
    ("Խոսքի սիփի վրա կարողանա աշխատի։", "Խոսքի CPU վրա կարողանա աշխատի։"),
    ("Վերջնական փուշու բանը վաղն եմ անելու։", "Վերջնական push բանը վաղն եմ անելու։"),
    ("Փաբլիկ տեսարք ես։", "public տեսարք ես։"),
    ("Չ մեզ չի տենց սարքել պրիվետ էինք։", "Չ մեզ չի տենց սարքել private էինք։"),
    ("Պրիվետ, ոնց ես։", "Պրիվետ, ոնց ես։"),  # no tech word nearby: left alone
])
def test_evening_run_2026_10_31(spoken, for_mt):
    assert Glossary.from_file().apply(spoken).for_mt == for_mt


def test_boost_list_leaves_out_llm():
    """Boosting էլէլեմ turned "telegram bot" into էլէլեմկրանբոտ."""
    assert not set(Glossary.from_file().boost_phrases()) & {"էլէլէմ", "էլէլեմ"}
