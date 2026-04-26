import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_import_service import import_current_docx, import_previous_docx


def test_import_current_docx_tracks_provenance(monkeypatch):
    payload = {
        "patient": {"age_years": 42, "sex": "weiblich", "exam_date": "05.03.2026"},
        "canonical": {"rest": {"mpap": 35}},
        "timeseries": {},
        "phases": {},
        "quality": {"status": "green", "reasons": []},
    }
    monkeypatch.setattr("rhk_import_service.parse_maclab_docx", lambda _file_path: dict(payload))

    bundle = import_current_docx(
        "/tmp/current.docx",
        ui_dict={"age": None, "sex": "keine Angabe", "rhk_date": ""},
        prev_payload=None,
        prev_docx_payload=None,
        wipe_defaults={"age": None, "sex": "keine Angabe", "rhk_date": ""},
    )

    assert bundle.ui_dict["age"] == 42
    assert bundle.ui_dict["sex"] == "weiblich"
    assert bundle.ui_dict["rhk_date"] == "05.03.2026"
    applied_keys = set(bundle.payload["_ui_applied_keys_current"])
    assert {"age", "rhk_date", "sex"} <= applied_keys
    assert bundle.payload["_ui_applied_values_current"]["age"] == 42


def test_import_previous_docx_backfills_missing_current_demographics(monkeypatch):
    payload = {
        "patient": {"age_years": 51, "sex": "männlich", "height_cm": 180},
        "canonical": {"rest": {"mpap": 41}},
        "timeseries": {
            "bloodgas": [{"site": "ART", "time": "08:00", "hb_g_dl": 13.6}],
        },
        "phases": {},
        "quality": {"status": "green", "reasons": []},
    }
    monkeypatch.setattr("rhk_import_service.parse_maclab_docx", lambda _file_path: dict(payload))

    bundle = import_previous_docx(
        "/tmp/previous.docx",
        ui_dict={"age": None, "sex": "", "height_cm": None, "hb_g_dl": None},
        prev_payload=None,
        current_docx_payload=None,
        wipe_defaults={"prev_mpap": None},
    )

    assert bundle.ui_dict["prev_mpap"] == 41
    assert bundle.ui_dict["age"] == 51
    assert bundle.ui_dict["sex"] == "männlich"
    assert bundle.ui_dict["height_cm"] == 180
    assert bundle.ui_dict["hb_g_dl"] == 13.6
    assert "prev_mpap" in set(bundle.payload["_ui_applied_keys_prev"])
