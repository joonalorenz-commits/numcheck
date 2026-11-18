from numcheck import sources

SRC = [
    ("Abstract", "During follow-up, 12/137 (8.8%) patients died, but none of the deaths was device-related."),
    ("3. Results", "Mean age was 54 years. During follow-up, 11 of 137 (8.8%) patients died. Two had a stroke."),
]


def test_same_sentence_found_and_source_contradiction_shown():
    m = sources.compare("During follow-up, 11 of 137 (8.8%) patients died", SRC)
    assert m.verdict == "same" and m.source_section == "3. Results"
    assert any(o["section"] == "Abstract" and o["missing_in_sentence"] == ["11"] for o in m.other_sentences)
    assert any(f["check"] == "fraction" and f["verdict"] == "inconsistent" for f in m.source_flags)


def test_differing_number_is_listed():
    m = sources.compare("In total 14 of 137 (8.8%) patients died", SRC[1:])
    assert m.verdict == "differs" and m.missing_in_source == ["14"]


def test_unrelated_statement_is_not_found():
    assert sources.compare("3 of 20 (15%) had bleeding", SRC).verdict == "not_found"


def test_statements_need_count_and_percentage():
    page = "The device is safe. In 46 patients (71.0%) satisfaction was high. Mean 3.2 mm."
    assert sources.statements(page) == ["In 46 patients (71.0%) satisfaction was high."]


def test_html_sections():
    html = "<html><h2>Abstract</h2><p>11 of 137 (8.8%) died.</p><h2>Results</h2><table><tr><td>Deaths</td><td>11 (8.0)</td></tr></table></html>"
    secs = dict(sources.sections_from_html(html))
    assert "11 of 137 (8.8%) died." in secs["Abstract"] and "11 (8.0)" in secs["Results"]
