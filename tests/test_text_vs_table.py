"""Text against table."""

import numcheck
from numcheck import document, text_vs_table as tvt

TABLE = """Table 2 Outcomes
Outcome Lateral group (n=1073) Supine group (n=1070)
Incidence of hypoxaemia 58 (5.4) 161 (15.0)
Airway rescue:
Yes 68 (6.3) 148 (13.8)
Severe hypoxaemia 8 (0.7) 51 (4.8)
"""


def _tvt(pages):
    return tvt.check(document.prepare(pages))


def _flagged(findings):
    return [b for b in findings if b.verdict != "consistent"]


def test_same_statement_in_text_and_table():
    text = "Hypoxaemia occurred in 58 (5.4%) patients in the lateral group and 161 (15.0%) in the supine group."
    findings = _tvt({1: text, 2: TABLE})
    assert [b.verdict for b in findings] == ["consistent", "consistent"]


def test_different_count_in_text_for_quoted_row():
    text = "Hypoxaemia occurred in 58 (5.4%) patients in the lateral group and 165 (15.0%) in the supine group."
    flagged = _flagged(_tvt({1: text, 2: TABLE}))
    assert len(flagged) == 1
    assert flagged[0].printed == "165 (15.0%)" and flagged[0].computed == "161 (15.0)"
    assert "Incidence of hypoxaemia" in flagged[0].note


def test_row_label_in_clause_is_enough():
    text = "Severe hypoxaemia was observed in 9 patients (0.7%) with lateral positioning overall in this trial."
    flagged = _flagged(_tvt({1: text, 2: TABLE}))
    assert len(flagged) == 1 and flagged[0].computed == "8 (0.7)"


def test_words_of_previous_statement_do_not_count():
    # "at birth" belongs to 115, not to 71
    table = "Wasting n (%)\nBirth 45 (12.5) 70 (19.3)\nTwelve months 71 (12.5) 30 (8.0)\n"
    text = "Wasting declined from 115 of 597 (19.3%) at birth to 71 of 570 (12.5%) at 12 months in the cohort overall."
    assert not _flagged(_tvt({1: text, 2: table}))


def test_total_over_groups_is_no_contradiction():
    table = "Drug Urban Rural\nBupropion 10 746 (7.6) 7457 (7.7)\n"
    text = "Pharmacotherapy was common in this population, mainly bupropion (18 203 patients [7.6%]) and others."
    assert not _flagged(_tvt({1: text, 2: table}))


def test_list_over_rows_finds_percentage_of_wrong_row():
    table = ("Race Group A (n = 138) Group B (n = 137) Total (N = 275)\n"
               "Hispanic 23 (16.7) 17 (12.4) 40 (14.5)\n"
               "Non-Hispanic Black 49 (35.5) 60 (43.8) 109 (39.6)\n"
               "Non-Hispanic White 44 (31.9) 45 (32.8) 89 (32.4)\n")
    text = ("Among the participants enrolled in this trial, 40 (14.5%) were Hispanic, 109 (32.4%) were non-Hispanic Black, "
            "89 (32.4%) were non-Hispanic White.")
    flagged = _flagged(_tvt({1: text, 2: table}))
    assert len(flagged) == 1
    assert flagged[0].computed == "109 (39.6)" and "Non-Hispanic White" in flagged[0].note


def test_running_text_is_no_table_row():
    text = ("At 6 months, 35 of 85 physicians (41.2%) in the intervention arm had burnout compared with "
            "46 of 91 (50.5%) in the control arm.")
    assert tvt._table_rows(1, text) == []


def test_missing_count_is_not_read_as_count():
    text = "Abstinence was 25 of 166 participants [15.1%] vs of 166 participants [8.4%] in the complete-case analysis."
    table = "Outcome A B\nContinuous abstinence 25 (15.1) 14 (8.4)\n"
    assert not _flagged(_tvt({1: text, 2: table}))


def test_text_vs_table_is_part_of_check():
    text = "Hypoxaemia occurred in 58 (5.4%) patients in the lateral group and 165 (15.0%) in the supine group."
    findings = numcheck.check({1: text, 2: TABLE})
    flagged = [b for b in findings if b.check == "text_vs_table" and b.verdict == "inconsistent"]
    assert len(flagged) == 1
    # the position points to the statement in the prepared text, like the other checks
    assert document.normalize(text)[flagged[0].start:flagged[0].end].startswith("165")


HEADER = """Table 3 Outcomes
Outcome Total (n=2143) Lateral group (n=1073) Supine group (n=1070)
Incidence of hypoxaemia 219 (10.2) 58 (5.4) 161 (15.0)
Airway rescue 216 (10.1) 68 (6.3) 148 (13.8)
"""


def test_column_names_from_header():
    rows = tvt._table_rows(2, HEADER)
    assert rows[0].header[1:] == ("Lateral group", "Supine group") and rows[0].header[0].endswith("Total")
    assert tvt._column(rows[0], " in the supine group") == 2


def test_column_from_group_name_finds_wrong_percentage():
    # count right, percentage wrong: the neighbour gives the row, "supine" the column
    text = "Airway rescue was needed in 68 (6.3%) patients in the lateral group vs 148 (12.8%) in the supine group."
    flagged = _flagged(_tvt({1: text, 2: HEADER}))
    assert len(flagged) == 1 and flagged[0].computed == "148 (13.8)"


def test_list_is_no_comparison():
    assert tvt._comparison(" in the lateral group vs ")
    assert tvt._comparison(" in the lateral group and ")
    assert not tvt._comparison(" were alive and retained in care, ")
    assert not tvt._comparison(" in ITT; ")


def test_copied_percentage_without_denominator():
    # PSMAfore CSR p. 166: the percentage of the second statement also appears with the first
    table = "Deaths Crossover (N=134)\nAll deaths 59 (44.0) 3 (2.2)\nStudy indication 51 (38.1) 2 (1.5)\n"
    text = ("Among the 134 participants who crossed over to receive treatment, 59 deaths (38.1%) were reported, "
            "of which 51 deaths (38.1%) were due to study indication.")
    flagged = _flagged(_tvt({1: text, 2: table}))
    assert len(flagged) == 1 and flagged[0].printed == "59 (38.1%)"


N_PERCENT = """Table 10: 2 Disposition of patients - ES
Placebo
N %
Nera 9 mg bid
N %
Nera 18 mg bid
N %
Adverse event
43 10.9
49 12.5 59 15.1 151 12.8
Death 24 6.1 25 6.4 15 3.8 64 5.4
Lost to follow-up 1 0.3 0 0 1 0.3 2 0.2
"""


def test_table_with_separate_percent_column():
    rows = tvt._table_rows(2, N_PERCENT)
    death = [r for r in rows if r.label == "Death"][0]
    assert death.cells == [(24, "6.1"), (25, "6.4"), (15, "3.8"), (64, "5.4")]
    # rows without label (set apart in the PDF) count too
    assert any(r.cells[:2] == [(49, "12.5"), (59, "15.1")] for r in rows)


def test_broken_sentence_and_three_group_comparison():
    # the sentence breaks in the PDF; each pair alone is in several rows, together only in one
    table = N_PERCENT + "Other reason 24 6.1 26 6.4 30 7.7 80 6.8\nDiarrhoea 25 6.4 15 3.8 10 2.6 50 4.3\n"
    text = ("Up to DBL1, death was reported in 24 patients (6.1%) in the placebo group, 25 patients (6.4%) in the\n"
            "9 mg bid nerandomilast group, and 16 patients (3.8%) in the 18 mg bid nerandomilast group.")
    flagged = _flagged(_tvt({1: text, 2: table}))
    assert len(flagged) == 1 and flagged[0].printed == "16 (3.8%)" and flagged[0].computed == "15 (3.8)"


def test_percentage_with_reference_in_bracket():
    m = tvt._STATEMENT.search("962 patients (81.7% of the treated patients) completed planned treatment")
    assert m and m.group(1) == "962" and m.group(3) == "81.7"


def test_grade_in_label_must_match():
    table = "Shift Dato-DXd ICC\nGrade 1 4 (1.3) 9 (4.1)\nGrade 3 18 (8.0) 2 (0.9)\n"
    text = ("In the safety analysis set, shifts to Grade 3 were observed for 3 (1.3%) participants on Dato-DXd "
            "during treatment overall.")
    assert not _flagged(_tvt({1: text, 2: table}))


def test_percentage_copied_from_neighbouring_cell():
    # VESALIUS-CV CSR p. 126: 1139 (31.4%) in the text, table 1139 (32.3) and 1100 (31.4)
    table = "Sex n (%)\nMale 1139 (32.3) 1100 (31.4) 755 (29.1) 754 (28.8)\n"
    text = ("Analysis of treatment-emergent adverse events by sex: AEs were reported in 1100 male participants (31.4%) "
            "receiving evolocumab and 1139 male participants (31.4%) receiving placebo.")
    flagged = _flagged(_tvt({1: text, 2: table}))
    assert len(flagged) == 1 and flagged[0].computed == "1139 (32.3)" and "belongs to 1100 in this row" in flagged[0].note


def test_small_other_count_with_same_percent_is_other_population():
    table = "AE Crossover\nBack pain 4 (1.1) 3 (0.8)\n"
    text = "The frequently reported AEs by preferred term were anaemia and back pain (6 participants (1.1%) for each term)."
    assert not _flagged(_tvt({1: text, 2: table}))
