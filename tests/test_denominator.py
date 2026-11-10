from numcheck import denominator, document


def _verdicts(text):
    return [(b.printed, b.verdict) for b in denominator.check(document.prepare({1: text}))]


def test_grim_with_count_impossible():
    # 52/73 = 71.2 %; no number of people gives 71.3 % with 52
    text = "With 73 patients randomized to receive the drug in this trial (mean age 59 years; 52 men [71.3%]) overall."
    assert ("71.3", "impossible") in _verdicts(text)


def test_grim_reachable_stays_silent():
    # without a denominator in the sentence only impossible values are reported
    assert _verdicts("In this trial of the new drug for adults, we saw that 52 men (71.2%) were included overall.") == []


def test_grim_large_denominators():
    # 7285 of 9 311 844 is 0.08 %; the value is reachable
    text = "The study included 9,311,844 individuals of which 7,285 (0.08%) had acute care involving hallucinogens."
    assert all(u == "consistent" for _, u in _verdicts(text))


def test_list_adds_up_to_100():
    # 264 + 160 = 424; 264/424 = 62.3 %, not 62.2 %
    text = "Among all of those who answered the survey at the clinic, 264 (62.2%) were female and 160 (37.7%) were male."
    assert ("62.2", "truncated") in _verdicts(text)     # 62.26 truncated is 62.2
    text = text.replace("62.2", "62.4")      # sum 100.1 is still within rounding
    assert ("62.4", "inconsistent") in _verdicts(text)
    text = text.replace("62.4", "62.3")
    assert all(u == "consistent" for _, u in _verdicts(text))


def test_explicit_denominator():
    # 30/102 = 29.4 %; 29.1 % is reachable with 103 (no GRIM case), but not with 102
    text = "Of the 102 participants in the trial, 30 (29.1%) had a diagnosis of RA and 33 (32.4%) had psoriatic arthritis."
    assert ("29.1", "inconsistent") in _verdicts(text)


def test_subgroup_between_denominator_and_statement():
    text = ("A total of 343 participants were screened for the trial, 240 were randomized and "
            "169 participants (70.4%) completed the trial between January and March.")
    assert ("70.4", "inconsistent") not in _verdicts(text)


def test_group_after_statement():
    text = "Of these 100 participants in the trial, 49 (98%) in the active group and 49 (98%) in the sham group finished."
    assert all(u != "inconsistent" for _, u in _verdicts(text))


def test_age_is_no_count():
    text = "Results show that about half of the respondents in the trial were between the ages of 35 and 49 (48.2%)."
    assert _verdicts(text) == []
    text = "Obesity affected 15 991 of 36 396 individuals aged 18 to 29 years (43.9%) in the large cohort overall."
    assert _verdicts(text) == []
