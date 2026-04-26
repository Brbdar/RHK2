import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import rhk_logging


class _CaptureLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def warning(self, message: str) -> None:
        self.messages.append(message)

    def error(self, message: str) -> None:
        self.messages.append(message)


def test_safe_context_redacts_paths_and_payloads():
    safe = rhk_logging._safe_context(
        {
            "file_name": "alice_case.json",
            "path": "/tmp/rhk_befunder/alice_case.json",
            "case_state": {"ui": {"patient_name": "Alice Example", "story": "Dyspnoe seit Monaten"}},
            "note": "copied from /tmp/rhk_exports/report.pdf to C:\\Users\\bt\\report.pdf",
            "module_id": "P1",
        }
    )

    assert safe["file_name"] == "<redacted:file>"
    assert safe["path"] == "<redacted:path>"
    assert safe["case_state"]["_redacted"] is True
    assert safe["note"] == "copied from <redacted:path> to <redacted:path>"
    assert safe["module_id"] == "P1"


def test_log_exception_sanitizes_payload_before_serializing(monkeypatch):
    logger = _CaptureLogger()
    monkeypatch.setattr(rhk_logging, "_get_logger", lambda: logger)

    rhk_logging.log_exception(
        "RHK_TEST",
        "Failed while reading /Users/bt/Patients/alice/report.pdf",
        ValueError("open /tmp/rhk_befunder/alice_case.json failed"),
        file_name="alice_case.json",
        path="/tmp/rhk_befunder/alice_case.json",
        case_state={"ui": {"patient_name": "Alice Example"}},
    )

    payload = json.loads(logger.messages[-1])

    assert payload["message"] == "Failed while reading <redacted:path>"
    assert payload["error"] == "open <redacted:path> failed"
    assert payload["context"]["file_name"] == "<redacted:file>"
    assert payload["context"]["path"] == "<redacted:path>"
    assert payload["context"]["case_state"]["_redacted"] is True
