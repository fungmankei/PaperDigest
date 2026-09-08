from pathlib import Path

from src.config_loader import JournalInclusion, parse_abs_level
from src.journal_registry import (
    build_registry_from_combined,
    compute_journal_weight,
    filter_journals,
    filter_elite,
    is_elite,
    load_registry,
    Journal,
)


def test_parse_abs_level():
    assert parse_abs_level("4*") == 4.5
    assert parse_abs_level("3") == 3.0
    assert parse_abs_level("n/a") is None
    assert parse_abs_level(None) is None


def test_load_sample_registry():
    sample = Path(__file__).resolve().parent.parent / "data" / "journals.sample.csv"
    journals = load_registry(sample)
    assert len(journals) >= 20
    jm = next(j for j in journals if j.journal_name == "Journal of Marketing")
    assert jm.ft50 and jm.utd24
    assert "0022-2429" in jm.issn
    assert jm.abs_numeric == 4.5


def test_filter_by_area_and_inclusion(sample_journals):
    crit = JournalInclusion(abs_min_level=3, abdc_grades=["A*", "A"],
                            sjr_quartile="Q1", include_ft50=True, include_utd24=True)
    result = filter_journals(sample_journals, ["Marketing", "Information Systems"], crit)
    names = {j.journal_name for j in result}
    assert "Journal of Marketing" in names       # matches area + high rank
    assert "MIS Quarterly" in names
    assert "Obscure Marketing Notes" not in names  # right area, fails all rank rules
    assert "Journal of Physics" not in names       # high rank, wrong area


def test_inclusion_is_union(sample_journals):
    # Only FT50 rule enabled -> only FT50 journals qualify (within area).
    crit = JournalInclusion(abs_min_level=None, abdc_grades=[], sjr_quartile=None,
                            include_ft50=True, include_utd24=False)
    result = filter_journals(sample_journals, ["Marketing", "Information Systems"], crit)
    assert {j.journal_name for j in result} == {"Journal of Marketing", "MIS Quarterly"}


def test_compute_journal_weight_blends_rank_elective_impact():
    # 4* + FT50 only, no impact: 25*(0.6*1.0 + 0.15*0.5 + 0.25*0) = 16.88
    j = Journal(journal_name="X", abs_level="4*", ft50=True)
    assert compute_journal_weight(j) == 16.88
    # Max score: 4*, FT50+UTD24, impact >= cap -> 25.0
    j_max = Journal(journal_name="Max", abs_level="4*", ft50=True, utd24=True,
                    impact_factor=20.0)
    assert compute_journal_weight(j_max) == 25.0
    # ABDC 'A' with no ABS, no lists, no impact: 25*0.6*0.85 = 12.75
    j3 = Journal(journal_name="Z", abs_level=None, abdc="A", ft50=False)
    assert compute_journal_weight(j3) == 12.75
    # SJR is ignored by the formula.
    j_sjr = Journal(journal_name="S", abs_level=None, sjr="Q1")
    assert compute_journal_weight(j_sjr) == compute_journal_weight(
        Journal(journal_name="S2"))


def test_is_elite_rule():
    assert is_elite(Journal(journal_name="a", ft50=True))
    assert is_elite(Journal(journal_name="a", utd24=True))
    assert is_elite(Journal(journal_name="a", abs_level="4*"))
    assert is_elite(Journal(journal_name="a", abs_level="4"))
    assert is_elite(Journal(journal_name="a", abdc="A*"))
    # Not elite: ABS 3, ABDC A, or nothing
    assert not is_elite(Journal(journal_name="a", abs_level="3", abdc="A"))
    assert not is_elite(Journal(journal_name="a"))


def test_filter_journals_elite_only(sample_journals):
    from src.config_loader import JournalInclusion
    # sample_journals: JoM (elite, Marketing), MISQ (elite, IS),
    # Obscure (abs 1, Marketing -> not elite), Physics (abs 4, Physics -> elite but wrong area)
    result = filter_journals(sample_journals, ["Marketing", "Information Systems"],
                             JournalInclusion(), elite_only=True)
    names = {j.journal_name for j in result}
    assert names == {"Journal of Marketing", "MIS Quarterly"}
    # Physics is elite (abs 4) but excluded by area
    assert "Journal of Physics" not in names
    assert len(filter_elite(sample_journals)) == 3  # JoM, MISQ, Physics


def test_impact_factor_increases_weight():
    low = Journal(journal_name="A", abs_level="4", impact_factor=0.0)
    high = Journal(journal_name="A", abs_level="4", impact_factor=15.0)
    assert compute_journal_weight(high) > compute_journal_weight(low)


def test_build_registry_from_combined(tmp_path):
    src = tmp_path / "combined.csv"
    src.write_text(
        "Journal Title,Publisher,Field,ISSN,AJG 2021,FT50,UTD24,ABDC,SJR Quartile\n"
        "Journal of Marketing,AMA,Marketing,0022-2429,4*,Yes,Yes,A*,Q1\n"
        "Some Journal,Elsevier,Finance,1111-2222,3,No,No,B,Q2\n",
        encoding="utf-8",
    )
    out = tmp_path / "journals.csv"
    journals = build_registry_from_combined(src, out)
    assert out.exists()
    assert len(journals) == 2
    jm = journals[0]
    assert jm.journal_name == "Journal of Marketing"
    assert jm.ft50 is True and jm.utd24 is True
    # computed: 25*(0.6*1.0[4*] + 0.15*1.0[ft50+utd24] + 0.25*0[no impact]) = 18.75
    assert jm.journal_weight == 18.75
    reloaded = load_registry(out)
    assert reloaded[0].journal_name == "Journal of Marketing"
