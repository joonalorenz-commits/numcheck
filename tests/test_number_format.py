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


def test_table_continued_on_next_page_keeps_its_header():
    # Page 1: a one-arm table (N = 30), then a four-column table whose rows go on to page 2.
    # Page 2 starts with those rows and then has a new header for another part of the table.
    page1 = ("Tabelle 1 Risankizumab N = 30 Randomisiert, n (%) 30 (100,0) Studienabbruch, n (%) 3 (10,0) "
             "Lost to follow up 1 (3,3) Einwilligung zurückgezogen 1 (3,3) Studie abgeschlossen, n (%) 27 (90,0) "
             "Tabelle 2 Risankizumab Ustekinumab Risankizumab Ustekinumab N = 304 N = 100 N = 294 N = 99 "
             "Alter, n (%) 86 (28,3) 34 (34,0) 105 (35,7) 30 (30,3)")
    page2 = ("Ethnie, n (%) weiß 200 (65,8) 74 (74,0) 255 (86,7) 91 (91,9) "
             "Teilanwendungsgebiet B N = 100 N = 34 N = 90 N = 36 "
             "Geschlecht, n (%) weiblich 28 (28,0) 9 (26,5) 32 (35,6) 11 (30,6)")
    flagged = [f for f in check_pages({1: page1, 2: page2}) if f.flagged]
    assert flagged == []
