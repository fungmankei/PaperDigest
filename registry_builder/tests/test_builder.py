import sys
from pathlib import Path

# Make both the project root (for `src`) and its parent (for `registry_builder`)
# importable regardless of where pytest is invoked from.
ROOT = Path(__file__).resolve().parent.parent.parent
for p in (str(ROOT), str(ROOT.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

from registry_builder import build as build_mod
from registry_builder.normalize import format_issn, normalize_name, split_issns
from registry_builder.sources.abdc import parse_abdc
from registry_builder.sources.abs_ajg import parse_abs
from registry_builder.sources.seed_lists import load_seed


def test_normalize_name():
    assert normalize_name("The Review of Financial Studies") == "review of financial studies"
    assert normalize_name("Manufacturing & Service Operations Management") == \
        "manufacturing and service operations management"
    assert normalize_name("Journal of Marketing") == "journal of marketing"


def test_issn_helpers():
    assert format_issn("00221082") == "0022-1082"
    assert format_issn("0304-405X") == "0304-405X"
    assert split_issns("0022-1082, 1540-6261") == ["0022-1082", "1540-6261"]
    assert split_issns("n/a") == []


def test_seed_loads():
    seed = load_seed()
    assert len(seed) >= 50
    jm = seed[normalize_name("Journal of Marketing")]
    assert jm["ft50"] and jm["utd24"]
    assert jm["issn"] == ["0022-2429"]
    # INFORMS Journal on Computing is UTD24-only (not FT50)
    ijc = seed[normalize_name("INFORMS Journal on Computing")]
    assert ijc["utd24"] and not ijc["ft50"]


def test_parse_abdc(tmp_path):
    f = tmp_path / "abdc.csv"
    f.write_text(
        "Journal Title,ISSN,ISSN Online,2022 rating,FoR\n"
        "Journal of Marketing,0022-2429,1547-7185,A*,Marketing\n"
        "Some Ops Journal,1111-2222,,A,Operations Management\n"
        "A Weak Journal,3333-4444,,D,Management\n",
        encoding="utf-8")
    data = parse_abdc(f)
    assert normalize_name("Journal of Marketing") in data
    assert data[normalize_name("Some Ops Journal")]["abdc"] == "A"
    assert data[normalize_name("Some Ops Journal")]["field"] == "Operations Management"
    # invalid grade 'D' is dropped
    assert normalize_name("A Weak Journal") not in data


def test_parse_abs(tmp_path):
    f = tmp_path / "abs.csv"
    f.write_text(
        "Journal Title,ISSN,AJG 2021\n"
        "Journal of Marketing,0022-2429,4*\n"
        "Minor Journal,5555-6666,2\n",
        encoding="utf-8")
    data = parse_abs(f)
    assert data[normalize_name("Journal of Marketing")]["abs_level"] == "4*"


def test_build_end_to_end_offline(tmp_path, monkeypatch):
    # No network: disable ABDC download and stub OpenAlex enrichment.
    def fake_enrich(records, mailto, cache_dir, max_workers=6, ttl_hours=168):
        for rec in records.values():
            rec["impact_factor"] = 10.0
        return len(records)

    monkeypatch.setattr(build_mod, "enrich_impact_factors", fake_enrich)

    out = tmp_path / "journals.csv"
    journals = build_mod.build(out_path=out, abdc_url=None, abdc_file=None,
                               mailto="t@e.c", enrich=True)
    assert out.exists()
    assert len(journals) >= 50
    jm = next(j for j in journals if j.journal_name == "Journal of Marketing")
    assert jm.impact_factor == 10.0
    assert jm.ft50 and jm.utd24 and jm.sjr is None
    # weight: 25*(0.6*0.8[list rank] + 0.15*1.0 + 0.25*min(1,10/15)) = 25*(0.48+0.15+0.1667)
    assert jm.journal_weight > 0
    # sorted descending by weight
    weights = [j.journal_weight for j in journals]
    assert weights == sorted(weights, reverse=True)


def test_build_adds_abdc_only_journal(tmp_path, monkeypatch):
    abdc_file = tmp_path / "abdc.csv"
    abdc_file.write_text(
        "Journal Title,ISSN,2022 rating,FoR\n"
        "Brand New Ops Journal,9090-1010,A*,Operations Management\n",
        encoding="utf-8")
    monkeypatch.setattr(build_mod, "enrich_impact_factors",
                        lambda *a, **k: 0)
    out = tmp_path / "j.csv"
    journals = build_mod.build(out_path=out, abdc_url=None, abdc_file=abdc_file,
                               enrich=False)
    added = next(j for j in journals if j.journal_name == "Brand New Ops Journal")
    assert added.abdc == "A*"
    assert added.areas == ["Operations & Technology Management"]
