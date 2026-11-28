from numcheck import check as check_pages
from numcheck.number_format import english, is_german, to_english


def test_german_page_is_recognised():
    t = "EV + P 26/135 (19,3%) RC + PLND 57/125 (44,2%) 13 (19,4) 28 (42,4)"
    assert is_german(t)


def test_english_page_is_left_alone():
    t = "Of 1,234 patients, 37 (36.3%) and 20 (12.5%) had events (95% CI 0.29, 0.80); n=1,203 (4.1%)"
    assert not is_german(t)
    assert english(t) == t


def test_conversion_keeps_length_and_positions():
    t = "57/125 (44,2%) HR = 0, 694 [0,484; 0,995], p = 0,0470. Insgesamt 1.234 Patienten am 17.07.2026"
    out = to_english(t)
    assert len(out) == len(t)
    assert "57/125 (44.2%)" in out
    assert "0.694  [0.484, 0.995]" in out
    assert "p = 0.0470." in out
    assert "1,234 Patienten" in out
    assert "17.07.2026" in out


def test_german_fraction_is_checked():
    page = "Tabelle 4-42 EV + P 26/135 (19,3%) RC + PLND 57/125 (44,2%) und 6/167 (4,1 %) sowie 1/159 (0,6 %)"
    flagged = [f for f in check_pages({1: page}) if f.flagged]
    printed = sorted(f.printed for f in flagged)
    assert printed == ["4.1", "44.2"]


def test_german_von_is_a_fraction():
    page = "Ein Ereignis trat bei 12 von 40 Patienten (35,0 %) auf, bei 3 von 40 (7,5 %) und 5 von 50 (10,0 %)."
    flagged = [f for f in check_pages({1: page}) if f.flagged]
    assert [f.printed for f in flagged] == ["35.0"]


def test_grade_before_bracket_is_not_a_count():
    page = ("Unerwünschte Ereignisse nach Schweregrad (CTCAE Grad ≥ 3 (8,0 %) bzw. Grad 3 (8,0 %)) "
            "bei Patienten mit HCV-Genotyp 1 (64,2 %) und 20 (40,0 %) und 10 (20,0 %).")
    flagged = [f for f in check_pages({1: page}) if f.flagged]
    assert flagged == []


def test_von_count_is_not_a_statement_of_its_own():
    page = ("Diarrhoe trat bei 26 von 38 (68,4 %) Behandelten auf. Mehr als die Hälfte (6 von 11 [54,5 %]) "
            "und 27 von 42 (64,3 %) sowie 15 von 42 [35,7 %].")
    flagged = [f for f in check_pages({1: page}) if f.flagged]
    assert flagged == []
