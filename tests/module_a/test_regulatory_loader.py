"""A.5: event-sourced regulatory data ingestion. See DESIGN.md D-009."""
import csv
import json

from src.module_a.regulatory.loader import load_regulatory_events
from src.module_a.regulatory.target_parser import parse_target_description, classify_scope


def test_loads_all_events_and_is_idempotent(conn):
    first = load_regulatory_events(conn)
    assert first["skipped"] is False
    assert first["events"] == 12

    second = load_regulatory_events(conn)
    assert second["skipped"] is True
    assert second["events"] == 12
    assert conn.execute("SELECT COUNT(*) c FROM regulatory_events").fetchone()["c"] == 12


def test_target_description_is_parsed_deterministically(conn):
    load_regulatory_events(conn)
    ev001 = conn.execute("SELECT * FROM regulatory_events WHERE event_id='EV001'").fetchone()
    assert json.loads(ev001["target_ingredients_json"]) == ["Nimesulide", "Paracetamol"]
    assert ev001["scope_note"] == "all strengths"

    ev012 = conn.execute("SELECT * FROM regulatory_events WHERE event_id='EV012'").fetchone()
    assert json.loads(ev012["target_ingredients_json"]) == ["Ibuprofen", "Paracetamol"]
    assert ev012["scope_note"] == "paediatric suspensions only"

    # PRODUCT-type targets are not decomposed into an ingredient set (see DESIGN.md D-012)
    ev010 = conn.execute("SELECT * FROM regulatory_events WHERE event_id='EV010'").fetchone()
    assert ev010["target_type"] == "PRODUCT"
    assert ev010["target_ingredients_json"] is None


def test_parse_target_description_unit():
    names, scope = parse_target_description("Nimesulide + Paracetamol (all strengths)", "FDC")
    assert names == ["Nimesulide", "Paracetamol"]
    assert scope == "all strengths"

    names, scope = parse_target_description("Ranitidine (all products)", "INGREDIENT")
    assert names == ["Ranitidine"]
    assert scope == "all products"

    names, scope = parse_target_description("Ofloxacin + Ornidazole Suspension (paediatric)", "PRODUCT")
    assert names is None
    assert scope == "paediatric"


def test_classify_scope():
    assert classify_scope(None) == "UNLIMITED"
    assert classify_scope("all strengths") == "UNLIMITED"
    assert classify_scope("All Products") == "UNLIMITED"
    assert classify_scope("paediatric suspensions only") == "SUSPENSION"
    assert classify_scope("Schedule H1 enforcement") == "UNVERIFIABLE"
    assert classify_scope("specific ratio") == "UNVERIFIABLE"


def test_different_content_is_not_treated_as_already_loaded(conn, tmp_path):
    header = ["event_id", "notification_id", "date_published", "effective_date", "action",
              "target_type", "target_description", "supersedes_event_id", "note"]

    def write(path, event_id):
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerow([event_id, "N1", "2020-01-01", "2020-01-05", "PROHIBITED", "INGREDIENT",
                        "TestDrug (all products)", "", "test"])

    v1, v2 = tmp_path / "reg_v1.csv", tmp_path / "reg_v2.csv"
    write(v1, "EVX1")
    write(v2, "EVX2")

    r1 = load_regulatory_events(conn, csv_path=v1)
    assert r1["skipped"] is False
    r2 = load_regulatory_events(conn, csv_path=v2)
    assert r2["skipped"] is False


def test_unmapped_target_ingredients_are_queued_with_provenance(conn):
    """G3 fix (DESIGN.md D-014): EV004/EV007 ("Caffeine") and EV011
    ("Codeine-based cough FDCs") never resolve to a canonical ingredient.
    Each must produce a review_queue entry with the new reason code,
    carrying the event's own provenance -- not just be silently absent from
    ingredient matching."""
    from src.module_a.ingest.cdci_loader import load_cdci
    load_cdci(conn)  # populates the canonical ingredient registry EV004/EV007/EV011 are checked against
    result = load_regulatory_events(conn)
    assert result["queued"] == 3  # EV004, EV007, EV011 -- verified against the real data pack

    queued_rows = conn.execute(
        "SELECT * FROM review_queue WHERE entity_type='regulatory_event' "
        "AND reason_code='REGULATORY_TARGET_INGREDIENT_UNMAPPED' ORDER BY id"
    ).fetchall()
    assert len(queued_rows) == 3

    candidates_by_event = {}
    for row in queued_rows:
        c = json.loads(row["candidates_json"])
        candidates_by_event[c["event_id"]] = c

    assert set(candidates_by_event) == {"EV004", "EV007", "EV011"}

    ev004 = candidates_by_event["EV004"]
    assert ev004["unmapped_ingredient_names"] == ["Caffeine"]
    assert ev004["target_description"] == "Chlorpheniramine + Phenylephrine + Caffeine + Paracetamol (specific ratio)"
    assert ev004["action"] == "PROHIBITED"
    assert ev004["effective_date"] == "2016-03-10"
    assert ev004["notification_id"] == "GSR 218(E)"
    assert ev004["load_batch_id"] is not None

    ev011 = candidates_by_event["EV011"]
    assert ev011["unmapped_ingredient_names"] == ["Codeine-based cough FDCs"]

    # every queued row must reference an actual regulatory_events row (real
    # entity_id, not a placeholder) -- provenance must be traceable, not just quoted
    for row in queued_rows:
        event = conn.execute("SELECT * FROM regulatory_events WHERE id=?", (row["entity_id"],)).fetchone()
        assert event is not None
        assert event["event_id"] == json.loads(row["candidates_json"])["event_id"]


def test_events_with_fully_mapped_targets_are_not_queued(conn):
    from src.module_a.ingest.cdci_loader import load_cdci
    load_cdci(conn)
    load_regulatory_events(conn)
    queued_event_ids = {
        json.loads(r["candidates_json"])["event_id"]
        for r in conn.execute(
            "SELECT * FROM review_queue WHERE entity_type='regulatory_event' "
            "AND reason_code='REGULATORY_TARGET_INGREDIENT_UNMAPPED'"
        ).fetchall()
    }
    # EV001/EV002/EV003 (Nimesulide+Paracetamol) and EV005/EV006 (Ranitidine)
    # all map cleanly against CDCI's ingredient vocabulary and must not be queued.
    assert queued_event_ids.isdisjoint({"EV001", "EV002", "EV003", "EV005", "EV006"})


def test_running_without_cdci_loaded_first_queues_everything(conn):
    """If the canonical ingredient registry is empty (CDCI not loaded yet),
    every FDC/INGREDIENT event's targets are -- correctly -- unmapped. This
    isn't the normal run_all.py order (CDCI loads first), but the loader
    must not crash or silently skip the check if run standalone."""
    result = load_regulatory_events(conn)
    assert result["queued"] == 11  # all 11 FDC/INGREDIENT-type events (EV010 is PRODUCT-type, has no target ingredients)


def test_reload_of_skipped_batch_reports_the_same_queued_count(conn):
    from src.module_a.ingest.cdci_loader import load_cdci
    load_cdci(conn)
    first = load_regulatory_events(conn)
    second = load_regulatory_events(conn)
    assert second["skipped"] is True
    assert second["queued"] == first["queued"] == 3
    # and it must not have queued a second, duplicate set of review items
    total_queued = conn.execute(
        "SELECT COUNT(*) c FROM review_queue WHERE entity_type='regulatory_event'"
    ).fetchone()["c"]
    assert total_queued == 3
