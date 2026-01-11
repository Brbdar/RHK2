import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import re

from rhk_base import load_rulebook, load_textdb_blocks, DEFAULT_RULEBOOK_PATH
from rhk_case import build_case, build_render_ctx
from rhk_reports import build_doctor_report_template, build_doctor_report, random_example
from rhk_base import render_block


def _norm(s: str) -> str:
    s = (s or "")
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def test_examples_render_selected_and_auto_modules_into_reports():
    rules = load_rulebook(DEFAULT_RULEBOOK_PATH)
    blocks = load_textdb_blocks()

    scenarios = ["no_ph", "pah_pre", "cteph", "ild_ph", "hfpef_ipcph", "cpcph", "shunt_asd"]

    for scen in scenarios:
        ui = random_example(scenario=scen, seed=42)
        case = build_case(dict(ui), rules)

        doc_templ = build_doctor_report_template(case, blocks)
        doc_full = build_doctor_report(case, blocks)

        # No unresolved placeholders should remain in final reports
        assert re.search(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}", doc_templ) is None
        assert re.search(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}", doc_full) is None

        # Ensure selected and auto modules are actually rendered (not just stored)
        mods = []
        try:
            mods += list(case.get("ui", {}).get("modules") or [])
        except Exception:
            pass
        try:
            mods += list((case.get("decision") or {}).get("modules") or [])
        except Exception:
            pass
        # Dedup, keep order
        seen = set()
        mods = [m for m in mods if isinstance(m, str) and (m not in seen and not seen.add(m))]

        for mid in mods:
            b = blocks.get(mid)
            if not b:
                continue
            ctx = build_render_ctx(case)
            rendered = _norm(render_block(b, ctx))
            # If a block is empty by design, ignore
            if len(rendered) < 10:
                continue
            # Robust presence check: at least a few content words from the rendered block must appear in report.
            words = [w for w in re.findall(r"[A-Za-zÄÖÜäöüß]{5,}", rendered)][:12]
            hit = 0
            hay = _norm(doc_full) + " " + _norm(doc_templ)
            for w in set(words):
                if w in hay:
                    hit += 1
            assert hit >= 2, f"Module {mid} scheint nicht in den Bericht eingeflossen zu sein."