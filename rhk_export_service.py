"""Export services kept separate from the Gradio UI layer."""

from __future__ import annotations

import os
import shutil
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from rhk_case import build_case
from rhk_case_service import prepare_case_runtime_input
from rhk_export_paths import make_export_path
from rhk_logging import log_exception
from rhk_reports import build_doctor_report, markdown_to_docx_file
from rhk_runtime_policy import get_export_retention_days


@dataclass
class FileExportBundle:
    file_path: str
    message: str


def _format_success_message(prefix: str, file_path: str) -> str:
    ts_human = time.strftime("%Y-%m-%d %H:%M:%S")
    fname = Path(str(file_path)).name
    exp_dir = str(Path(str(file_path)).resolve().parent)
    return f"✅ {prefix} erstellt ({ts_human}). Datei: {fname} (Export-Ordner: {exp_dir})"


def _normalize_case_filename(name: Any) -> Optional[str]:
    text = str(name or "").strip()
    if not text:
        return None
    if not text.lower().endswith(".json"):
        text = f"{text}.json"
    return text


def _ensure_case_dict(case_state: Any, *, error_message: str) -> Dict[str, Any]:
    if not isinstance(case_state, dict):
        raise ValueError(error_message)
    return dict(case_state)


def _attach_import_payloads(
    case: Dict[str, Any],
    *,
    case_filename: Any,
    docx_cur_state: Any,
    docx_prev_state: Any,
    echo_cur_state: Any,
    echo_prev_state: Any,
) -> Dict[str, Any]:
    try:
        remembered_name = _normalize_case_filename(case_filename)
        if remembered_name:
            case["case_filename"] = remembered_name
    except Exception as exc:
        log_exception("RHK_EXPORT_CASE_FILENAME", "Failed to attach case filename to export case.", exc)

    try:
        imports = case.setdefault("imports", {})
        if isinstance(docx_cur_state, dict) and docx_cur_state:
            imports["docx_current"] = docx_cur_state
        if isinstance(docx_prev_state, dict) and docx_prev_state:
            imports["docx_prev"] = docx_prev_state
        if isinstance(echo_cur_state, dict) and echo_cur_state:
            imports["echo_cur"] = echo_cur_state
        if isinstance(echo_prev_state, dict) and echo_prev_state:
            imports["echo_prev"] = echo_prev_state
    except Exception as exc:
        log_exception("RHK_EXPORT_IMPORTS_ATTACH", "Failed to attach import payloads to export case.", exc)
    return case


def build_doctor_docx_file(case_state: Any, *, blocks: Dict[str, Any]) -> str:
    case = _ensure_case_dict(case_state, error_message="Bitte zuerst den Befund erstellen, dann DOCX herunterladen.")
    markdown = str(build_doctor_report(case, blocks) or "").strip()
    out_path = make_export_path(stem="rhk_arztbericht", suffix=".docx")
    markdown_to_docx_file(markdown, out_path)
    return str(out_path)


def export_doctor_docx(case_state: Any, *, blocks: Dict[str, Any]) -> FileExportBundle:
    export_path = build_doctor_docx_file(case_state, blocks=blocks)
    return FileExportBundle(
        file_path=export_path,
        message=_format_success_message("DOCX", export_path),
    )


def save_doctor_docx_local(case_state: Any, *, blocks: Dict[str, Any], out_dir: str) -> str:
    case = _ensure_case_dict(case_state, error_message="Bitte zuerst den Befund erstellen, dann DOCX speichern.")

    resolved_out_dir = str(out_dir or "").strip()
    if not resolved_out_dir:
        resolved_out_dir = os.path.join(os.path.expanduser("~"), "Documents", "RHK_Befunde")

    os.makedirs(resolved_out_dir, exist_ok=True)
    markdown = str(build_doctor_report(case, blocks) or "").strip()
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(resolved_out_dir, f"rhk_arztbericht_{ts}.docx")
    markdown_to_docx_file(markdown, out_path)
    return out_path


def export_doctor_docx_zip(case_state: Any, *, blocks: Dict[str, Any]) -> FileExportBundle:
    docx_path = build_doctor_docx_file(case_state, blocks=blocks)
    if not docx_path or not os.path.exists(str(docx_path)):
        raise ValueError("DOCX konnte nicht erstellt werden (ZIP-Export abgebrochen).")

    zip_path = make_export_path(stem="rhk_arztbericht", suffix=".zip")
    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(str(docx_path), arcname=os.path.basename(str(docx_path)))
    return FileExportBundle(
        file_path=str(zip_path),
        message=_format_success_message("DOCX ZIP", str(zip_path)),
    )


def export_prerhk_pdf(
    *,
    flags_state: Any,
    pmods_state: Any,
    docx_cur_state: Any,
    docx_prev_state: Any,
    echo_cur_state: Any,
    echo_prev_state: Any,
    case_filename: Any,
    raw_ui: Dict[str, Any],
    rules: List[Any],
) -> FileExportBundle:
    flags = dict(flags_state or {})
    raw, _base_case = prepare_case_runtime_input(
        raw_ui=dict(raw_ui or {}),
        case_state_in=None,
        pmods_state=pmods_state,
        flags=flags,
    )

    case = dict(build_case(raw, rules))
    case = _attach_import_payloads(
        case,
        case_filename=case_filename,
        docx_cur_state=docx_cur_state,
        docx_prev_state=docx_prev_state,
        echo_cur_state=echo_cur_state,
        echo_prev_state=echo_prev_state,
    )

    from rhk_pdf_prerhk import generate_prerhk_pdf

    pdf_path_tmp = generate_prerhk_pdf(case)
    out_path = make_export_path(stem="Pre-RHK", suffix=".pdf")

    try:
        if str(Path(pdf_path_tmp).resolve()) != str(Path(out_path).resolve()):
            shutil.move(str(pdf_path_tmp), str(out_path))
    except Exception as exc:
        log_exception("RHK_EXPORT_PRERHK_MOVE", "Moving generated Pre-RHK PDF into export dir failed; serving source path.", exc)
        out_path = str(pdf_path_tmp)

    try:
        out_dir = Path(out_path).resolve().parent
        now = time.time()
        max_age = get_export_retention_days() * 24 * 3600
        for path in out_dir.glob("Pre-RHK_*.pdf"):
            try:
                if path.is_file() and (now - path.stat().st_mtime) > max_age:
                    path.unlink(missing_ok=True)
            except Exception as exc:
                log_exception("RHK_EXPORT_PRERHK_CLEAN_FILE", "Cleanup of old Pre-RHK export file failed.", exc, path=str(path))
    except Exception as exc:
        log_exception("RHK_EXPORT_PRERHK_CLEANUP", "Pre-RHK cleanup loop failed.", exc)

    return FileExportBundle(
        file_path=str(out_path),
        message=_format_success_message("Pre-RHK PDF", str(out_path)),
    )
