from src.module_a.ingest.cdci_loader import load_cdci
from src.module_a.ingest.reference_loader import load_nlem, load_jan_aushadhi


def test_nlem_combo_is_split_and_both_tokens_resolve(conn):
    load_cdci(conn)
    load_nlem(conn)
    row = conn.execute(
        "SELECT match_status FROM reference_nlem WHERE medicine = 'Amoxicillin + Clavulanic Acid'"
    ).fetchone()
    assert row is not None
    assert row["match_status"] == "EXACT", "both halves of the combo exist verbatim in CDCI and should resolve"


def test_nlem_known_gaps_are_queued_not_guessed(conn):
    load_cdci(conn)
    result = load_nlem(conn)
    # From manual inspection of the data pack: ORS, Zinc Sulphate, and
    # "Iron (Ferrous salt)" don't string-match any CDCI ingredient verbatim.
    assert result["queued"] == 3
    for name in ("ORS", "Zinc Sulphate", "Iron (Ferrous salt)"):
        row = conn.execute("SELECT match_status FROM reference_nlem WHERE medicine = ?", (name,)).fetchone()
        assert row["match_status"] == "QUEUED"


def test_jan_aushadhi_all_generics_match_cdci_vocabulary(conn):
    load_cdci(conn)
    result = load_jan_aushadhi(conn)
    assert result["rows"] == 50
    assert result["queued"] == 0
