import numcheck


def _on_page(text):
    return numcheck.check({1: text})


def test_fraction_consistent_and_inconsistent():
    b = _on_page("in 27 of 295 patients (9.2%) and in 52 of 307 patients (17.9%)")
    assert [x.verdict for x in b if x.check == "fraction"] == ["consistent", "inconsistent"]


def test_impossible_percentage_with_602_people():
    b = _on_page("A total of 602 patients were enrolled. Notably, 82.3% of patients had it.")
    (e,) = [x for x in b if x.check == "grim_percent"]
    assert e.verdict == "truncated" and e.computed == "496/602"
    b = _on_page("A total of 602 patients were enrolled. Notably, 82.2% of patients had it.")
    assert [x.verdict for x in b if x.check == "grim_percent"] == ["consistent"]


def test_p_value_is_really_the_chi_square_statistic():
    text = ("Indomethacin (N=295) Placebo (N = 307). Bleeding occurred in 11 patients (1.8%): "
            "4 in the indomethacin group and 7 in the placebo group (P = 0.72).")
    (v,) = [x for x in _on_page(text) if x.check == "two_group_test"]
    assert v.verdict == "inconsistent" and "0.716" in v.note


def test_fisher_p_value_matches():
    (v,) = [x for x in _on_page("27 of 295 (9.2%) versus 52 of 307 (16.9%) (P = 0.005).") if x.check == "two_group_test"]
    assert v.verdict == "consistent" and "Fisher" in v.note


def test_table_row_against_header():
    b = _on_page("Drug (N=295) Placebo (N=307) Ampullectomy — no. (%) 9 (3.1) 9 (2.9) Stent — no. (%) 246 (83.4) 250 (82.0)")
    assert [x.verdict for x in b if x.check == "table_cell"] == ["consistent", "consistent", "consistent", "other_denominator"]


def test_t_statistic():
    b = _on_page("difference t(30) = 2.04, P = 0.05 and t(30) = 2.04, P = 0.01")
    assert [x.verdict for x in b if x.check == "test_statistic"] == ["consistent", "inconsistent"]


def test_table_cell_reachable_with_no_denominator():
    b = _on_page("Drug (N=295) Placebo (N=307) Stent — no. (%) 246 (38.4) 250 (81.4)")
    assert [x.verdict for x in b if x.check == "table_cell"] == ["impossible", "consistent"]


def test_percentage_of_a_group_is_no_finding():
    text = "Drug (N=84) Placebo (N=86). A total of 254 subjects were randomized. 75.6% of subjects receiving placebo."
    assert [x.verdict for x in _on_page(text) if x.check == "grim_percent"] == ["consistent"]


def test_mean_and_sd_are_no_percent_cells():
    b = _on_page("Drug (N = 222) Placebo (N = 221) Age (years) Mean (StD) 54 (13.9) 54 (13.0)")
    assert [x for x in b if x.check == "table_cell"] == []


def test_header_with_thousands_separator():
    b = _on_page("Drug (N=1,030) Placebo (N=1,011) n (%) 990 (96.1) 907 (89.7)")
    assert [x.verdict for x in b if x.check == "table_cell"] == ["consistent", "consistent"]


def test_number_from_cited_study_is_skipped():
    text = "A total of 106 patients were randomized. No AEs were reported in 73.3% of patients (Zhao, 2023)."
    assert [x for x in _on_page(text) if x.check == "grim_percent"] == []


def test_row_with_more_columns_than_header_is_not_matched():
    b = _on_page("A (N=222) B (N=221) Rash 1 ( 0.5%) 0 1 ( 0.2%) 2 ( 0.9%)")
    assert [x for x in b if x.check == "table_cell"] == []


def test_n_below_lloq_is_no_percent_row():
    b = _on_page("A N = 319 B N = 318 Geometric CV (%) NC NC Day 1 n (n < LLOQ) 289 (5) 287 (3)")
    assert [x for x in b if x.check == "table_cell"] == []


def test_statistic_within_rounding_range():
    b = _on_page("at T3 (χ2(1) = 0.399, p = 0.527)")
    assert [x.verdict for x in b if x.check == "test_statistic"] == ["consistent"]


def test_thousands_separator_and_glued_numbers():
    b = _on_page("A total of 12,483/21733 (57.4%) had events. Placebo: 8043.4 ± 10.496/202 (47.5%)")
    assert [(x.printed, x.verdict) for x in b if x.check == "fraction"] == [("57.4", "consistent")]


def test_p_value_before_the_pairs_does_not_belong():
    b = _on_page("Statins (P < .001) and β-blockers (11 of 47 [23.4%] vs 3 of 42 [7.1%]; P = .12).")
    assert [x.printed for x in b if x.check == "two_group_test"] == ["P = .12"]


def test_decimal_means_and_thousands_are_no_counts():
    b = _on_page("Group (n = 176) Control (n = 170) No. (%) Baseline 15.58 (3.50) 16.14 (3.07) "
                    "White, n (%) 28,050 (97.0%) 421 (96.6%)")
    assert [x for x in b if x.check == "table_cell"] == []


def test_unit_in_row_is_no_percent_row():
    b = _on_page("A (n = 95) B (n = 95) Gender, female (n (%)) 30 (32) 38 (40) Age (years) 72 (6) 74 (5)")
    assert [x.printed for x in b if x.check == "table_cell"] == ["32", "40"]


def test_adjusted_p_value_is_other_test():
    text = "16 of 21 (76.2%) vs 3 of 12 (25.0%) (adjusted RR 1.42, 95% CI 0.84-2.41; P = .19)."
    assert [x.verdict for x in _on_page(text) if x.check == "two_group_test"] == ["other_test"]


def _interval(text):
    return [(x.verdict, x.computed) for x in _on_page(text) if x.check == "ci_p"]


def test_interval_consistent():
    assert _interval("hazard ratio 0.75 (95% CI, 0.65-0.86; P < .001)")[0][0] == "consistent"


def test_estimate_outside_interval():
    assert _interval("HR 0.95 (95% CI 0.65 to 0.86), P = 0.01")[0][0] == "impossible"


def test_interval_and_significance_contradict():
    assert _interval("odds ratio 1.40 (95% CI, 1.10-1.78; P = .21)")[0][0] == "inconsistent"


def test_p_value_far_from_approximation_is_unclear():
    assert _interval("risk ratio 0.80 (95% CI, 0.70-0.91; P = .04)")[0][0] == "unclear"


def test_difference_with_negative_limits():
    assert _interval("mean difference −2.1 (95% CI, −3.0 to −1.2; P < .001)")[0][0] == "consistent"


def test_other_level_is_not_checked():
    assert _interval("HR 0.80 (97.5% CI, 0.64-1.00; P = .03)") == []


def test_relative_risk_is_a_ratio():
    assert _interval("relative risk, 0.18 [95% CI, 0.07-0.50]; P < .001")[0][0] == "consistent"


def test_csr_notation():
    assert _interval("Hazard ratio (95% CI) 0.599 (0.488, 0.736), p-value <0.0001")[0][0] == "consistent"


def test_more_csr_notations():
    assert _interval("The difference (95% CI, p-value) in FVC [mL] at Week 52 was 44.9 (6.4, 83.3, p = 0.0222)")[0][0] == "consistent"
    assert _interval("Hazard ratio (95% CI)a - 0.75 (0.65, 0.86) Nominal p-valueb - < 0.001*")[0][0] == "consistent"


def test_minus_with_space():
    assert _interval("the difference was - 0.74 (-1.64, 0.16), nominal p-value 0.1132")[0][0] == "consistent"


def test_the_word_or_is_no_odds_ratio():
    assert _interval("a reduction of 8.5 or more points (−12.8 to −3.9; P < .001)") == []


def test_adjusted_hazard_ratio():
    assert _interval("cases (AHR, 0.56 [95% CI, 0.30-0.89]; P = .002) and")[0][0] == "unclear"


def test_categories_exceed_n():
    text = ("Drug (N=945) Placebo (N=943) 1 Day n (%) 8 ( 0.8) 6 ( 0.6) 2 Days n (%) 1 ( 0.1) 0 "
            "3 Days n (%) 2 ( 0.2) 3 ( 0.3) 4 Days n (%) 4 ( 0.4) 5 ( 0.5) 5 Days n (%) 928 (98.3) 929 (98.4) "
            ">5 Days n (%) 1 ( 0.1) 1 ( 0.1) Total number of tablets")
    b = [x for x in _on_page(text) if x.check == "category_sum"]
    assert [(x.printed, x.computed) for x in b] == [("N = 943", "944")]


def test_complete_split_is_consistent():
    text = "A (N=86) B (N=84) Male, n (%) 33 (38.4) 34 (40.5) Female, n (%) 53 (61.6) 50 (59.5)"
    assert [x for x in _on_page(text) if x.check == "category_sum"] == []


def test_sub_rows_do_not_belong_to_split():
    text = ("A (N=945) B (N=943) Ongoing 347 (36.7) 338 (35.8) Completed 557 (58.9) 567 (60.1) "
            "Discontinued 41 ( 4.3) 38 ( 4.0) Reason Adverse event 0 1 ( 0.1) Death 0 2 ( 0.2)")
    assert [x for x in _on_page(text) if x.check == "category_sum"] == []


def test_block_with_exact_sum_is_preferred():
    text = ("All (N = 1810) A (n = 1296) B (n = 514) First device, No. (%) DL 1430 (79.0) 1070 (82.6) 360 (70.0) "
            "VL 315 (17.4) 179 (13.8) 136 (26.5) VLh 48 (2.7) 34 (2.6) 14 (2.7) Other 16 (0.9) 12 (0.9) 4 (0.8) "
            "None 1 (0.1) 1 (0.1) 0 Aux device, No. (%) Stylet 990 (54.7) 792 (61.1) 198 (38.5) "
            "Bougie 574 (31.7) 319 (24.6) 255 (49.6) Other 3 (0.2) 2 (0.2) 1 (0.2) None 241 (13.3) 182 (14.0) 59 (11.5) "
            "Unknown 2 (0.1) 1 (0.1) 1 (0.2) Cormack")
    assert [x for x in _on_page(text) if x.check == "category_sum"] == []


def _of_check(text, art):
    return [(x.printed, x.verdict) for x in _on_page(text) if x.check == art]


def test_partition_without_header_finds_wrong_percentage():
    # Female/Male add up to 100 % per column, so N = 19 + 84 = 103 and 50 + 149 = 199
    text = "Sex Female 19 (18.4) 50 (25.1) Male 84 (81.6) 149 (74.9)"
    assert _of_check(text, "column_partition") == []
    assert ("25.3", "inconsistent") in _of_check(text.replace("25.1", "25.3").replace("74.9", "74.7"), "column_partition")


def test_partition_forced_to_100():
    # 1/3 = 33.3 %; correctly rounded 33.3 + 33.3 + 33.3 = 99.9, printed forced to 100
    text = "Grade A 1 (33.4) 10 (50.0) B 1 (33.3) 5 (25.0) C 1 (33.3) 5 (25.0)"
    assert _of_check(text, "column_partition") == [("33.4", "forced_to_100")]


def test_partition_ignores_cells_with_denominator_and_thousands():
    assert _of_check("Aspirin 256/262 (97.7%) 269 (97.1%) Clopidogrel 6/262 (2.3%) 8 (2.9%)", "column_partition") == []
    assert _of_check("No 58 000 (39.1) 22 002 (38.5) Yes 90 436 (60.9) 35 198 (61.5)", "column_partition") == []


def test_row_total_column():
    kopf = "Hypnosis (n = 126) Sham (n = 124) Total (N = 250) "
    rows = "Asian 5 (4.0) 2 (1.6) 7 (2.8) Black 20 (15.9) 22 (17.7) 42 (16.8) White 90 (71.4) 88 (71.0) 178 (71.2) "
    assert _of_check(kopf + rows + "Other 11 (8.7) 12 (9.7) 23 (9.2)", "row_total") == []
    assert _of_check(kopf + rows + "Other 11 (8.7) 12 (9.7) 24 (9.6)", "row_total") == [("24", "inconsistent")]
