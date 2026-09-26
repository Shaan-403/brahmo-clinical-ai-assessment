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
