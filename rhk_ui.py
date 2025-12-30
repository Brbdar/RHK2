#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RHK Befundassistent – Gradio UI (split from rhk_app_web_master.py).

Enthält:
- Desktop-Only Overlay + Head/CSS/JS Assets
- build_demo() (Gradio Blocks + Callbacks)

Hinweis: Inhalt ist weitgehend 1:1 aus der Master-Datei extrahiert.
"""

from __future__ import annotations

from rhk_base import *  # noqa: F401,F403

from rhk_case import build_case, build_dashboard_html  # noqa: F401
from rhk_reports import (
    build_doctor_report,
    build_patient_report,
    build_internal_report,
    random_example,
    export_json,
    load_case_json,
)  # noqa: F401

# =============================================================================
# Gradio UI
# =============================================================================

# --- Client/UI behaviour ------------------------------------------------------
# Desktop-only enforcement:
# - The app is designed for wide screens. On small screens we display an overlay and block interaction.
# - Override for testing with: RHK_DESKTOP_ONLY=0
DESKTOP_ONLY: bool = os.environ.get("RHK_DESKTOP_ONLY", "1").strip().lower() not in ("0", "false", "no", "off")
DESKTOP_MIN_WIDTH_PX: int = int(os.environ.get("RHK_DESKTOP_MIN_WIDTH", "1100"))
DESKTOP_VIEWPORT_WIDTH_PX: int = int(os.environ.get("RHK_DESKTOP_VIEWPORT_WIDTH", "1200"))

# Inject a desktop-like viewport on mobile browsers (desktop browsers usually ignore this tag).
HEAD_HTML = f'<meta name="viewport" content="width={DESKTOP_VIEWPORT_WIDTH_PX}, initial-scale=1">'

CSS = ("""
/* ------------------------------------------------------------------

/* Neutralize "Befund erstellen/aktualisieren" buttons (avoid persistent blue look) */
#btn_generate_top button, #btn_generate_bottom button {
  background: #ffffff !important;
  color: #0f172a !important;
  border: 1px solid rgba(148, 163, 184, 0.9) !important;
  box-shadow: none !important;
}
#btn_generate_top button:hover, #btn_generate_bottom button:hover {
  filter: brightness(0.98);
}
   Light Theme – enforced (incl. system/browser dark-mode)
   ------------------------------------------------------------------ */
:root, .dark {
  color-scheme: light !important;
  --card-bg: rgba(255,255,255,0.96);
  --border: rgba(0,0,0,0.08);

  /* Gradio CSS vars (override dark defaults) */
  --body-background-fill: #f6f7fb !important;
  --background-fill-primary: #ffffff !important;
  --background-fill-secondary: #f6f7fb !important;
  --block-background-fill: rgba(255,255,255,0.96) !important;
  --block-border-color: rgba(0,0,0,0.08) !important;
  --input-background-fill: #ffffff !important;
  --input-border-color: rgba(0,0,0,0.18) !important;
  --body-text-color: #111111 !important;
  --input-text-color: #111111 !important;
}

html, body { color-scheme: light !important; background: #f6f7fb !important; }

.gradio-container { max-width: 1700px !important; min-width: %dpx !important; margin: 0 auto !important; padding-left: 8px; padding-right: 8px; }

/* Prevent any dark mode artefacts */
.dark, .dark * { color-scheme: light !important; }
.dark body, .dark .gradio-container { background: #f6f7fb !important; }
.dark .card, .dark .gr-box, .dark .panel { background: var(--card-bg) !important; color: #111 !important; }
.dark .prose, .dark .markdown, .dark .wrap { color: #111 !important; }

/* Force light input fields (some browsers/components keep dark backgrounds) */
.gradio-container input:not([type="checkbox"]):not([type="radio"]),
.gradio-container textarea,
.gradio-container select {
  background: #ffffff !important;
  color: #111111 !important;
}

/* Make checkbox/radio state clearly visible */
.gradio-container input[type="checkbox"],
.gradio-container input[type="radio"]{
  accent-color: #2563eb !important;
}

.gradio-container input::placeholder,
.gradio-container textarea::placeholder {
  color: rgba(0,0,0,0.45) !important;
}

/* Hide theme toggle (we enforce light) */
button[aria-label*="dark"],
button[aria-label*="Dark"],
button[title*="dark"],
button[title*="Dark"] {
  display: none !important;
}
/* Tabs: immer sichtbar (wrap statt overflow) */
[role="tablist"]{
  flex-wrap: wrap !important;
  overflow: visible !important;
  white-space: normal !important;
  gap: 4px 6px !important;
}
/* volle Tab-Titel (kein Ellipsis) */
[role="tablist"] > button{
  flex: 0 0 auto !important;
  max-width: none !important;
  width: auto !important;
  overflow: visible !important;
  text-overflow: clip !important;
  white-space: nowrap !important;
  margin: 2px 4px !important;
  padding: 6px 10px !important;
  font-size: 13px !important;
}
/* Gradio "More/..." Overflow-Button in Tab-Leisten ausblenden (wir wrappen stattdessen) */
.gradio-container .tabs button[aria-label="More"],
.gradio-container .tabs button[title="More"],
.gradio-container .tabs button[aria-label="Mehr"],
.gradio-container .tabs button[title="Mehr"],
.gradio-container .tabs .tab-nav__more,
.gradio-container .tabs .tab-nav__button--more,
.gradio-container .tabs .tab-nav__button-more{
  display: none !important;
}


/* Tabs: robust gegen Gradio 6.x Overflow-Button (… / three-dots) */
#rhk_input_tabs [role="tablist"] button:not([role="tab"]),
#rhk_output_tabs [role="tablist"] button:not([role="tab"]){
  display: none !important;
}
#rhk_input_tabs [role="tab"], #rhk_output_tabs [role="tab"]{
  white-space: normal !important;
  text-overflow: clip !important;
  overflow: visible !important;
  max-width: none !important;
}
/* P-Module: 2 Spalten + niemals "More/..." (Gradio baut je nach Version Overflow-Controls) */
#pmods_choice_lvl1 .wrap,
#pmods_choice_lvl2 .wrap,
#pmods_choice_lvl3 .wrap{
  display: grid !important;
  grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
  gap: 6px 16px !important;
  max-height: none !important;
  overflow: visible !important;
}
#pmods_choice_lvl1 label,
#pmods_choice_lvl2 label,
#pmods_choice_lvl3 label{
  white-space: normal !important;
}

/* Disabled P-Module cards (hellgrau) */
.pmod-disabled-grid{
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 16px;
  margin-top: 8px;
}
.pmod-card{
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 10px 12px;
}
.pmod-card.disabled{
  background: #f2f2f2;
  color: #555;
  border-color: #ddd;
}
.pmod-title{
  font-weight: 650;
  margin-bottom: 4px;
}
.pmod-reason{
  font-size: 12px;
  line-height: 1.25;
  opacity: 0.95;
}

.card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 14px 16px;
  box-shadow: 0 2px 14px rgba(0,0,0,0.04);
}
.card-title { font-size: 16px; font-weight: 700; margin-bottom: 6px; }
.row { display:flex; gap:16px; flex-wrap: wrap; margin: 6px 0; }
.badges { display:flex; gap:8px; flex-wrap:wrap; margin: 10px 0 0; }
.badge { padding: 5px 10px; border-radius: 999px; font-size: 12px; border: 1px solid var(--border); background: rgba(0,0,0,0.03); }
.badge-blue { background: rgba(59,130,246,0.12); border-color: rgba(59,130,246,0.25); }
.badge-purple { background: rgba(168,85,247,0.12); border-color: rgba(168,85,247,0.25); }
.badge-orange { background: rgba(249,115,22,0.12); border-color: rgba(249,115,22,0.25); }
.badge-teal { background: rgba(20,184,166,0.12); border-color: rgba(20,184,166,0.25); }
.badge-red { background: rgba(239,68,68,0.12); border-color: rgba(239,68,68,0.25); }
.muted { color: rgba(0,0,0,0.55); }
.small { font-size: 12px; color: rgba(0,0,0,0.55); }
.subhead { font-size: 13px; color: rgba(0,0,0,0.65); margin-top: -6px; }
.whatsnew{ margin-top: 6px; font-size: 13px; color: rgba(0,0,0,0.65); }


/* Desktop-only overlay */
#rhk_desktop_only_overlay{
  position: fixed;
  inset: 0;
  z-index: 999999;
  background: rgba(255,255,255,0.97);
  backdrop-filter: blur(3px);
  display:flex;
  align-items:center;
  justify-content:center;
  padding: 24px;
}
#rhk_desktop_only_overlay .rhk-desktop-only-box{
  max-width: 760px;
  border: 1px solid rgba(0,0,0,0.12);
  border-radius: 14px;
  padding: 18px 18px;
  background: rgba(255,255,255,0.98);
  box-shadow: 0 12px 40px rgba(0,0,0,0.14);
}
#rhk_desktop_only_overlay h2{
  margin: 0 0 10px 0;
  font-size: 18px;
}
#rhk_desktop_only_overlay p{
  margin: 8px 0;
  line-height: 1.35;
}

/* v25.0: robust tab/option overflow handling (Gradio versions differ) */
.gradio-container .tab-nav,
.gradio-container .tabs > .tab-nav,
.gradio-container .tab-nav > div {
  flex-wrap: wrap !important;
  overflow-x: visible !important;
  overflow-y: visible !important;
}
.gradio-container button[aria-label="More"],
.gradio-container button[title="More"],
.gradio-container button[aria-label="Mehr"],
.gradio-container button[title="Mehr"],
.gradio-container .tab-nav__more,
.gradio-container .tab-nav__overflow,
.gradio-container .tab-nav__overflow-menu,
.gradio-container .tab-nav__overflowButton {
  display: none !important;
}

/* ------------------------------------------------------------------
   RHK Glass Topbar (sticky)
   ------------------------------------------------------------------ */
#rhk_topbar{
  position: sticky;
  top: 8px;
  z-index: 10000;
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 16px;
}
#rhk_topbar .rhk-topbar{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:12px;
  padding:10px 14px;
  margin:6px 0 12px;
  background: rgba(255,255,255,0.75);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255,255,255,0.5);
  border-radius: 14px;
  box-shadow: 0 4px 6px -1px rgba(0,0,0,0.02),
              0 10px 28px rgba(0,0,0,0.06);
}
#rhk_topbar .rhk-topbar__left{
  display:flex;
  align-items:center;
  gap:12px;
  min-width:0;
}
#rhk_topbar .rhk-logo{
  width:42px;
  height:42px;
  border-radius:12px;
  flex-shrink:0;
  display:flex;
  align-items:center;
  justify-content:center;
  background: linear-gradient(135deg, #eff6ff, #f3e8ff);
  border: 1px solid rgba(255,255,255,0.6);
  color:#4f46e5;
}
#rhk_topbar .rhk-titlewrap{
  display:flex;
  flex-direction:column;
  justify-content:center;
  min-width:0;
}
#rhk_topbar .rhk-title{
  font-size:15px;
  font-weight:800;
  line-height:1.1;
  letter-spacing:-0.3px;
  color:#111;
}
#rhk_topbar .rhk-subtitle{
  font-size:13px;
  color: rgba(0,0,0,0.5);
  margin-top:2px;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
  font-weight:500;
}
#rhk_topbar .rhk-topbar__right{
  display:flex;
  align-items:center;
  gap:8px;
  flex-wrap:wrap;
}
#rhk_topbar .rhk-chip{
  padding:6px 12px;
  border-radius:99px;
  font-size:12px;
  font-weight:600;
  background: rgba(255,255,255,0.5);
  border: 1px solid rgba(0,0,0,0.06);
  color:#4b5563;
  white-space:nowrap;
}
#rhk_topbar .rhk-chip--primary{
  background: rgba(37,99,235,0.1);
  border-color: rgba(37,99,235,0.2);
  color:#2563eb;
}

""".strip() % DESKTOP_VIEWPORT_WIDTH_PX)

JS_ON_LOAD = r"""
() => {
  // Force light mode (this app is styled for light mode)
  const applyLight = () => {
    try {
      document.documentElement.classList.remove('dark');
      document.body.classList.remove('dark');
      // Some Gradio builds use attributes / data-theme instead of a class
      try { document.documentElement.setAttribute('data-theme','light'); } catch (e) {}
      try { document.body.setAttribute('data-theme','light'); } catch (e) {}
      document.documentElement.style.colorScheme = 'light';
      document.body.style.colorScheme = 'light';
      try { document.documentElement.style.backgroundColor = '#f6f7fb'; } catch (e) {}
      try { document.body.style.backgroundColor = '#f6f7fb'; } catch (e) {}

      // Best-effort: prevent persistence of dark preference
      try {
        localStorage.setItem('theme', 'light');
        localStorage.setItem('gradio_theme', 'light');
        localStorage.setItem('gradio-theme', 'light');
      } catch (e) {}
    } catch (e) {}
  };

  // Ensure nothing is collapsed into a "More/…" overflow menu.
  // Users must always see all tabs and all P-Module options deterministically.
  const fixOverflows = () => {
    try {
      // Tabs: wrap instead of overflow (Gradio versions differ in markup)
      const tablists = document.querySelectorAll('#rhk_input_tabs [role="tablist"], #rhk_output_tabs [role="tablist"], [role="tablist"]');
      tablists.forEach((tl) => {
        try {
          tl.style.flexWrap = 'wrap';
          tl.style.overflow = 'visible';
          tl.style.whiteSpace = 'normal';
        } catch (e) {}
      });
      // Tab buttons: never truncate into ellipsis
      document.querySelectorAll('#rhk_input_tabs [role="tab"], #rhk_output_tabs [role="tab"], [role="tab"]').forEach((b) => {
        try {
          b.style.whiteSpace = 'normal';
          b.style.maxWidth = 'none';
          b.style.textOverflow = 'clip';
          b.style.overflow = 'visible';
        } catch (e) {}
      });

      // Hide icon-only overflow menu buttons (… / three-dots) inside tab bars
      document.querySelectorAll('#rhk_input_tabs [role="tablist"] button, #rhk_output_tabs [role="tablist"] button').forEach((b) => {
        try {
          const role = b.getAttribute('role') || '';
          if (role.toLowerCase() === 'tab') return;
          const label = (b.getAttribute('aria-label') || '').toLowerCase();
          const title = (b.getAttribute('title') || '').toLowerCase();
          const cls = (b.className || '').toLowerCase();
          const hasPopup = (b.getAttribute('aria-haspopup') || '').toLowerCase();
          const looksLikeOverflow =
            hasPopup === 'menu' ||
            label.includes('more') || label.includes('mehr') || label.includes('overflow') ||
            title.includes('more') || title.includes('mehr') ||
            cls.includes('overflow') || cls.includes('more') || cls.includes('ellipsis') ||
            (b.querySelector && b.querySelector('svg'));
          if (looksLikeOverflow) {
            b.style.display = 'none';
            b.setAttribute('aria-hidden', 'true');
          }
        } catch (e) {}
      });


      // P-Module option lists: never collapse/clip
      ['#pmods_choice_lvl1', '#pmods_choice_lvl2', '#pmods_choice_lvl3'].forEach((sel) => {
        const root = document.querySelector(sel);
        if (!root) return;
        try { root.style.maxHeight = 'none'; root.style.overflow = 'visible'; } catch (e) {}
        const wrap = root.querySelector('.wrap');
        if (wrap) {
          try { wrap.style.maxHeight = 'none'; wrap.style.overflow = 'visible'; } catch (e) {}
        }
      });

      // Hide any overflow "More/Mehr" controls created by Gradio
      const maybeHide = (el) => {
        const t = (el && el.innerText ? el.innerText.trim() : '');
        if (!t) return;
        const isMore = (
          t === 'More' || t === 'More…' || t === 'More...' ||
          t === 'Mehr' || t === 'Mehr…' || t === 'Mehr...' ||
          /^\+\d+\s*more$/i.test(t) || /^\+\d+\s*mehr$/i.test(t)
        );
        if (!isMore) return;

        const inTabs = el.closest('[role="tablist"], .tabs, .tab-nav, .tabitem, .tab-nav__overflow, .tab-nav__more');
        const inModules = el.closest('#pmods_choice_lvl1, #pmods_choice_lvl2, #pmods_choice_lvl3');
        if (inTabs || inModules) {
          try { el.style.display = 'none'; el.setAttribute('aria-hidden', 'true'); } catch (e) {}
        }
      };

      document.querySelectorAll('button, div, span, a').forEach(maybeHide);

      document.querySelectorAll(
        'button[aria-label*="More"], button[aria-label*="Mehr"], button[title*="More"], button[title*="Mehr"]'
      ).forEach((b) => {
        const inTabs = b.closest('[role="tablist"], .tabs, .tab-nav');
        const inModules = b.closest('#pmods_choice_lvl1, #pmods_choice_lvl2, #pmods_choice_lvl3');
        if (inTabs || inModules) {
          try { b.style.display = 'none'; b.setAttribute('aria-hidden', 'true'); } catch (e) {}
        }
      });
    } catch (e) {}
  };

  // Desktop-only overlay (blocks interaction on small screens)
  const DESKTOP_ONLY = __DESKTOP_ONLY__;
  const MIN_W = __MIN_WIDTH__;

  const isMobileUA = () => /Mobi|Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent || "");

  const isSmallViewport = () => {
    const w = window.innerWidth || 0;
    return (w > 0) && (w < MIN_W);
  };

  const ensureOverlay = (show) => {
    const existing = document.getElementById("rhk_desktop_only_overlay");
    if (show) {
      if (existing) return;
      const overlay = document.createElement("div");
      overlay.id = "rhk_desktop_only_overlay";
      overlay.innerHTML = `
        <div class="rhk-desktop-only-box">
          <h2>Desktop erforderlich</h2>
          <p>Diese Anwendung ist für Desktop/Laptop optimiert (großer Bildschirm, viele Eingabefelder).</p>
          <p><b>Bitte öffnen Sie sie auf einem Desktop-Computer.</b></p>
        </div>
      `;
      document.body.appendChild(overlay);
      try { document.body.style.overflow = "hidden"; } catch (e) {}
    } else {
      if (!existing) return;
      existing.remove();
      try { document.body.style.overflow = ""; } catch (e) {}
    }
  };

  const update = () => {
    applyLight();
    fixOverflows();
    if (!DESKTOP_ONLY) {
      ensureOverlay(false);
      return;
    }
    const block = isMobileUA() || isSmallViewport();
    ensureOverlay(block);
  };

  // Re-apply light mode if the framework toggles theme after render
  try {
    const obs = new MutationObserver(() => { applyLight(); fixOverflows(); });
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['class', 'data-theme'] });
    obs.observe(document.body, { attributes: true, attributeFilter: ['class', 'data-theme'] });
  } catch (e) {}

  update();
  setTimeout(update, 50);
  setTimeout(update, 250);
  window.addEventListener("resize", () => setTimeout(update, 50));
}
"""
JS_ON_LOAD = JS_ON_LOAD.replace("__DESKTOP_ONLY__", "true" if DESKTOP_ONLY else "false")
JS_ON_LOAD = JS_ON_LOAD.replace("__MIN_WIDTH__", str(DESKTOP_MIN_WIDTH_PX)).strip()


def _gradio_major_version() -> int:
    """Best-effort: parse gradio.__version__ major number.

    Gradio 6 moved app-level params (theme/css/js/head) from Blocks() to launch().
    We support both so the project runs with gradio>=5,<7.
    """
    try:
        v = getattr(gr, "__version__", "0")
        return int(str(v).split(".")[0])
    except Exception:
        return 0


def build_demo() -> Tuple[gr.Blocks, str, gr.Theme]:
    blocks = load_textdb_blocks()
    rules = load_rulebook(DEFAULT_RULEBOOK_PATH)

    theme = gr.themes.Soft()

    blocks_kwargs: Dict[str, Any] = {"title": APP_TITLE}
    major = _gradio_major_version()
    # Apply styling/js/head across Gradio 5.x and 6.x
    blocks_kwargs.update({"theme": theme, "css": CSS, "js": JS_ON_LOAD, "head": HEAD_HTML})

    # Build Blocks with best-effort compatibility across Gradio 5.x / 6.x
    demo_ctx = None
    _kwargs_try = dict(blocks_kwargs)
    for _drop in [[], ["head"], ["head", "js"], ["head", "js", "css"], ["head", "js", "css", "theme"]]:
        try:
            _k = dict(_kwargs_try)
            for kk in _drop:
                _k.pop(kk, None)
            demo_ctx = gr.Blocks(**_k)
            break
        except TypeError:
            demo_ctx = None
    if demo_ctx is None:
        demo_ctx = gr.Blocks(title=APP_TITLE)

    with demo_ctx as demo:
        # Header
        gr.HTML(RHK_HEADER_HTML)
        gr.Markdown(f"<div class='whatsnew'>{WHATS_NEW}</div>")
# Buttons top
        with gr.Row():
            btn_example_top = gr.Button("Beispiel laden (random)", variant="secondary")
            btn_generate_top = gr.Button("Befund erstellen/aktualisieren", variant="secondary", elem_id="btn_generate_top")
            btn_clear_top = gr.Button("Befunde leeren", variant="secondary")
            save_btn_top = gr.Button("Fall speichern (.json)", variant="secondary")
            load_btn_top = gr.UploadButton("Fall laden (.json)", file_types=[".json"], variant="secondary")

        # Layout: left inputs, right outputs
        with gr.Row():
            with gr.Column(scale=7):
                tabs = gr.Tabs(elem_id="rhk_input_tabs")

                field_components: Dict[str, gr.components.Component] = {}

                def add(name: str, comp: gr.components.Component):
                    field_components[name] = comp
                    return comp

                # ---- Tab 1: Klinik & Labor ----
                with gr.TabItem("Klinik & Labor", id=0):
                    with gr.Row():
                        add("firstname", gr.Textbox(label="Vorname"))
                        add("name", gr.Textbox(label="Name"))
                    with gr.Row():
                        add("age", gr.Number(label="Alter (Jahre)"))
                        add("sex", gr.Dropdown(label="Geschlecht", choices=["weiblich", "männlich", "divers"], value=None))
                    with gr.Row():
                        add("height_cm", gr.Number(label="Größe (cm)"))
                        add("weight_kg", gr.Number(label="Gewicht (kg)"))
                    with gr.Row():
                        add("bp_sys", gr.Number(label="RR syst (mmHg)"))
                        add("bp_dia", gr.Number(label="RR diast (mmHg)"))
                        add("hr", gr.Number(label="Herzfrequenz (/min)"))
                    add("story", gr.Textbox(label="Story / Kurz-Anamnese", lines=3))
                    with gr.Row():
                        add("chd_pos", gr.Checkbox(label="Angeborener Herzfehler/Shunt bekannt oder V. a."))
                    with gr.Column(visible=False) as chd_details:
                        add("chd_type", gr.Dropdown(label="Welche Diagnose? (optional)", choices=["ASD (Vorhofseptumdefekt)", "VSD (Ventrikelseptumdefekt)", "PDA (Ductus arteriosus persistens)", "AVSD (atrioventrikulärer Septumdefekt)", "Komplexer Herzfehler / univentrikulär", "Eisenmenger-Syndrom", "Status nach Korrektur (z.B. Shunt-Verschluss)", "Sonstiges/unklar"], value=None))
                        add("chd_desc", gr.Textbox(label="Details (optional)", lines=2))

                    with gr.Row():
                        ph_known = add("ph_known", gr.Checkbox(label="PH-Diagnose bekannt"))
                        ph_suspected = add("ph_suspected", gr.Checkbox(label="PH-Verdachtsdiagnose"))

                    # Bekannte PH: Details (nur sichtbar, wenn „PH-Diagnose bekannt“ aktiviert ist)
                    with gr.Column(visible=False) as ph_known_details:
                        gr.Markdown("#### Bekannte PH – Details")
                        add("ph_known_dx", gr.Dropdown(
                            label="Bekannte PH-Diagnose (Gruppe/Typ)",
                            choices=[
                                "PAH (Gruppe 1)",
                                "PH bei Linksherzerkrankung / HFpEF (Gruppe 2)",
                                "PH bei Lungenerkrankung / Hypoxie (Gruppe 3)",
                                "CTEPH (Gruppe 4)",
                                "Sonstige/unklar (Gruppe 5)",
                            ],
                            value=None,
                        ))
                        add("ph_known_subtype", gr.Textbox(label="Subtyp / Kontext (optional)", lines=2, placeholder="z.B. Systemsklerose, Portopulmonal, idiopathisch …"))
                        with gr.Row():
                            add("ph_first_dx", gr.Textbox(label="Erstdiagnose (MM/JJJJ)", placeholder="z.B. 03/2021"))
                            add("ph_reason_rhk", gr.Dropdown(
                                label="Grund der aktuellen Untersuchung",
                                choices=["Verlaufskontrolle", "Therapieentscheidung", "Neusymptomatik", "vor Eingriff/OP", "Sonstiges"],
                                value=None,
                            ))

                        ph_med_choices = [
                            "PDE‑5‑Hemmer",
                            "sGC‑Stimulator (Riociguat)",
                            "Endothelin‑Rezeptorantagonist (ERA)",
                            "Prostazyklin‑Therapie / -Analogon",
                            "IP‑Rezeptoragonist (z.B. Selexipag)",
                            "Kalziumantagonist (bei Vasoreaktivität)",
                            "Diuretikum",
                            "Sauerstofftherapie",
                            "Sonstiges",
                        ]
                        add("ph_current_meds", gr.Dropdown(
                            label="Aktuelle Therapie (Mehrfachauswahl)",
                            choices=ph_med_choices,
                            multiselect=True,
                            value=[],
                        ))
                        add("ph_prev_meds", gr.Dropdown(
                            label="Frühere Therapie (optional, Mehrfachauswahl)",
                            choices=ph_med_choices,
                            multiselect=True,
                            value=[],
                        ))
                        add("ph_interventions", gr.Dropdown(
                            label="Bereits durchgeführte Interventionen (optional, Mehrfachauswahl)",
                            choices=[
                                "PEA (Pulmonalisendarteriektomie, OP)",
                                "BPA (Ballonangioplastie, Katheter)",
                                "Vasoreaktivitätstest",
                                "Intensivtherapie/Parenteraltherapie",
                                "LTX-Evaluation (Transplantations-Abklärung)",
                                "Sonstiges",
                            ],
                            multiselect=True,
                            value=[],
                        ))


                    gr.Markdown("### Symptome / Funktion")
                    with gr.Row():
                        add("who_fc", gr.Dropdown(label="WHO-FC", choices=["I", "II", "III", "IV"], value=None))
                        add("six_mwd_m", gr.Number(label="6MWD (m)"))
                        add("syncope", gr.Dropdown(label="Synkope", choices=["keine", "gelegentlich", "wiederholt"], value=None))
                    with gr.Row():
                        add("hemoptysis", gr.Checkbox(label="Hämoptyse"))
                        add("dizziness", gr.Checkbox(label="Schwindel"))
                        add("stairs_flights", gr.Number(label="Treppen (Etagen) bis Pause", precision=0))

                    gr.Markdown("### Labor")
                    with gr.Row():
                        add("hb_g_dl", gr.Number(label="Hb (g/dl)"))
                        anemia_type = add("anemia_type", gr.Dropdown(
                            label="Anämie-Typ (falls Anämie vorliegt)",
                            choices=["mikrozytär", "normozytär", "makrozytär", "hämolytisch", "akute Blutung/Blutverlust", "unklar"],
                            value=None,
                            visible=False,
                        ))
                    with gr.Row():
                        add("crp_mg_l", gr.Number(label="CRP (mg/l)"))
                        add("leukocytes_g_l", gr.Number(label="Leukozyten (G/l)"))
                        add("platelets_g_l", gr.Number(label="Thrombozyten (G/l)"))
                    with gr.Row():
                        add("creatinine_mg_dl", gr.Number(label="Kreatinin (mg/dl)"))
                        add("inr", gr.Number(label="INR"))
                        add("ptt_s", gr.Number(label="PTT (s)"))
                    with gr.Row():
                        add("egfr", gr.Number(label="eGFR (ml/min/1,73m²)"))
                    with gr.Row():
                        add("bnp_kind", gr.Dropdown(label="BNP/NT-proBNP", choices=["BNP", "NT-proBNP"], value="NT-proBNP"))
                        add("bnp_value", gr.Number(label="Wert (pg/ml)"))
                        add("entresto", gr.Checkbox(label="Entresto/ARNI? (BNP eingeschränkt)"))
                    with gr.Row():
                        add("congestive_organopathy", gr.Radio(label="Hinweis auf congestive Organopathie?", choices=["ja", "nein"], value=None))

                    gr.Markdown("### Medikation & wichtige Zusatzangaben")

                    # Antikoagulation (wichtig v.a. für CTEPH-/Embolie-Logik)
                    with gr.Row():
                        anticoag_status = add("anticoag_status", gr.Dropdown(
                            label="Antikoagulation (Blutverdünnung)?",
                            choices=["ja", "nein", "unklar"],
                            value=None,
                        ))
                        anticoag_substance = add("anticoag_substance", gr.Dropdown(
                            label="Substanz / Klasse (falls ja)",
                            choices=[
                                "DOAC (Apixaban, Rivaroxaban, Edoxaban, Dabigatran)",
                                "VKA (Phenprocoumon/Warfarin)",
                                "Heparin/LMWH",
                                "Fondaparinux",
                                "sonstiges",
                            ],
                            value=None,
                            visible=False,
                        ))
                    with gr.Row():
                        anticoag_indication = add("anticoag_indication", gr.Dropdown(
                            label="Indikation (falls ja)",
                            choices=["Vorhofflimmern", "Venenthrombose/Lungenembolie", "CTEPH/CTEPD", "Mechanische Klappe", "Andere/unklar"],
                            value=None,
                            visible=False,
                        ))
                        anticoag_since = add("anticoag_since", gr.Textbox(
                            label="seit wann (optional)",
                            placeholder="MM/JJJJ",
                            visible=False,
                        ))
                    anticoag_note = add("anticoag_note", gr.Textbox(
                        label="Antikoagulation – Bemerkung (optional)",
                        lines=2,
                        visible=False,
                    ))

                    # Lungentransplantations-Evaluation (LTX)
                    with gr.Row():
                        add("ltx_eval", gr.Dropdown(
                            label="LTX-Evaluation (Transplantations-Abklärung) erfolgt?",
                            choices=["ja", "nein", "unklar"],
                            value=None,
                        ))
                        add("ltx_eval_date", gr.Textbox(label="LTX-Evaluation: Datum (optional)", placeholder="MM/JJJJ"))


                # ---- Tab 2: Bildgebung & Echo/CMR (merged) ----
                with gr.TabItem("Bildgebung & Echo/CMR", id=1):
                    gr.Markdown("### Thorax-Bildgebung")
                    with gr.Row():
                        add("ct_done", gr.Checkbox(label="CT Thorax/CT-Angio durchgeführt"))
                        add("vq_done", gr.Checkbox(label="V/Q durchgeführt"))
                    with gr.Row():
                        add("ct_ild", gr.Checkbox(label="ILD"))
                        add("ct_emphysema", gr.Checkbox(label="Emphysem"))
                        add("ct_embolie", gr.Checkbox(label="Embolie"))
                        add("ct_mosaic", gr.Checkbox(label="Mosaikperfusion"))
                        add("ct_koronarkalk", gr.Checkbox(label="Koronarkalk"))

                    with gr.Accordion("ILD – Details (nur bei ILD)", open=False) as acc_ild:
                        add("ild_type", gr.Textbox(label="Welche ILD?", lines=1))
                        with gr.Row():
                            add("ild_histology", gr.Checkbox(label="Histologisch gesichert?"))
                            add("ild_fibrosis_clinic", gr.Checkbox(label="An Fibroseambulanz angebunden?"))
                    add("ild_extent", gr.Dropdown(label="Ausmaß der ILD", choices=["", "gering", "mittel", "ausgedehnt"], value=""))

                    # ILD – Antifibrotische Therapie (nur sichtbar, wenn ILD markiert ist)
                    with gr.Column(visible=False) as ild_tx_details:
                        gr.Markdown("#### ILD – Antifibrotische Therapie")
                        antifib_status = add("antifibrotic_status", gr.Dropdown(
                            label="Antifibrotische Therapie vorhanden?",
                            choices=["ja", "nein", "unklar"],
                            value=None,
                        ))
                        with gr.Row():
                            antifib_drug = add("antifibrotic_drug", gr.Dropdown(
                                label="Präparat (falls ja)",
                                choices=["Nintedanib", "Pirfenidon", "sonstiges"],
                                value=None,
                                visible=False,
                            ))
                            antifib_since = add("antifibrotic_since", gr.Textbox(
                                label="seit wann (optional)",
                                placeholder="MM/JJJJ",
                                visible=False,
                            ))
                        antifib_note = add("antifibrotic_note", gr.Textbox(
                            label="Bemerkung (optional)",
                            lines=2,
                            visible=False,
                        ))


                    with gr.Accordion("V/Q – Details (nur bei V/Q)", open=False) as acc_vq:
                        with gr.Row():
                            add("vq_defect", gr.Checkbox(label="V/Q pathologisch (Perfusionsdefekte)"))
                            add("vq_desc", gr.Textbox(label="V/Q – Kurzbeschreibung", lines=2))

                    gr.Markdown("### Echokardiographie")
                    with gr.Row():
                        add("echo_done", gr.Checkbox(label="Echo durchgeführt"))
                        add("lvef", gr.Number(label="LV-EF (%)"))
                        add("la_enlarged", gr.Checkbox(label="Linksatrium erweitert"))
                    with gr.Row():
                        add("ee_ratio", gr.Number(label="E/e'"))
                        add("pasp_echo", gr.Number(label="sPAP Echo (mmHg)"))
                        add("tapse_mm", gr.Number(label="TAPSE (mm)"))
                        add("atrial_fib", gr.Checkbox(label="Vorhofflimmern"))
                    with gr.Row():
                        add("trv_ms", gr.Number(label="TRV max (m/s)", precision=2))
                        add("pa_diam_mm", gr.Number(label="PA Durchmesser (mm)", precision=0))
                        add("rv_lv_ratio", gr.Number(label="RV/LV Ratio", precision=2))
                        add("septal_flattening", gr.Checkbox(label="Septumflattening"))
                    with gr.Row():
                        add("s_prime_cm_s", gr.Number(label="Trikuspidales S' (cm/s)"))
                        add("ra_esa_cm2", gr.Number(label="RA ESA (cm²)"))
                        add("rv_edd_mm", gr.Number(label="RV EDD (mm)", precision=0))
                    with gr.Row():
                        add("ivc_diam_mm", gr.Number(label="V. cava inferior Durchmesser (mm)"))
                        add("ivc_collapse", gr.Radio(label="VCI Kollaps >50%?", choices=["ja", "nein"], value=None))

                    gr.Markdown("### MRT / CMR (optional)")
                    with gr.Row():
                        add("cmr_done", gr.Checkbox(label="CMR durchgeführt"))
                        add("rvef", gr.Number(label="RV-EF (%)"))
                        add("rvesvi", gr.Number(label="RVESVi (ml/m²)"))

                # ---- Tab 3: Lungenfunktion ----
                with gr.TabItem("Lungenfunktion", id=2):
                    with gr.Row():
                        add("lufu_done", gr.Checkbox(label="Lufu durchgeführt"))
                        add("lufu_obstructive", gr.Checkbox(label="Obstruktiv"))
                        add("lufu_restrictive", gr.Checkbox(label="Restriktiv"))
                        add("lufu_diffusion", gr.Checkbox(label="Diffusionsstörung"))
                    with gr.Row():
                        add("fev1_l", gr.Number(label="FEV1 (l)"))
                        add("fvc_l", gr.Number(label="FVC (l)"))
                        add("dlco_sb", gr.Number(label="DLCO SB (optional)"))
                    with gr.Row():
                        add("dlco_va", gr.Number(label="DLCO/VA (optional)"))
                        add("residual_volume_l", gr.Number(label="Residualvolumen RV (l, optional)"))
                    add("lufu_summary", gr.Textbox(label="Lufu Summary (Freitext)", lines=3))

                # ---- Tab 4: RHK ----
                with gr.TabItem("RHK", id=3):
                    gr.Markdown("### Ruhehämodynamik")
                    with gr.Row():
                        add("spap_rest", gr.Number(label="sPAP (mmHg)"))
                        add("dpap_rest", gr.Number(label="dPAP (mmHg)"))
                        add("mpap_rest", gr.Number(label="mPAP (optional)"))
                    with gr.Row():
                        add("pawp_rest", gr.Number(label="PAWP (mmHg)"))
                        add("rap_rest", gr.Number(label="RAP (mmHg)"))
                    with gr.Row():
                        add("co_rest", gr.Number(label="CO (l/min)"))
                        add("ci_rest", gr.Number(label="CI (optional)"))
                        add("pvr_rest", gr.Number(label="PVR (optional, WU)"))

                    gr.Markdown("#### Auto-Berechnung (wird nach „Befund erstellen“ gefüllt)")
                    with gr.Row():
                        auto_mpap = gr.Number(label="mPAP (berechnet)", interactive=False)
                        auto_ci = gr.Number(label="CI (berechnet)", interactive=False)
                        auto_pvr = gr.Number(label="PVR (berechnet)", interactive=False)
                    with gr.Row():
                        auto_pvri = gr.Number(label="PVRi (berechnet)", interactive=False)
                        auto_tpg = gr.Number(label="TPG (berechnet)", interactive=False)
                        auto_dpg = gr.Number(label="DPG (berechnet)", interactive=False)

                    gr.Markdown("### Belastungshämodynamik (optional)")
                    with gr.Row():
                        add("exercise_protocol", gr.Dropdown(choices=["", "WHO-Rampe", "Stufenprotokoll", "Laufband", "unbekannt"], value="", label="Belastungsprotokoll"))
                        add("exercise_peak_watts", gr.Number(label="Max. Last (W)"))
                    with gr.Row():
                        add("exercise_done", gr.Checkbox(label="Belastung durchgeführt"))
                        add("spap_peak", gr.Number(label="sPAP Peak (mmHg)"))
                        add("dpap_peak", gr.Number(label="dPAP Peak (mmHg)"))
                        add("mpap_peak", gr.Number(label="mPAP Peak (optional)"))
                    with gr.Row():
                        add("pawp_peak", gr.Number(label="PAWP Peak (mmHg)"))
                        add("co_peak", gr.Number(label="CO Peak (l/min)"))
                        add("ci_peak", gr.Number(label="CI Peak (l/min/m²) (optional)"))

                    gr.Markdown("### Volumenchallenge (optional)")
                    with gr.Row():
                        add("volume_challenge_done", gr.Checkbox(label="Volumenchallenge durchgeführt"))
                        add("pawp_pre", gr.Number(label="PAWP pre (mmHg)"))
                        add("pawp_post", gr.Number(label="PAWP post (mmHg)"))
                    with gr.Row():
                        add("mpap_pre", gr.Number(label="mPAP pre (mmHg)"))
                        add("mpap_post", gr.Number(label="mPAP post (mmHg)"))

                    gr.Markdown("### Vasoreaktivität (optional)")
                    with gr.Row():
                        add("vaso_test_done", gr.Checkbox(label="Vasoreaktivität getestet"))
                        add("vaso_agent", gr.Textbox(label="Agent (z.B. iNO)", lines=1))
                    add("vaso_response_desc", gr.Textbox(label="Antwort / Kommentar", lines=2))
                    with gr.Row():
                        add("vaso_mpap_pre", gr.Number(label="mPAP vor Test (mmHg)", precision=0))
                        add("vaso_co_pre", gr.Number(label="CO vor Test (L/min)", precision=2))
                        add("vaso_mpap_post", gr.Number(label="mPAP nach Test (mmHg)", precision=0))
                        add("vaso_co_post", gr.Number(label="CO nach Test (L/min)", precision=2))

                    gr.Markdown("### Stufenoxymetrie (optional)")
                    with gr.Row():
                        add("sat_svc", gr.Number(label="SVC O2-Sättigung (%)"))
                        add("sat_ivc", gr.Number(label="IVC O2-Sättigung (%)"))
                        add("sat_ra", gr.Number(label="RA O2-Sättigung (%)"))
                    with gr.Row():
                        add("sat_rv", gr.Number(label="RV O2-Sättigung (%)"))
                        add("sat_pa", gr.Number(label="PA O2-Sättigung (%)"))
                        add("sat_ao", gr.Number(label="Aorta O2-Sättigung (%)"))

                    gr.Markdown("### Kurvenmorphologie (optional)")
                    with gr.Row():
                        add("wedge_v_wave", gr.Checkbox(label="Prominente V-Welle (PAWP)"))
                        add("wedge_a_wave", gr.Checkbox(label="Prominente A-Welle (PAWP)"))
                        add("rap_a_wave", gr.Checkbox(label="Prominente A-Welle (RAP)"))
                        add("rap_v_wave", gr.Checkbox(label="Prominente V-Welle (RAP)"))
                    with gr.Row():
                        add("rv_pseudo_dip", gr.Checkbox(label="Pseudo-Dip (RV-Kurve)"))
                        add("rv_dip_plateau", gr.Checkbox(label="Dip-Plateau (RV-Kurve)"))

                    gr.Markdown("### Verlauf / Vergleich (Vor-RHK, optional)")

                    with gr.Row():

                        add("prev_rhk_date", gr.Textbox(label="Vor-RHK (z.B. 03/21)"))

                        add("prev_is_initial", gr.Checkbox(label="Vor-RHK war Initialkatheter"))

                    with gr.Row():

                        add("prev_mpap", gr.Number(label="mPAP vor (mmHg)"))

                        add("prev_pawp", gr.Number(label="PAWP vor (mmHg)"))

                        add("prev_rap", gr.Number(label="RAP vor (mmHg)"))

                    with gr.Row():

                        add("prev_ci", gr.Number(label="CI vor (l/min/m²)"))

                        add("prev_pvr", gr.Number(label="PVR vor (WU)"))

                        add("prev_label", gr.Textbox(label="Kommentar (optional)"))

                    gr.Markdown("**Therapie seit Vor-RHK (optional):** Nur relevant, wenn es sich um eine Verlaufskontrolle nach Therapieanpassung handelt.")

                    add("prev_tx_added", gr.CheckboxGroup(label="Therapie neu/eskaliert", choices=['ERA (Endothelin-Rezeptor-Antagonist)', 'PDE5-Hemmer', 'sGC-Stimulator (Riociguat)', 'Prostazyklin (inhalativ/IV/SC)', 'IP-Rezeptor-Agonist (Selexipag)', 'Kalziumantagonist (bei Vasoreaktivität)', 'Antikoagulation', 'Diuretika / Entwässerung', 'Sauerstofftherapie', 'Sonstiges'], value=[]))

                    add("prev_tx_free", gr.Textbox(label="Therapie – Freitext (optional)", lines=2))

                # ---- Tab 5: Weitere Bereiche ----
                with gr.TabItem("Weitere Befunde", id=4):
                    gr.Markdown("### Blutgase / LTOT")
                    with gr.Row():
                        add("ltot", gr.Checkbox(label="LTOT vorhanden"))
                        ltot_flow = add("ltot_flow_l_min", gr.Number(label="LTOT (l/min)", visible=False))
                    gr.Markdown("### Infektiologie / Immunologie")
                    with gr.Row():
                        add("virology_pos", gr.Checkbox(label="Virologie/Infektiologie positiv"))
                    with gr.Row():
                        viro_items = add("virology_items", gr.Dropdown(
                            label="Virologie/Infektiologie – Auswahl (optional, Mehrfachauswahl)",
                            choices=["HIV", "Hepatitis B", "Hepatitis C", "Schistosomiasis (parasitär)", "Andere/unklar"],
                            multiselect=True,
                            value=[],
                            visible=False,
                        ))
                        viro_desc = add("virology_desc", gr.Textbox(label="Virologie/Infektiologie – Details", lines=2, visible=False))

                    with gr.Row():
                        add("immunology_pos", gr.Checkbox(label="Immunologie/Autoimmun positiv"))
                    with gr.Row():
                        immun_items = add("immunology_items", gr.Dropdown(
                            label="Immunologie/Autoimmun – Auswahl (optional, Mehrfachauswahl)",
                            choices=[
                                "Systemische Sklerose (Sklerodermie)",
                                "SLE (Lupus erythematodes)",
                                "MCTD (Mixed connective tissue disease)",
                                "Sjögren-Syndrom",
                                "Rheumatoide Arthritis",
                                "Myositis",
                                "Vaskulitis",
                                "Antiphospholipid-Syndrom",
                                "Sarkoidose",
                                "Andere/unklar",
                            ],
                            multiselect=True,
                            value=[],
                            visible=False,
                        ))
                        immun_desc = add("immunology_desc", gr.Textbox(label="Immunologie/Autoimmun – Details", lines=2, visible=False))

                    gr.Markdown("### Genetik")
                    with gr.Row():
                        add("mutation_pos", gr.Checkbox(label="Mutation/Genetik relevant (PAH/PH-assoziiert)"))
                    with gr.Row():
                        mut_items = add("mutation_items", gr.Dropdown(
                            label="Genetik – Auswahl (optional, Mehrfachauswahl)",
                            choices=[
                                "BMPR2",
                                "ACVRL1 (ALK1)",
                                "ENG",
                                "SMAD9",
                                "KCNK3",
                                "TBX4",
                                "SOX17",
                                "ATP13A3",
                                "GDF2 (BMP9)",
                                "KDR",
                                "CAV1",
                                "EIF2AK4 (PVOD/PCH)",
                                "Andere/unklar",
                            ],
                            multiselect=True,
                            value=[],
                            visible=False,
                        ))
                        mut_desc = add("mutation_desc", gr.Textbox(label="Genetik – Details", lines=2, visible=False))

                    gr.Markdown("### Abdomen / Leber")
                    with gr.Row():
                        add("abd_sono_done", gr.Checkbox(label="Abdomen-Sono durchgeführt"))
                        abd_desc = add("abd_sono_desc", gr.Textbox(label="Besondere Befunde?", lines=2, visible=False))

                # ---- Tab 6: Procedere & Module ----
                with gr.TabItem("Procedere & Module", id=5):
                    p_ids = sorted([bid for bid, b in blocks.items() if b.kind == "module" and bid.startswith("P")])

                    # Baseline-Choices (werden nach „Generieren“ fallbasiert sortiert & gelabelt)
                    base_module_choices: List[Tuple[str, str]] = []
                    for pid in p_ids:
                        if pid in blocks:
                            base_module_choices.append((f"{pid} – {blocks[pid].title}", pid))

                    gr.Markdown("### P-Module (optional)")
                    gr.Markdown("**Level I – prioritäre Empfehlungen** · Level II – sinnvoll ergänzend · Level III – optional")
                    gr.Markdown(
                        "Die P-Module werden automatisch nach Sinnhaftigkeit in **Level I–III** sortiert. "
                        "Nicht passende Module werden **hellgrau** angezeigt und sind nicht anwählbar. "
                        "Falls Sie dennoch Aspekte dokumentieren möchten, nutzen Sie den **Freitext** im Procedere."
                    )

                    with gr.Group(elem_id="pmods_lvl1"):
                        modules_lvl1_comp = add(
                            "modules_lvl1",
                            gr.CheckboxGroup(
                                label="Level I – prioritäre Empfehlungen",
                                choices=[],
                                value=[],
                                elem_id="pmods_choice_lvl1",
                            ),
                        )

                    with gr.Group(elem_id="pmods_lvl2"):
                        modules_lvl2_comp = add(
                            "modules_lvl2",
                            gr.CheckboxGroup(
                                label="Level II – sinnvoll ergänzend",
                                choices=[],
                                value=[],
                                elem_id="pmods_choice_lvl2",
                            ),
                        )

                    with gr.Group(elem_id="pmods_lvl3"):
                        modules_lvl3_comp = add(
                            "modules_lvl3",
                            gr.CheckboxGroup(
                                label="Level III – optional",
                                choices=base_module_choices,
                                value=[],
                                elem_id="pmods_choice_lvl3",
                            ),
                        )
                    modules_disabled_html = gr.HTML(value="", elem_id="modules_disabled")
                    add("procedere_free", gr.Textbox(label="Procedere – Freitext", lines=3))
                    gr.Markdown("Hinweis: Bereits durchgeführte Untersuchungen werden in den Modulen möglichst ausgefiltert (z.B. V/Q, CT, Echo, Lufu).")

            with gr.Column(scale=5):
                dashboard = gr.HTML(value=build_dashboard_html(None))
                with gr.Tabs(elem_id="rhk_output_tabs"):
                    with gr.TabItem("Arztbericht"):
                        out_doc = gr.Markdown()
                    with gr.TabItem("Patientenbericht"):
                        out_pat = gr.Markdown()
                    with gr.TabItem("Intern"):
                        out_int = gr.Markdown()
                    with gr.TabItem("Debug"):
                        out_json = gr.Code(language="json")

        # Buttons bottom (mirrored)
        with gr.Row():
            btn_example_bottom = gr.Button("Beispiel laden (random)", variant="secondary")
            btn_generate_bottom = gr.Button("Befund erstellen/aktualisieren", variant="secondary", elem_id="btn_generate_bottom")
            btn_clear_bottom = gr.Button("Befunde leeren", variant="secondary")
            save_btn_bottom = gr.Button("Fall speichern (.json)", variant="secondary")
            load_btn_bottom = gr.UploadButton("Fall laden (.json)", file_types=[".json"], variant="secondary")

        file_out = gr.File(label="Download: gespeicherter Fall", visible=False)
        state_case = gr.State(value=None)

        # --- Conditional visibility bindings ---
        def _update_visibility_ild(ct_ild: bool):
            return (
                gr.update(visible=bool(ct_ild)),  # accordion open state cannot be updated; but content visible
            )

        # We can't update Accordion directly; instead show/hide inside by leaving content always, but ok.

        def _toggle_desc(flag: bool):
            return gr.update(visible=bool(flag))

        def _toggle_desc_text(flag: bool):
            return gr.update(visible=bool(flag))

        def _toggle_ltot(flag: bool):
            return gr.update(visible=bool(flag))

        def _toggle_anemia(hb_val, sex_val):
            hb = _safe_float(hb_val)
            anemia = _infer_anemia(sex_val, hb)
            return gr.update(visible=bool(anemia))
        field_components["virology_pos"].change(lambda x: (gr.update(visible=bool(x)), gr.update(visible=bool(x))), inputs=[field_components["virology_pos"]], outputs=[viro_items, viro_desc])
        field_components["immunology_pos"].change(lambda x: (gr.update(visible=bool(x)), gr.update(visible=bool(x))), inputs=[field_components["immunology_pos"]], outputs=[immun_items, immun_desc])
        field_components["mutation_pos"].change(lambda x: (gr.update(visible=bool(x)), gr.update(visible=bool(x))), inputs=[field_components["mutation_pos"]], outputs=[mut_items, mut_desc])
        field_components["chd_pos"].change(lambda x: gr.update(visible=bool(x)), inputs=[field_components["chd_pos"]], outputs=[chd_details])
        field_components["abd_sono_done"].change(lambda x: _toggle_desc_text(x), inputs=[field_components["abd_sono_done"]], outputs=[abd_desc])
        field_components["ltot"].change(lambda x: _toggle_ltot(x), inputs=[field_components["ltot"]], outputs=[ltot_flow])

        # Anemia type show/hide when Hb or sex changes
        field_components["hb_g_dl"].change(_toggle_anemia, inputs=[field_components["hb_g_dl"], field_components["sex"]], outputs=[anemia_type])
        field_components["sex"].change(_toggle_anemia, inputs=[field_components["hb_g_dl"], field_components["sex"]], outputs=[anemia_type])
        # Bekannte PH: Details ein-/ausblenden
        field_components["ph_known"].change(lambda x: _toggle_desc(x), inputs=[field_components["ph_known"]], outputs=[ph_known_details])

        # Antikoagulation: Detailfelder nur bei "ja"
        def _toggle_anticoag(status: str):
            on = str(status or "").strip().lower() == "ja"
            return (
                gr.update(visible=on),
                gr.update(visible=on),
                gr.update(visible=on),
                gr.update(visible=on),
            )
        field_components["anticoag_status"].change(_toggle_anticoag, inputs=[field_components["anticoag_status"]], outputs=[anticoag_substance, anticoag_indication, anticoag_since, anticoag_note])

        # ILD – Antifibrotika: Block nur bei ILD; Detailfelder nur bei "ja"
        field_components["ct_ild"].change(lambda x: _toggle_desc(x), inputs=[field_components["ct_ild"]], outputs=[ild_tx_details])

        def _toggle_antifib(status: str):
            on = str(status or "").strip().lower() == "ja"
            return (
                gr.update(visible=on),
                gr.update(visible=on),
                gr.update(visible=on),
            )
        field_components["antifibrotic_status"].change(_toggle_antifib, inputs=[field_components["antifibrotic_status"]], outputs=[antifib_drug, antifib_since, antifib_note])


        # --- Helpers to map UI dict to component list ---
        input_components = [field_components[k] for k in field_components.keys()]
        input_keys = list(field_components.keys())

        def ui_get_raw(*vals):
            return {k: v for k, v in zip(input_keys, vals)}

        def apply_ui_to_components(ui_dict: Dict[str, Any]) -> List[Any]:
            out: List[Any] = []
            for k in input_keys:
                v = ui_dict.get(k)
                if k == "modules":
                    # UI-Value sind reine IDs (P01–P25); robust gegen alte Case-Files mit Labels.
                    v = _normalize_module_ids(v)
                # Backward compatible mappings (alte Case-Files)
                if k == "syncope":
                    if isinstance(v, bool):
                        v = "gelegentlich" if v else "keine"
                if k == "anemia_type" and isinstance(v, str):
                    v_map = {
                        "microcytic": "mikrozytär",
                        "normocytic": "normozytär",
                        "macrocytic": "makrozytär",
                        "iron_deficiency": "mikrozytär",
                        "hemolytic": "hämolytisch",
                        "other": "unklar",
                    }
                    v = v_map.get(v, v)
                out.append(v)
            return out

        # --- Generate function ---
        def _generate(*vals):
            raw = ui_get_raw(*vals)
            # Module kommen aus der UI als IDs (Choices liefern Value=Pxx); zusätzlich robust normalisieren.
            raw["modules"] = _normalize_module_ids((raw.get("modules_lvl1") or []) + (raw.get("modules_lvl2") or []) + (raw.get("modules_lvl3") or []) + (raw.get("modules") or []))
            case = build_case(raw, rules)

            doc = build_doctor_report(case, blocks)
            pat = build_patient_report(case)
            internal = build_internal_report(case)
            dash = build_dashboard_html(case)

            # computed outputs
            der = case["derived"]
            ci_calc = None
            if der.get("co") is not None and der.get("bsa_m2") is not None and der.get("bsa_m2"):
                try:
                    ci_calc = float(der.get("co")) / float(der.get("bsa_m2"))
                except Exception:
                    ci_calc = None

            # --- P-Module UI: fallbasiert sortieren + nicht anwählbare Module (hellgrau) anzeigen ---
            policy = der.get("p_module_policy") or {}
            mod_choices = build_p_module_choices(blocks, policy)
            disabled_html = build_disabled_p_modules_html(blocks, policy)

            allowed_vals = {v for (_, v) in mod_choices}

            # Sichtbarkeit/Logik vereinheitlichen:
            # - "Auto"-Module aus dem Regelwerk (case.decision.modules) werden im Bericht verwendet,
            #   sollen aber auch in der UI als "vorselektiert" sichtbar sein.
            auto_mods = _normalize_module_ids((case.get("decision") or {}).get("modules") or [])
            sel_vals = _normalize_module_ids(case.get("ui", {}).get("modules") or [])

            # Auto + User-Auswahl zusammenführen (dedup, Reihenfolge: Auto zuerst)
            sel_vals = list(dict.fromkeys(auto_mods + sel_vals))

            # Nur erlaubte Module behalten
            sel_vals = [m for m in sel_vals if m in allowed_vals]

            # In den Case-State zurückschreiben, damit Save/Live-Update konsistent bleibt
            try:
                case.setdefault("ui", {})["modules"] = sel_vals
            except Exception:
                pass


            # --- P-Module UI updates (Level I/II/III + disabled list) ---
            choices_lvl1 = [(lab, mid) for (lab, mid) in mod_choices if lab.strip().startswith("[I]")]
            choices_lvl2 = [(lab, mid) for (lab, mid) in mod_choices if lab.strip().startswith("[II]")]
            choices_lvl3 = [(lab, mid) for (lab, mid) in mod_choices if lab.strip().startswith("[III]")]

            allowed_lvl1 = {mid for (_lab, mid) in choices_lvl1}
            allowed_lvl2 = {mid for (_lab, mid) in choices_lvl2}
            allowed_lvl3 = {mid for (_lab, mid) in choices_lvl3}

            selected_lvl1 = [m for m in sel_vals if m in allowed_lvl1]
            selected_lvl2 = [m for m in sel_vals if m in allowed_lvl2]
            selected_lvl3 = [m for m in sel_vals if m in allowed_lvl3]

            modules_lvl1_update = gr.update(choices=choices_lvl1, value=selected_lvl1)
            modules_lvl2_update = gr.update(choices=choices_lvl2, value=selected_lvl2)
            modules_lvl3_update = gr.update(choices=choices_lvl3, value=selected_lvl3)

            return (
                der.get("mpap_calc"), ci_calc, der.get("pvr_calc"), der.get("pvri"), der.get("tpg"), der.get("dpg"),
                dash, doc, pat, internal,
                json.dumps(case, ensure_ascii=False, indent=2),
                case,
                modules_lvl1_update,
                modules_lvl2_update,
                modules_lvl3_update,
                disabled_html,
            )
        generate_outputs = [
            auto_mpap, auto_ci, auto_pvr, auto_pvri, auto_tpg, auto_dpg,
            dashboard,
            out_doc, out_pat, out_int,
            out_json,
            state_case,
            modules_lvl1_comp, modules_lvl2_comp, modules_lvl3_comp,
            modules_disabled_html,
        ]

        btn_generate_top.click(_generate, inputs=input_components, outputs=generate_outputs)
        btn_generate_bottom.click(_generate, inputs=input_components, outputs=generate_outputs)

        # --- Live-Update: Procedere/Module sollen deterministisch im Bericht landen ---
        # Häufiger UX-Fehler: User ändert Module/Freitext nach dem Generieren und erwartet, dass der Bericht folgt.
        # Wir aktualisieren daher den Bericht direkt aus dem bestehenden Case-State, ohne alle Ableitungen neu zu rechnen.
        def _update_procedere_only(case_state, m1, m2, m3, free_text):
            if not case_state:
                # Noch kein Fall generiert – nichts zu aktualisieren.
                return (gr.update(), gr.update(), gr.update(), gr.update(), None)
            try:
                ui = dict(case_state.get("ui") or {})
                ui["modules_lvl1"] = m1 or []
                ui["modules_lvl2"] = m2 or []
                ui["modules_lvl3"] = m3 or []
                ui["procedere_free"] = free_text or ""
                ui["modules"] = _normalize_module_ids((ui.get("modules_lvl1") or []) + (ui.get("modules_lvl2") or []) + (ui.get("modules_lvl3") or []))
                case_state["ui"] = ui

                doc = build_doctor_report(case_state, blocks)
                pat = build_patient_report(case_state)
                internal = build_internal_report(case_state)
                dbg = json.dumps(case_state, ensure_ascii=False, indent=2)
                return (doc, pat, internal, dbg, case_state)
            except Exception:
                # Fail-safe: do not break UI on minor issues
                return (gr.update(), gr.update(), gr.update(), gr.update(), case_state)

        _procedere_inputs = [state_case, modules_lvl1_comp, modules_lvl2_comp, modules_lvl3_comp, field_components["procedere_free"]]
        _procedere_outputs = [out_doc, out_pat, out_int, out_json, state_case]

        modules_lvl1_comp.change(_update_procedere_only, inputs=_procedere_inputs, outputs=_procedere_outputs)
        modules_lvl2_comp.change(_update_procedere_only, inputs=_procedere_inputs, outputs=_procedere_outputs)
        modules_lvl3_comp.change(_update_procedere_only, inputs=_procedere_inputs, outputs=_procedere_outputs)
        field_components["procedere_free"].change(_update_procedere_only, inputs=_procedere_inputs, outputs=_procedere_outputs)
        # Optional: bei Enter/Submit ebenfalls
        try:
            field_components["procedere_free"].submit(_update_procedere_only, inputs=_procedere_inputs, outputs=_procedere_outputs)
        except Exception:
            pass

        # --- Example loader ---
        def _load_example():
            ui = random_example()
            vals = apply_ui_to_components(ui)
            gen = _generate(*vals)
            return (*vals, *gen)

        load_outputs = input_components + generate_outputs

        btn_example_top.click(_load_example, inputs=[], outputs=load_outputs)
        btn_example_bottom.click(_load_example, inputs=[], outputs=load_outputs)

        # --- Clear all (Befunde leeren) ---
        # Reset inputs to their initial default values and clear all outputs/state.
        _DEFAULT_INPUT_VALUES = [c.value for c in input_components]
        _INIT_CHOICES_LVL1 = getattr(modules_lvl1_comp, "choices", None)
        _INIT_CHOICES_LVL2 = getattr(modules_lvl2_comp, "choices", None)
        _INIT_CHOICES_LVL3 = getattr(modules_lvl3_comp, "choices", None)

        def _clear_all():
            # Inputs
            vals = list(_DEFAULT_INPUT_VALUES)

            # Outputs (mirror generate_outputs order)
            cleared_outputs = (
                None, None, None, None, None, None,  # auto_mpap..auto_dpg
                "",                                   # dashboard
                "", "", "",                            # out_doc, out_pat, out_int
                "{}",                                 # out_json
                None,                                 # state_case
                gr.update(choices=_INIT_CHOICES_LVL1, value=[]),
                gr.update(choices=_INIT_CHOICES_LVL2, value=[]),
                gr.update(choices=_INIT_CHOICES_LVL3, value=[]),
                "",                                   # modules_disabled_html
            )
            return (*vals, *cleared_outputs)

        btn_clear_top.click(_clear_all, inputs=[], outputs=load_outputs)
        btn_clear_bottom.click(_clear_all, inputs=[], outputs=load_outputs)


        # --- Clear / reset ---
        def _clear():
            # Reset all inputs + outputs deterministically
            empty_ui = {k: None for k in input_keys}
            # Explicit empties for list-like fields
            for lk in ("meds", "comorbidities", "modules_lvl1", "modules_lvl2", "modules_lvl3", "modules"):
                if lk in empty_ui:
                    empty_ui[lk] = []
            vals = apply_ui_to_components(empty_ui)

            # Reset module UI: show all modules initially in Level III
            modules_lvl1_update = gr.update(choices=[], value=[])
            modules_lvl2_update = gr.update(choices=[], value=[])
            modules_lvl3_update = gr.update(choices=base_module_choices, value=[])

            dash = build_dashboard_html(None)
            return (
                *vals,
                None, None, None, None, None, None,   # auto_* (6)
                dash,
                "", "", "",                             # doc, patient, internal
                "{}",                                   # JSON
                None,                                   # state_case
                modules_lvl1_update, modules_lvl2_update, modules_lvl3_update,
                "",                                     # disabled html
            )

        def _save_case(case_state):
            if not case_state:
                return gr.update(visible=False, value=None)
            # Store full case with ui/derived/decision; but saving 'ui' is enough; keep full for debugging
            path = os.path.join("/tmp", f"rhk_case_{_dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            export_json(case_state, path)
            return gr.update(visible=True, value=path)

        save_btn_top.click(_save_case, inputs=[state_case], outputs=[file_out])
        save_btn_bottom.click(_save_case, inputs=[state_case], outputs=[file_out])

        # --- Load case ---
        def _load_case(file):
            if file is None:
                return
            fp = file.name if hasattr(file, "name") else str(file)
            data = load_case_json(fp)
            # Accept either full case or ui-only
            ui_dict = data.get("ui") if isinstance(data, dict) and "ui" in data else data
            if not isinstance(ui_dict, dict):
                ui_dict = {}
            vals = apply_ui_to_components(ui_dict)
            gen = _generate(*vals)
            return (*vals, *gen)

        load_btn_top.upload(_load_case, inputs=[load_btn_top], outputs=load_outputs)
        load_btn_bottom.upload(_load_case, inputs=[load_btn_bottom], outputs=load_outputs)

    return demo, CSS, theme


