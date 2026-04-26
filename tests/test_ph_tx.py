import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rhk_ph_tx import (
    PH_DRUG_CHOICES,
    PH_DRUG_TO_CLASS_TAGS,
    PH_TX_STATUS_CHOICES,
    PH_TX_TABLE_HEADERS,
    derive_rulebook_class_lists_from_episodes,
    episodes_to_ph_tx_table_rows,
    episodes_to_ph_tx_text,
    format_ph_tx_episode_line,
    legacy_lists_to_episodes,
    parse_ph_tx_table_rows,
)

# ---------------------------------------------------------------------------
# Constants sanity
# ---------------------------------------------------------------------------

def test_drug_choices_not_empty():
    assert len(PH_DRUG_CHOICES) > 5


def test_status_choices_not_empty():
    assert len(PH_TX_STATUS_CHOICES) > 0
    assert "aktuell" in PH_TX_STATUS_CHOICES
    assert "abgesetzt" in PH_TX_STATUS_CHOICES


def test_table_headers_count():
    assert len(PH_TX_TABLE_HEADERS) == 6


# ---------------------------------------------------------------------------
# parse_ph_tx_table_rows – list input
# ---------------------------------------------------------------------------

def test_parse_table_rows_list():
    rows = [
        ["Sildenafil", "aktuell", "01/2024", "", "", ""],
        ["Bosentan", "abgesetzt", "", "06/2023", "Nebenwirkung", ""],
    ]
    eps = parse_ph_tx_table_rows(rows)
    assert len(eps) == 2
    assert eps[0]["drug"] == "Sildenafil"
    assert eps[0]["status"] == "aktuell"
    assert eps[1]["drug"] == "Bosentan"
    assert eps[1]["status"] == "abgesetzt"


def test_parse_table_rows_none():
    assert parse_ph_tx_table_rows(None) == []


def test_parse_table_rows_empty_list():
    assert parse_ph_tx_table_rows([]) == []


def test_parse_table_rows_skips_empty_drug():
    rows = [["", "aktuell", "", "", "", ""]]
    assert parse_ph_tx_table_rows(rows) == []


def test_parse_table_rows_skips_empty_status():
    rows = [["Sildenafil", "", "", "", "", ""]]
    assert parse_ph_tx_table_rows(rows) == []


# ---------------------------------------------------------------------------
# parse_ph_tx_table_rows – text input (fallback editor)
# ---------------------------------------------------------------------------

def test_parse_text_tab_delimited():
    text = "Sildenafil\taktuell\t01/2024\t\t\t"
    eps = parse_ph_tx_table_rows(text)
    assert len(eps) == 1
    assert eps[0]["drug"] == "Sildenafil"


def test_parse_text_pipe_delimited():
    text = "Sildenafil | aktuell | 01/2024 | | |"
    eps = parse_ph_tx_table_rows(text)
    assert len(eps) == 1
    assert eps[0]["drug"] == "Sildenafil"


def test_parse_text_semicolon_delimited():
    text = "Sildenafil;aktuell;01/2024;;;"
    eps = parse_ph_tx_table_rows(text)
    assert len(eps) == 1


def test_parse_text_skips_comments_and_headers():
    text = "# comment\nMedikament\tStatus\tSeit\tBis\tGrund\tKommentar\nSildenafil\taktuell\t\t\t\t"
    eps = parse_ph_tx_table_rows(text)
    assert len(eps) == 1


def test_parse_text_empty():
    assert parse_ph_tx_table_rows("") == []
    assert parse_ph_tx_table_rows("   ") == []


# ---------------------------------------------------------------------------
# parse_ph_tx_table_rows – dict input
# ---------------------------------------------------------------------------

def test_parse_dict_input():
    d = {"drug": "Sildenafil", "status": "aktuell", "since": "", "until": "", "reason": "", "note": ""}
    eps = parse_ph_tx_table_rows(d)
    assert len(eps) == 1
    assert eps[0]["drug"] == "Sildenafil"


def test_parse_dict_missing_drug():
    assert parse_ph_tx_table_rows({"drug": "", "status": "aktuell"}) == []


# ---------------------------------------------------------------------------
# episodes_to_ph_tx_table_rows
# ---------------------------------------------------------------------------

def test_episodes_to_table_rows():
    eps = [
        {"drug": "Sildenafil", "status": "aktuell", "since": "01/2024", "until": "", "reason": "", "note": ""},
    ]
    rows = episodes_to_ph_tx_table_rows(eps)
    assert len(rows) == 1
    assert rows[0][0] == "Sildenafil"
    assert rows[0][1] == "aktuell"


def test_episodes_to_table_rows_skips_invalid():
    eps = [
        {"drug": "", "status": "aktuell"},
        {"drug": "X", "status": ""},
        "not_a_dict",
    ]
    assert episodes_to_ph_tx_table_rows(eps) == []


def test_episodes_to_table_rows_none():
    assert episodes_to_ph_tx_table_rows(None) == []


# ---------------------------------------------------------------------------
# episodes_to_ph_tx_text
# ---------------------------------------------------------------------------

def test_episodes_to_text_roundtrip():
    eps = [
        {"drug": "Sildenafil", "status": "aktuell", "since": "01/2024", "until": "", "reason": "", "note": ""},
        {"drug": "Bosentan", "status": "abgesetzt", "since": "", "until": "06/2023", "reason": "NW", "note": ""},
    ]
    text = episodes_to_ph_tx_text(eps)
    assert "Sildenafil" in text
    assert "Bosentan" in text
    # Parse back
    parsed = parse_ph_tx_table_rows(text)
    assert len(parsed) == 2


# ---------------------------------------------------------------------------
# Drug classification
# ---------------------------------------------------------------------------

def test_drug_classification_known_drugs():
    tags = PH_DRUG_TO_CLASS_TAGS
    assert "sildenafil" in tags
    assert "PDE-5-Hemmer" in tags["sildenafil"]
    assert "opsumit (macitentan)" in tags
    assert "Endothelin-Rezeptorantagonist (ERA)" in tags["opsumit (macitentan)"]
    assert "adempas (riociguat)" in tags
    assert "sGC-Stimulator (Riociguat)" in tags["adempas (riociguat)"]


def test_drug_classification_prostacyclin():
    tags = PH_DRUG_TO_CLASS_TAGS
    for drug in ("ventavis (iloprost)", "treprostinil", "epoprostenol"):
        assert drug in tags
        assert "Prostazyklin-Therapie / -Analogon" in tags[drug]


# ---------------------------------------------------------------------------
# derive_rulebook_class_lists_from_episodes
# ---------------------------------------------------------------------------

def test_derive_class_lists_current():
    eps = [{"drug": "Sildenafil", "status": "aktuell"}]
    result = derive_rulebook_class_lists_from_episodes(eps)
    assert "PDE-5-Hemmer" in result["ph_current_meds"]
    assert result["ph_new_meds"] == []


def test_derive_class_lists_planned():
    eps = [{"drug": "Sildenafil", "status": "geplant"}]
    result = derive_rulebook_class_lists_from_episodes(eps)
    assert "PDE-5-Hemmer" in result["ph_new_meds"]
    assert result["ph_current_meds"] == []


def test_derive_class_lists_stopped():
    eps = [{"drug": "Sildenafil", "status": "abgesetzt"}]
    result = derive_rulebook_class_lists_from_episodes(eps)
    assert "PDE-5-Hemmer" in result["ph_stopped_meds"]


def test_derive_class_lists_previous():
    eps = [{"drug": "Sildenafil", "status": "früher"}]
    result = derive_rulebook_class_lists_from_episodes(eps)
    assert "PDE-5-Hemmer" in result["ph_prev_meds"]


def test_derive_class_lists_unknown_drug():
    eps = [{"drug": "UnknownDrug123", "status": "aktuell"}]
    result = derive_rulebook_class_lists_from_episodes(eps)
    assert result["ph_current_meds"] == []


def test_derive_class_lists_empty():
    result = derive_rulebook_class_lists_from_episodes([])
    assert result["ph_current_meds"] == []
    assert result["ph_new_meds"] == []
    assert result["ph_stopped_meds"] == []
    assert result["ph_prev_meds"] == []


# ---------------------------------------------------------------------------
# legacy_lists_to_episodes
# ---------------------------------------------------------------------------

def test_legacy_lists_to_episodes():
    ui = {
        "ph_current_meds": ["Sildenafil"],
        "ph_prev_meds": ["Bosentan"],
        "ph_new_meds": ["Riociguat"],
        "ph_stopped_meds": ["Tadalafil"],
        "ph_stop_reason": "Nebenwirkung",
    }
    eps = legacy_lists_to_episodes(ui)
    drugs = [e["drug"] for e in eps]
    assert "Sildenafil" in drugs
    assert "Bosentan" in drugs
    assert "Riociguat" in drugs
    assert "Tadalafil" in drugs

    # Check statuses
    for e in eps:
        if e["drug"] == "Sildenafil":
            assert e["status"] == "aktuell"
        elif e["drug"] == "Bosentan":
            assert e["status"] == "früher"
        elif e["drug"] == "Riociguat":
            assert e["status"] == "geplant"
        elif e["drug"] == "Tadalafil":
            assert e["status"] == "abgesetzt"


def test_legacy_lists_to_episodes_empty():
    assert legacy_lists_to_episodes({}) == []


# ---------------------------------------------------------------------------
# format_ph_tx_episode_line
# ---------------------------------------------------------------------------

def test_format_episode_line_basic():
    e = {"drug": "Sildenafil", "status": "aktuell"}
    line = format_ph_tx_episode_line(e)
    assert "Sildenafil" in line
    assert "aktuell" in line


def test_format_episode_line_with_dates():
    e = {"drug": "Sildenafil", "status": "aktuell", "since": "01/2024", "until": ""}
    line = format_ph_tx_episode_line(e)
    assert "seit 01/2024" in line


def test_format_episode_line_with_range():
    e = {"drug": "Sildenafil", "status": "früher", "since": "01/2020", "until": "06/2023"}
    line = format_ph_tx_episode_line(e)
    assert "01/2020 bis 06/2023" in line


def test_format_episode_line_empty():
    assert format_ph_tx_episode_line({"drug": "", "status": ""}) == ""
    assert format_ph_tx_episode_line({}) == ""
