#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RHK Befundassistent – Gradio UI (split from rhk_app_web_master.py).

Enthält:
- Desktop-Only Overlay + Head/CSS/JS Assets
- build_demo() (Gradio Blocks + Callbacks)

Hinweis: UI modernisiert (Sticky-Bar, P-Module Karten, Vergleichsmodus).
"""

from __future__ import annotations

import html as _html

from rhk_base import *  # noqa: F401,F403

from rhk_case import build_case, build_dashboard_html  # noqa: F401
from rhk_reports import (
    build_doctor_report,
    build_patient_report,
    build_echo_patient_report,
    build_echo_doctor_report_extended,
    build_internal_report,
    random_example,
    export_json,
    export_summary_json,
    build_summary_dict,
    markdown_to_plain,
    markdown_to_word_html,
    extract_markdown_section,
    load_case_json,
)  # noqa: F401
from rhk_import_docx import parse_maclab_docx, map_payload_to_ui  # noqa: F401
from rhk_viz import svg_mpap_pawp_vs_co, svg_series_over_phases, svg_delta_bars, svg_compare_bars  # noqa: F401
from rhk_ui_echo import build_echo_section, bind_echo_import  # noqa: F401
from rhk_ui_rhk import build_rhk_tab  # noqa: F401


# =============================================================================
# Gradio UI
# =============================================================================

# --- Client/UI behaviour ------------------------------------------------------
# Desktop-only enforcement (optional):
# - The app is designed for wide screens.
# - If enabled, on small screens we display an overlay and block interaction.
# - Default is OFF, because forced viewports/min-width can produce confusing rendering.
# - Override explicitly with: RHK_DESKTOP_ONLY=0
# v26 default: ON (mobile is intentionally not supported)
DESKTOP_ONLY: bool = os.environ.get("RHK_DESKTOP_ONLY", "1").strip().lower() not in ("0", "false", "no", "off")
DESKTOP_MIN_WIDTH_PX: int = int(os.environ.get("RHK_DESKTOP_MIN_WIDTH", "1100"))
DESKTOP_VIEWPORT_WIDTH_PX: int = int(os.environ.get("RHK_DESKTOP_VIEWPORT_WIDTH", "1200"))

# Optional: Inject a desktop-like viewport on mobile browsers.
# This can be useful for debugging, but can also affect desktop rendering depending on browser/zoom.
# Default is OFF.
FORCE_DESKTOP_VIEWPORT: bool = os.environ.get("RHK_FORCE_DESKTOP_VIEWPORT", "0").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)
_VIEWPORT_META = (
    f'<meta name="viewport" content="width={DESKTOP_VIEWPORT_WIDTH_PX}, initial-scale=1">'
    if FORCE_DESKTOP_VIEWPORT
    else ""
)

# NOTE: We enforce a readable light UI even if the browser/system prefers dark.
# Additionally, we attach a robust, cross-browser copy-to-Word handler to the three copy buttons.
HEAD_HTML = "".join(
    [
        _VIEWPORT_META,
        '<meta name="color-scheme" content="light">',
        '<meta name="supported-color-schemes" content="light">',
        r"""
<script>
(function(){
  // ------------------------------------------------------------------
  // Hard-default to Gradio light theme.
  // Gradio's own theme system is driven by the query param `__theme`.
  // If it is missing, some browsers/system-preferences will render dark,
  // which breaks our carefully tuned light UI.
  // We therefore enforce: /?__theme=light (single reload, no flicker).
  // ------------------------------------------------------------------
  try {
    var u = new URL(window.location.href);
    var th = u.searchParams.get('__theme');
    if(th !== 'light'){
      u.searchParams.set('__theme', 'light');
      window.location.replace(u.toString());
      return;
    }
  } catch(e) {}

  function byId(id){ return document.getElementById(id); }
  function getTextboxValue(rootId){
    var root = byId(rootId);
    if(!root) return "";
    var el = root.querySelector('textarea,input');
    if(el && typeof el.value === 'string') return el.value;
    return (root.textContent || "").trim();
  }
  function setFeedback(msg){
    var root = byId('rhk_copy_feedback');
    if(!root) return;
    // Gradio Markdown often wraps content; try common containers.
    var tgt = root.querySelector('.prose, .markdown, .md, .wrap, div') || root;
    tgt.textContent = msg;
  }
  function extractFragment(html){
    if(!html) return "";
    var s = '<!--StartFragment-->';
    var e = '<!--EndFragment-->';
    var i = html.indexOf(s);
    var j = html.indexOf(e);
    if(i >= 0 && j > i) return html.substring(i + s.length, j).trim();
    // Fallback: extract <body>...</body>
    var m = html.match(/<body[^>]*>([\\s\\S]*?)<\/body>/i);
    if(m && m[1]) return m[1].trim();
    return String(html);
  }
  function copyToClipboard(html, plain){
    // `html` is a full Word-friendly HTML document (incl. StartFragment markers)
    // produced server-side. For copying we prefer the fragment so Word pastes cleanly.
    var rawHtml = (html === undefined || html === null) ? "" : String(html);
    var h = extractFragment(rawHtml);
    var t = (plain === undefined || plain === null) ? "" : String(plain);

    function copyPlainExec(){
      var ta = document.createElement('textarea');
      ta.value = t;
      ta.style.position = 'fixed';
      ta.style.left = '-9999px';
      ta.style.top = '0';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      var ok = false;
      try { ok = document.execCommand('copy'); } catch(e) {}
      document.body.removeChild(ta);
      return ok;
    }

    function copyHtmlExec(){
      // Robust cross-browser fallback:
      // Use a temporary contenteditable container + explicit clipboardData injection.
      var div = document.createElement('div');
      var safeText = t
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\n/g, '<br>');
      div.innerHTML = (h && h.trim().length) ? h : safeText;
      div.style.position = 'fixed';
      div.style.left = '0';
      div.style.top = '0';
      div.style.opacity = '0';
      div.style.pointerEvents = 'none';
      div.style.width = '1px';
      div.style.height = '1px';
      div.style.overflow = 'hidden';
      div.setAttribute('contenteditable', 'true');
      document.body.appendChild(div);

      var ok = false;
      var sel = window.getSelection();
      try {
        div.focus();
        var range = document.createRange();
        range.selectNodeContents(div);
        sel.removeAllRanges();
        sel.addRange(range);
      } catch(e) {}

      function onCopy(e){
        try {
          if(e && e.clipboardData){
            // Prefer fragment for Word.
            e.clipboardData.setData('text/html', (h && h.trim().length) ? h : safeText);
            e.clipboardData.setData('text/plain', t);
            e.preventDefault();
            ok = true;
          }
        } catch(err) {}
      }
      div.addEventListener('copy', onCopy);
      try {
        document.execCommand('copy');
      } catch(e) {}
      div.removeEventListener('copy', onCopy);

      try { sel.removeAllRanges(); } catch(e) {}
      document.body.removeChild(div);
      return ok;
    }

    // 1) Clipboard API with HTML + plain (best quality, secure contexts)
    try {
      if(navigator.clipboard && navigator.clipboard.write && window.ClipboardItem){
        var blobHtml = new Blob([h], {type: 'text/html'});
        var blobText = new Blob([t], {type: 'text/plain'});
        var item = new ClipboardItem({'text/html': blobHtml, 'text/plain': blobText});
        return navigator.clipboard.write([item]).then(function(){
          setFeedback('✅ Formatiert für Word kopiert.');
        }).catch(function(){
          // fall through
          if(copyHtmlExec()) setFeedback('✅ Formatiert für Word kopiert.');
          else if(navigator.clipboard && navigator.clipboard.writeText){
            navigator.clipboard.writeText(t).then(function(){
              setFeedback('✅ Als Text kopiert (Browser erlaubt kein formatiertes Kopieren).');
            }).catch(function(){
              setFeedback(copyPlainExec() ? '✅ Als Text kopiert (Fallback).' : '⚠️ Konnte nicht automatisch kopieren.');
            });
          } else {
            setFeedback(copyPlainExec() ? '✅ Als Text kopiert (Fallback).' : '⚠️ Konnte nicht automatisch kopieren.');
          }
        });
      }
    } catch(e) {}

    // 2) execCommand (works also on http / older browsers)
    try {
      if(copyHtmlExec()) { setFeedback('✅ Formatiert für Word kopiert.'); return; }
    } catch(e) {}

    // 3) Plain text fallback
    try {
      if(navigator.clipboard && navigator.clipboard.writeText){
        navigator.clipboard.writeText(t).then(function(){
          setFeedback('✅ Als Text kopiert (Browser erlaubt kein formatiertes Kopieren).');
        }).catch(function(){
          setFeedback(copyPlainExec() ? '✅ Als Text kopiert (Fallback).' : '⚠️ Konnte nicht automatisch kopieren.');
        });
        return;
      }
    } catch(e) {}

    setFeedback(copyPlainExec() ? '✅ Als Text kopiert (Fallback).' : '⚠️ Konnte nicht automatisch kopieren.');
  }

  // Gradio re-renders buttons; binding to the concrete <button> is brittle.
  // Use ONE delegated click handler (capture) that survives any re-render.
  function installCopyDelegation(){
    if(window.__rhkCopyDelegationInstalled) return;
    window.__rhkCopyDelegationInstalled = true;
    document.addEventListener('click', function(ev){
      try {
        var t0 = ev && ev.target;
        if(!t0 || !t0.closest) return;
        var isDoc = !!t0.closest('#btn_copy_doc');
        var isPat = !!t0.closest('#btn_copy_pat');
        var isRhk = !!t0.closest('#btn_copy_rhk');
        if(!(isDoc || isPat || isRhk)) return;
        ev.preventDefault();
        ev.stopPropagation();
        var htmlId = isDoc ? 'copy_doc_html' : (isPat ? 'copy_pat_html' : 'copy_rhk_html');
        var plainId = isDoc ? 'copy_doc_plain' : (isPat ? 'copy_pat_plain' : 'copy_rhk_plain');
        var h = getTextboxValue(htmlId);
        var p = getTextboxValue(plainId);
        copyToClipboard(h, p);
      } catch(e) {
        setFeedback('⚠️ Konnte nicht automatisch kopieren.');
      }
    }, true);
  }

  function enforceLight(){
    try {
      document.documentElement.style.colorScheme = 'light';
      if(document.body) document.body.style.colorScheme = 'light';
    } catch(e) {}
  }

  function boot(){
    enforceLight();
    installCopyDelegation();
  }

  // Gradio may re-render; bind on load and after short delays.
  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', function(){ boot(); setTimeout(boot, 500); setTimeout(boot, 1500); });
  } else {
    boot(); setTimeout(boot, 500); setTimeout(boot, 1500);
  }
})();
</script>
""",
    ]
)

CSS = ("""
/* ------------------------------------------------------------------
   Light UI (robust): enforce readability even if browser/system prefers dark
   ------------------------------------------------------------------ */

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

/* Top action buttons: keep the same conservative light style */
#btn_example_top button, #btn_example_bottom button,
#btn_clear_top button, #btn_clear_bottom button,
#btn_save_top button, #btn_save_bottom button,
#btn_load_top button, #btn_load_bottom button {
  background: #ffffff !important;
  color: #0f172a !important;
  border: 1px solid rgba(148, 163, 184, 0.9) !important;
  box-shadow: none !important;
}
#btn_example_top button:hover, #btn_example_bottom button:hover,
#btn_clear_top button:hover, #btn_clear_bottom button:hover,
#btn_save_top button:hover, #btn_save_bottom button:hover,
#btn_load_top button:hover, #btn_load_bottom button:hover {
  filter: brightness(0.98);
}

/* Copy buttons: match the same style (avoid heavy dark blocks) */
#btn_copy_doc button, #btn_copy_pat button, #btn_copy_rhk button {
  background: #ffffff !important;
  color: #0f172a !important;
  border: 1px solid rgba(148, 163, 184, 0.9) !important;
  box-shadow: none !important;
}
#btn_copy_doc button:hover, #btn_copy_pat button:hover, #btn_copy_rhk button:hover {
  filter: brightness(0.98);
}

/* Hidden clipboard payloads must remain in DOM for robust JS copy binding */
.rhk-hidden-payload{ display: none !important; }

:root,
.dark,
:root[data-theme="dark"], html[data-theme="dark"], body[data-theme="dark"],
:root[data-color-mode="dark"], html[data-color-mode="dark"], body[data-color-mode="dark"],
.gradio-container[data-theme="dark"], .gradio-container[data-color-mode="dark"] {
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

.gradio-container { max-width: 1700px !important; margin: 0 auto !important; padding-left: 8px; padding-right: 8px; }

/* Force light cards/panels even if Gradio or browser applies dark-ish block fills */
.gradio-container .gr-box,
.gradio-container .gr-block,
.gradio-container .panel,
.gradio-container .form,
.gradio-container .wrap {
  background: rgba(255,255,255,0.96) !important;
  color: #111111 !important;
}

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

/* ------------------------------------------------------------------
   Sticky Summary Bar (always visible, concise live preview)
   ------------------------------------------------------------------ */
#rhk_summarybar_wrapper{
  position: sticky;
  top: 118px;
  z-index: 10001;
  max-width: 1600px;
  margin: 0 auto 10px;
  padding: 0 24px;
}
#rhk_summarybar_wrapper .rhk-summarybar{
  display:flex;
  flex-wrap:wrap;
  align-items:center;
  gap:8px;
  padding:10px 12px;
  background: rgba(255,255,255,0.78);
  backdrop-filter: blur(14px) saturate(160%%);
  -webkit-backdrop-filter: blur(14px) saturate(160%%);
  border: 1px solid rgba(0,0,0,0.06);
  border-radius: 18px;
  box-shadow: 0 10px 26px rgba(0,0,0,0.08);
}
.rhk-summarybar .rhk-schip{
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 650;
  background: rgba(255,255,255,0.55);
  border: 1px solid rgba(0,0,0,0.06);
  color: rgba(15,23,42,0.8);
  white-space: nowrap;
}
.rhk-summarybar .rhk-schip--hint{
  white-space: normal;
  flex: 1 1 100%;
  line-height: 1.25;
}

.rhk-summarybar .rhk-schip--good{ background: rgba(20,184,166,0.12); border-color: rgba(20,184,166,0.22); color:#0f766e; }
.rhk-summarybar .rhk-schip--warn{ background: rgba(249,115,22,0.12); border-color: rgba(249,115,22,0.22); color:#c2410c; }
.rhk-summarybar .rhk-schip--bad{ background: rgba(239,68,68,0.12); border-color: rgba(239,68,68,0.22); color:#b91c1c; }
.rhk-summarybar .rhk-schip--info{ background: rgba(37,99,235,0.12); border-color: rgba(37,99,235,0.22); color:#1d4ed8; }


/* ------------------------------------------------------------------
   Scrollable report panes (Arztbericht/Patientenbericht/Intern/Debug)
   Hinweis: Sticky Summary bleibt außerhalb und sticky.
   ------------------------------------------------------------------ */
.rhk-scrollbox {
  max-height: 72vh;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 10px 12px;
  border: 1px solid rgba(0,0,0,0.06);
  border-radius: 14px;
  background: rgba(255,255,255,0.98);
}

/* Conservative typography & better line-length in previews */
.rhk-scrollbox .prose,
.rhk-scrollbox .markdown,
.rhk-scrollbox .wrap {
  max-width: 76ch;
  margin: 0 auto;
  line-height: 1.45;
  font-size: 14px;
}
.rhk-scrollbox h1, .rhk-scrollbox h2, .rhk-scrollbox h3 {
  letter-spacing: -0.01em;
}

/* Copy row */
#rhk_copy_row {
  gap: 8px !important;
  align-items: center;
  margin: 6px 0 8px;
}
.rhk-copy-feedback{
  font-size: 12px;
  color: rgba(15,23,42,0.7);
  margin-top: 4px;
}

/* Consistent form rhythm (spacing/align) */
/* ------------------------------------------------------------------
   Stabilität: keine flackernde/halb-transparente Schrift bei Updates
   (Gradio setzt bei Pending/Loading teils Opacity/Filter auf Container)
   ------------------------------------------------------------------ */
.gradio-container label, .gradio-container label *,
.gradio-container [data-testid="block-label"], .gradio-container [data-testid="block-label"] *,
.gradio-container .block-label, .gradio-container .block-label *,
.gradio-container .label, .gradio-container .label *,
.gradio-container .label-wrap, .gradio-container .label-wrap * {
  opacity: 1 !important;
  filter: none !important;
  -webkit-text-fill-color: currentColor !important;
  transition: none !important;
  animation: none !important;
}
.gradio-container [aria-busy="true"], .gradio-container [aria-busy="true"] * {
  opacity: 1 !important;
  filter: none !important;
}
.gradio-container .loading, .gradio-container .loading * {
  opacity: 1 !important;
  filter: none !important;
}
/* Disable opacity/color transitions on form text to avoid perceived flicker */
.gradio-container label,
.gradio-container .wrap,
.gradio-container .prose,
.gradio-container input,
.gradio-container textarea,
.gradio-container select {
  transition: none !important;
}

/* Gradio nutzt teils Skeleton-/Pulse-Animationen beim Ein-/Ausblenden von Blöcken.
   Das wirkt wie ein "Pulsieren" (sichtbar -> verblassen -> sichtbar) und ist störend.
   Wir deaktivieren diese Effekte konsequent für alle UI-Elemente. */
.gradio-container .animate-pulse,
.gradio-container .animate-pulse *,
.gradio-container [class*="animate-pulse"],
.gradio-container [class*="animate-pulse"] *,
.gradio-container [class*="pulse"],
.gradio-container [class*="pulse"] * {
  animation: none !important;
  opacity: 1 !important;
  filter: none !important;
}

.gradio-container .gr-row {
  gap: 12px !important;
}
.gradio-container label {
  line-height: 1.15;
}
.gradio-container input:not([type="checkbox"]):not([type="radio"]),
.gradio-container textarea,
.gradio-container select {
  min-height: 38px;
  border-radius: 12px !important;
}
.rhk-scrollbox pre,
.rhk-scrollbox code {
  white-space: pre-wrap;
  word-break: break-word;
}
#rhk_output_tabs {
  overflow: visible !important;
}


/* ------------------------------------------------------------------
   P-Module Cards (Auto/Manuell/Gesperrt) – visual layer
   ------------------------------------------------------------------ */
#pmods_cards .pmod-grid{
  display:grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 8px 0 16px;
}
@media (min-width: 1200px){
  #pmods_cards .pmod-grid{ grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
#pmods_cards .pmod-card{
  background: rgba(255,255,255,0.7);
  border: 1px solid rgba(0,0,0,0.08);
  border-radius: 16px;
  padding: 10px 12px;
  box-shadow: 0 8px 22px rgba(0,0,0,0.06);
  transition: transform .12s ease, box-shadow .12s ease;
}
#pmods_cards .pmod-card:hover{ transform: translateY(-1px); box-shadow: 0 12px 28px rgba(0,0,0,0.08); }
#pmods_cards .pmod-title{ font-weight: 800; font-size: 13px; color: #0f172a; margin-bottom: 4px; }
#pmods_cards .pmod-sub{ font-size: 12px; color: rgba(15,23,42,0.65); margin-bottom: 8px; }
#pmods_cards .pmod-meta{ display:flex; gap:6px; flex-wrap:wrap; }
#pmods_cards .pmod-chip{ padding: 4px 10px; border-radius: 999px; font-size: 11px; font-weight: 700; border: 1px solid rgba(0,0,0,0.08); background: rgba(255,255,255,0.55); color: rgba(15,23,42,0.75); }
#pmods_cards .pmod-chip--auto{ background: rgba(37,99,235,0.12); border-color: rgba(37,99,235,0.22); color:#1d4ed8; }
#pmods_cards .pmod-chip--manual{ background: rgba(168,85,247,0.12); border-color: rgba(168,85,247,0.22); color:#6d28d9; }
#pmods_cards .pmod-chip--locked{ background: rgba(107,114,128,0.14); border-color: rgba(107,114,128,0.25); color:#374151; }
#pmods_cards .pmod-chip--lvl1{ background: rgba(20,184,166,0.12); border-color: rgba(20,184,166,0.22); color:#0f766e; }
#pmods_cards .pmod-chip--lvl2{ background: rgba(249,115,22,0.12); border-color: rgba(249,115,22,0.22); color:#c2410c; }
#pmods_cards .pmod-chip--lvl3{ background: rgba(148,163,184,0.16); border-color: rgba(148,163,184,0.28); color:#334155; }


/* ------------------------------------------------------------------
   Auffälliger Accordion-Header für Modulauswahl
   ------------------------------------------------------------------ */
#pmods_accordion summary, 
#pmods_accordion .label-wrap, 
#pmods_accordion button {
  background: linear-gradient(90deg, rgba(37,99,235,0.10), rgba(168,85,247,0.06)) !important;
  border: 1px solid rgba(37,99,235,0.22) !important;
  border-radius: 16px !important;
  padding: 10px 12px !important;
  font-weight: 900 !important;
  box-shadow: 0 10px 24px rgba(0,0,0,0.06) !important;
}
#pmods_accordion summary:hover,
#pmods_accordion button:hover{
  background: linear-gradient(90deg, rgba(37,99,235,0.14), rgba(168,85,247,0.08)) !important;
}
#pmods_accordion summary::after{
  content: "  (klicken)";
  font-weight: 700;
  opacity: 0.7;
}

/* ------------------------------------------------------------------
   Vergleichsübersicht Vorher/Nachher
   ------------------------------------------------------------------ */
#rhk_compare_overview .cmp-wrap{
  margin-top: 10px;
  margin-bottom: 16px;
  background: rgba(255,255,255,0.72);
  border: 1px solid rgba(0,0,0,0.08);
  border-radius: 18px;
  padding: 12px 12px;
  box-shadow: 0 10px 26px rgba(0,0,0,0.06);
}
#rhk_compare_overview .cmp-head{ display:flex; gap:10px; flex-wrap:wrap; align-items:center; margin-bottom: 8px; }
#rhk_compare_overview .cmp-title{ font-weight: 900; font-size: 13px; color:#0f172a; }
#rhk_compare_overview .cmp-note{ font-size: 12px; color: rgba(15,23,42,0.6); }
#rhk_compare_overview .cmp-date{ font-size: 11px; font-weight: 700; opacity: 0.75; }
#rhk_compare_overview table{ width:100%%; border-collapse: separate; border-spacing: 0; overflow:hidden; border-radius: 14px; }
#rhk_compare_overview th, #rhk_compare_overview td{ padding: 8px 10px; font-size: 12px; border-bottom: 1px solid rgba(0,0,0,0.06); }
#rhk_compare_overview th{ text-align:left; background: rgba(255,255,255,0.65); font-weight: 800; color: rgba(15,23,42,0.75); }
#rhk_compare_overview tr:last-child td{ border-bottom: none; }
#rhk_compare_overview .cmp-delta-up{ color:#b91c1c; font-weight: 800; }
#rhk_compare_overview .cmp-delta-down{ color:#0f766e; font-weight: 800; }
#rhk_compare_overview .cmp-delta-flat{ color:#334155; font-weight: 800; }

/* ------------------------------------------------------------------
   DOCX Import Status
   ------------------------------------------------------------------ */
.docx-status{display:flex;flex-direction:column;gap:10px;margin:8px 0 12px 0}
.docx-box{border:1px solid rgba(0,0,0,.10);border-radius:14px;padding:10px 12px;background:#fff}
.docx-box.warn{border-color:rgba(220,70,70,.35);background:rgba(220,70,70,.04)}
.docx-title{font-weight:900;margin:0 0 6px 0}
.docx-row{display:flex;flex-wrap:wrap;gap:8px}
.chip{display:inline-flex;gap:6px;align-items:center;padding:5px 10px;border-radius:999px;border:1px solid rgba(0,0,0,.10);background:rgba(0,0,0,.02);font-size:12px}
.chip-lab{color:rgba(0,0,0,.60);font-weight:800}
.small{margin-top:6px;color:rgba(0,0,0,.70);font-size:12px;line-height:1.35}

.docx-muted{margin-top:6px;color:rgba(0,0,0,.62);font-size:12px;line-height:1.35}
.docx-details{margin-top:8px}
.docx-details summary{cursor:pointer;font-weight:900;color:#0f172a;margin:6px 0}
.docx-list{margin:6px 0 0 18px;color:rgba(0,0,0,.72);font-size:12px;line-height:1.35}
.rhk-tbl{width:100%;border-collapse:separate;border-spacing:0;overflow:hidden;border-radius:12px;border:1px solid rgba(0,0,0,.08);margin-top:8px}
.rhk-tbl th,.rhk-tbl td{padding:6px 8px;font-size:12px;border-bottom:1px solid rgba(0,0,0,.06);vertical-align:top}
.rhk-tbl th{text-align:left;background:rgba(0,0,0,.03);font-weight:900;color:rgba(15,23,42,.8)}
.rhk-tbl tr:last-child td{border-bottom:none}
/* ------------------------------------------------------------------
   RHK Viz Grid
   ------------------------------------------------------------------ */
.rhk-viz-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
@media (max-width: 1200px){.rhk-viz-grid{grid-template-columns:1fr}}
.rhk-viz-item{width:100%}

""".strip())

# Avoid %-formatting pitfalls (Gradio/CSS contains many % characters).
CSS = CSS.replace("__DESKTOP_VIEWPORT_WIDTH_PX__", str(DESKTOP_VIEWPORT_WIDTH_PX)).replace("%%", "%")

JS_ON_LOAD = r"""
() => {
  // Force light mode (this app is styled for light mode)
  // Important: keep this idempotent to avoid flicker during reactive UI updates.
  const isDarkNow = () => {
    try {
      const de = document.documentElement;
      const bd = document.body;
      const htmlTheme = (de.getAttribute('data-theme') || '').toLowerCase();
      const bodyTheme = (bd && (bd.getAttribute('data-theme') || '').toLowerCase()) || '';
      const darkClass = de.classList.contains('dark') || (bd && bd.classList && bd.classList.contains('dark'));
      return darkClass || htmlTheme === 'dark' || bodyTheme === 'dark';
    } catch (e) { return false; }
  };

  const applyLight = () => {
    try {
      const de = document.documentElement;
      const bd = document.body;
      const needs = isDarkNow() || de.style.colorScheme !== 'light' || (bd && bd.style && bd.style.colorScheme !== 'light');
      if (!needs) return;
      try { de.classList.remove('dark'); } catch (e) {}
      try { if (bd && bd.classList) bd.classList.remove('dark'); } catch (e) {}
      // Some Gradio builds use attributes / data-theme instead of a class
      try { de.setAttribute('data-theme','light'); } catch (e) {}
      try { if (bd) bd.setAttribute('data-theme','light'); } catch (e) {}
      de.style.colorScheme = 'light';
      if (bd && bd.style) bd.style.colorScheme = 'light';
    } catch (e) {}
  };

  // Best-effort: prevent persistence of dark preference (once)
  try {
    localStorage.setItem('theme', 'light');
    localStorage.setItem('gradio_theme', 'light');
    localStorage.setItem('gradio-theme', 'light');
  } catch (e) {}

  // Throttled re-apply if the framework toggles theme during reactive updates
  let __rhk_light_ts = 0;
  const applyLightIfDark = () => {
    try {
      const now = Date.now();
      if (now - __rhk_light_ts < 120) return;
      __rhk_light_ts = now;
      if (isDarkNow()) applyLight();
    } catch (e) {}
  };

  // Ensure nothing is collapsed into a "More/…" overflow menu.
  // Users must always see all tabs and all P-Module options deterministically.
  // Keep "More/…" overflow controls out of the UI.
  // IMPORTANT: must be lightweight; avoid full-document scans.
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

      // Hide any overflow "More/Mehr" controls created by Gradio, but only inside relevant containers.
      const roots = document.querySelectorAll(
        '#rhk_input_tabs, #rhk_output_tabs, #pmods_choice_lvl1, #pmods_choice_lvl2, #pmods_choice_lvl3'
      );
      roots.forEach((root) => {
        try {
          root.querySelectorAll('button, div, span').forEach((el) => {
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
          });
        } catch (e) {}
      });

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
    const obs = new MutationObserver(() => { applyLightIfDark(); });
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['class', 'data-theme'] });
    obs.observe(document.body, { attributes: true, attributeFilter: ['class', 'data-theme'] });
  } catch (e) {}

  // Debounced "dirty" ping -> server updates status badges once per burst.
  const debounce = (fn, wait) => {
    let t;
    return (...args) => {
      try { clearTimeout(t); } catch (e) {}
      t = setTimeout(() => fn(...args), wait);
    };
  };

  const setupDirtyPing = () => {
    try {
      if (window.__rhk_dirty_setup) return;
      window.__rhk_dirty_setup = true;

      const getPingEl = () => document.querySelector('#rhk_dirty_ping textarea, #rhk_dirty_ping input');

      const bumpPing = debounce(() => {
        try {
          const el = getPingEl();
          if (!el) return;
          el.value = String(Date.now());
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
        } catch (e) {}
      }, 220);

      const shouldIgnore = (target) => {
        try {
          if (!target || !target.closest) return true;
          if (target.closest('#rhk_dirty_ping')) return true;
          // Procedere/Module have their own live-update path (do not mark report stale).
          if (target.closest('#pmods_choice_lvl1, #pmods_choice_lvl2, #pmods_choice_lvl3')) return true;
          if (target.closest('#procedere_free')) return true;
          return false;
        } catch (e) {
          return true;
        }
      };

      const onAnyEdit = (ev) => {
        try {
          if (window.__rhk_bulk_until && Date.now() < window.__rhk_bulk_until) return;
          const t = ev ? ev.target : null;
          if (shouldIgnore(t)) return;
          bumpPing();
        } catch (e) {}
      };

      document.addEventListener('input', onAnyEdit, true);
      document.addEventListener('change', onAnyEdit, true);

      const armBulk = () => { window.__rhk_bulk_until = Date.now() + 1400; };
      [
        'btn_example_top','btn_example_bottom','btn_clear_top','btn_clear_bottom',
        'btn_generate_top','btn_generate_bottom','btn_save_top','btn_save_bottom',
        'btn_load_top','btn_load_bottom'
      ].forEach((id) => {
        const node = document.getElementById(id);
        if (!node) return;
        try { node.addEventListener('click', armBulk, true); } catch (e) {}
      });
    } catch (e) {}
  };

  update();
  setupDirtyPing();
  setTimeout(update, 50);
  setTimeout(update, 250);
  window.addEventListener("resize", () => setTimeout(update, 50));
}
"""
JS_ON_LOAD = JS_ON_LOAD.replace("__DESKTOP_ONLY__", "true" if DESKTOP_ONLY else "false")
JS_ON_LOAD = JS_ON_LOAD.replace("__MIN_WIDTH__", str(DESKTOP_MIN_WIDTH_PX)).strip()


# -----------------------------------------------------------------------------
# Light-mode enforcement + Word-friendly clipboard copy (robust, cross-browser)
#
# Why this exists:
# - Some deployments (esp. Gradio 6+ / SSR / CDN caches) may ignore Blocks-level
#   `head` injection, and some browsers default to dark mode.
# - The app must remain readable and the copy buttons must work in Edge/Opera.
#
# We therefore run the enforcement & copy handler BOTH via `head` (best, earliest)
# and via `js` (fallback, survives head being ignored).
# -----------------------------------------------------------------------------

JS_LIGHT_COPY_FALLBACK = r"""
(function(){
  // --- 1) Always prefer Gradio light theme ---------------------------------
  // If the param is missing, some browsers/system themes will render dark.
  // We enforce a single redirect to add `__theme=light`.
  try {
    var u = new URL(window.location.href);
    var th = u.searchParams.get('__theme');
    if (th !== 'light') {
      u.searchParams.set('__theme', 'light');
      window.location.replace(u.toString());
      return;
    }
  } catch(e) {}

  function byId(id){ return document.getElementById(id); }

  function setFeedback(msg){
    try {
      var root = byId('rhk_copy_feedback');
      if(!root) return;
      var tgt = root.querySelector('.prose, .markdown, .md, .wrap, div') || root;
      tgt.textContent = msg;
    } catch(e) {}
  }

  function getTextboxValue(rootId){
    var root = byId(rootId);
    if(!root) return "";
    var el = root.querySelector('textarea,input');
    if(el && typeof el.value === 'string') return el.value;
    return (root.textContent || '').trim();
  }

  function extractFragment(html){
    if(!html) return "";
    var s = '<!--StartFragment-->';
    var e = '<!--EndFragment-->';
    var i = html.indexOf(s);
    var j = html.indexOf(e);
    if(i >= 0 && j > i) return html.substring(i + s.length, j).trim();
    var m = html.match(/<body[^>]*>([\\s\\S]*?)<\/body>/i);
    if(m && m[1]) return m[1].trim();
    return String(html);
  }

  function showManualCopy(text){
    try {
      var overlay = document.createElement('div');
      overlay.style.position = 'fixed';
      overlay.style.inset = '0';
      overlay.style.background = 'rgba(15, 23, 42, 0.35)';
      overlay.style.zIndex = '999999';
      overlay.style.display = 'flex';
      overlay.style.alignItems = 'center';
      overlay.style.justifyContent = 'center';

      var box = document.createElement('div');
      box.style.width = 'min(860px, 92vw)';
      box.style.maxHeight = '80vh';
      box.style.background = '#ffffff';
      box.style.border = '1px solid rgba(0,0,0,0.18)';
      box.style.borderRadius = '12px';
      box.style.boxShadow = '0 10px 30px rgba(0,0,0,0.20)';
      box.style.padding = '14px';
      box.style.display = 'flex';
      box.style.flexDirection = 'column';
      box.style.gap = '10px';

      var header = document.createElement('div');
      header.style.display = 'flex';
      header.style.alignItems = 'center';
      header.style.justifyContent = 'space-between';

      var title = document.createElement('div');
      title.textContent = 'Manuell kopieren';
      title.style.fontWeight = '600';
      title.style.color = '#0f172a';

      var close = document.createElement('button');
      close.textContent = '✕';
      close.style.border = 'none';
      close.style.background = 'transparent';
      close.style.cursor = 'pointer';
      close.style.fontSize = '18px';
      close.style.lineHeight = '18px';
      close.style.color = '#0f172a';

      header.appendChild(title);
      header.appendChild(close);

      var hint = document.createElement('div');
      hint.textContent = 'Browser blockiert automatisches Kopieren. Text ist markiert: bitte Strg+C und dann in Word einfügen.';
      hint.style.fontSize = '13px';
      hint.style.color = 'rgba(15, 23, 42, 0.75)';

      var ta = document.createElement('textarea');
      ta.value = String(text || '');
      ta.style.width = '100%';
      ta.style.height = '55vh';
      ta.style.resize = 'none';
      ta.style.border = '1px solid rgba(0,0,0,0.18)';
      ta.style.borderRadius = '10px';
      ta.style.padding = '10px';
      ta.style.fontFamily = 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace';
      ta.style.fontSize = '12px';
      ta.style.color = '#0f172a';
      ta.style.background = '#ffffff';

      box.appendChild(header);
      box.appendChild(hint);
      box.appendChild(ta);
      overlay.appendChild(box);
      document.body.appendChild(overlay);

      function cleanup(){
        try { document.body.removeChild(overlay); } catch(e) {}
      }
      overlay.addEventListener('click', function(ev){
        if(ev && ev.target === overlay) cleanup();
      });
      close.addEventListener('click', function(){ cleanup(); });

      setTimeout(function(){
        try { ta.focus(); ta.select(); } catch(e) {}
      }, 0);
    } catch(e) {}
  }

  function copyToClipboard(html, plain){
    var rawHtml = (html === undefined || html === null) ? '' : String(html);
    var frag = extractFragment(rawHtml);
    var t = (plain === undefined || plain === null) ? '' : String(plain);

    function copyPlainExec(){
      var ta = document.createElement('textarea');
      ta.value = t;
      ta.style.position = 'fixed';
      ta.style.left = '-9999px';
      ta.style.top = '0';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      var ok = false;
      try { ok = document.execCommand('copy'); } catch(e) {}
      document.body.removeChild(ta);
      return ok;
    }

    function copyHtmlExec(){
      var div = document.createElement('div');
      var safeText = t
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\n/g, '<br>');
      div.innerHTML = (frag && frag.trim().length) ? frag : safeText;
      div.style.position = 'fixed';
      div.style.left = '0';
      div.style.top = '0';
      div.style.opacity = '0';
      div.style.width = '1px';
      div.style.height = '1px';
      div.style.overflow = 'hidden';
      div.setAttribute('contenteditable', 'true');
      document.body.appendChild(div);

      var ok = false;
      var sel = window.getSelection();
      try {
        div.focus();
        var range = document.createRange();
        range.selectNodeContents(div);
        sel.removeAllRanges();
        sel.addRange(range);
      } catch(e) {}

      function onCopy(e){
        try {
          if(e && e.clipboardData){
            e.clipboardData.setData('text/html', (frag && frag.trim().length) ? frag : safeText);
            e.clipboardData.setData('text/plain', t);
            e.preventDefault();
            ok = true;
          }
        } catch(err) {}
      }
      div.addEventListener('copy', onCopy);
      try { document.execCommand('copy'); } catch(e) {}
      div.removeEventListener('copy', onCopy);

      try { sel.removeAllRanges(); } catch(e) {}
      try { document.body.removeChild(div); } catch(e) {}
      return ok;
    }

    // 1) Clipboard API (best)
    try {
      if(navigator.clipboard && navigator.clipboard.write && window.ClipboardItem){
        var blobHtml = new Blob([frag], {type: 'text/html'});
        var blobText = new Blob([t], {type: 'text/plain'});
        var item = new ClipboardItem({'text/html': blobHtml, 'text/plain': blobText});
        navigator.clipboard.write([item]).then(function(){
          setFeedback('✅ Formatiert für Word kopiert.');
        }).catch(function(){
          if(copyHtmlExec()) setFeedback('✅ Formatiert für Word kopiert.');
          else if(copyPlainExec()) setFeedback('✅ Als Text kopiert (Fallback).');
          else { setFeedback('⚠️ Kopieren blockiert.'); showManualCopy(t); }
        });
        return;
      }
    } catch(e) {}

    // 2) execCommand
    try {
      if(copyHtmlExec()) { setFeedback('✅ Formatiert für Word kopiert.'); return; }
    } catch(e) {}

    // 3) Plain fallback
    if(copyPlainExec()) { setFeedback('✅ Als Text kopiert (Fallback).'); return; }

    setFeedback('⚠️ Kopieren blockiert.');
    showManualCopy(t);
  }

  function installCopyDelegation(){
    if(window.__rhkCopyDelegationInstalled) return;
    window.__rhkCopyDelegationInstalled = true;
    document.addEventListener('click', function(ev){
      try {
        var t0 = ev && ev.target;
        if(!t0 || !t0.closest) return;
        var isDoc = !!t0.closest('#btn_copy_doc');
        var isPat = !!t0.closest('#btn_copy_pat');
        var isRhk = !!t0.closest('#btn_copy_rhk');
        if(!(isDoc || isPat || isRhk)) return;
        ev.preventDefault();
        ev.stopPropagation();
        var htmlId = isDoc ? 'copy_doc_html' : (isPat ? 'copy_pat_html' : 'copy_rhk_html');
        var plainId = isDoc ? 'copy_doc_plain' : (isPat ? 'copy_pat_plain' : 'copy_rhk_plain');
        var h = getTextboxValue(htmlId);
        var p = getTextboxValue(plainId);
        copyToClipboard(h, p);
      } catch(e) {
        setFeedback('⚠️ Konnte nicht automatisch kopieren.');
      }
    }, true);
  }

  function enforceLight(){
    try {
      document.documentElement.style.colorScheme = 'light';
      document.documentElement.setAttribute('data-theme', 'light');
      document.documentElement.setAttribute('data-color-mode', 'light');
      if(document.body){
        document.body.style.colorScheme = 'light';
        document.body.classList.remove('dark');
      }
    } catch(e) {}
  }

  function boot(){
    enforceLight();
    installCopyDelegation();
  }

  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', function(){ boot(); setTimeout(boot, 400); setTimeout(boot, 1200); });
  } else {
    boot(); setTimeout(boot, 400); setTimeout(boot, 1200);
  }
})();
"""

# Append fallback JS so the critical behaviour survives environments
# where only the `js` hook executes reliably.
JS_ON_LOAD = (JS_ON_LOAD + "\n" + JS_LIGHT_COPY_FALLBACK).strip()


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


def _fmt_or_dash(v: Any, nd: int = 0) -> str:
    try:
        if v is None or v == "":
            return "–"
        fv = float(v)
        if nd <= 0:
            return f"{fv:.0f}"
        return f"{fv:.{nd}f}"
    except Exception:
        return "–"


def load_rulebook_meta(path: str) -> Dict[str, Any]:
    """Read meta info (version/updated) from YAML rulebook without changing rule loading."""
    try:
        if not path or not os.path.exists(path):
            return {}
        if yaml is None:
            return {}
        with open(path, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
        meta = doc.get("meta") if isinstance(doc, dict) else {}
        return meta if isinstance(meta, dict) else {}
    except Exception:
        return {}


def html_escape(s: Any) -> str:
    """HTML-escape helper (quote-safe)."""
    try:
        return _html.escape(str(s), quote=True)
    except Exception:
        return ""



def build_sticky_summary_html(case: Optional[Dict[str, Any]], flags: Optional[Dict[str, Any]] = None) -> str:
    """Concise, always-visible live preview of key values."""
    if not case:
        status = ""
        if flags:
            # Minimal status even without case
            dirty = bool(flags.get("dirty"))
            saved_at = flags.get("saved_at")
            has_report = bool(flags.get("has_report"))
            stale = bool(flags.get("report_stale"))
            if has_report:
                status += "<span class='rhk-schip rhk-schip--warn'>Befund veraltet</span>" if stale else "<span class='rhk-schip rhk-schip--good'>Befund aktuell</span>"
            if dirty:
                status += "<span class='rhk-schip rhk-schip--warn'>Änderungen nicht gespeichert</span>"
            elif saved_at:
                status += "<span class='rhk-schip rhk-schip--good'>Gespeichert</span>"
        return (
            "<div class='rhk-summarybar'>"
            "<span class='rhk-schip rhk-schip--info'>Hämodynamik: –</span>"
            "<span class='rhk-schip'>RAP: –</span>"
            "<span class='rhk-schip'>mPAP: –</span>"
            "<span class='rhk-schip'>PAWP: –</span>"
            "<span class='rhk-schip'>PVR: –</span>"
            "<span class='rhk-schip'>CI: –</span>"
            "<span class='rhk-schip rhk-schip--warn'>Risiko: –</span>"
            f"{status}"
            "</div>"
        )

    ui = case.get("ui") or {}
    der = case.get("derived") or {}
    scores = case.get("scores") or {}

    # Warnungen (nicht blockierend)
    warns = case.get("warnings") or []
    wcnt = len(warns) if isinstance(warns, list) else 0
    wtone = "warn"
    if wcnt:
        try:
            sev = {str(w.get("severity")) for w in warns if isinstance(w, dict)}
            wtone = "bad" if "error" in sev else "warn"
        except Exception:
            wtone = "warn"
    wchip = ""
    if wcnt:
        # Tooltip with full warning list
        w_msgs = []
        try:
            for w in warns:
                if isinstance(w, dict) and str(w.get("message") or "").strip():
                    w_msgs.append(str(w.get("message")).strip())
        except Exception:
            w_msgs = []
        tooltip = "\n".join([f"- {m}" for m in w_msgs]) if w_msgs else ""
        tattr = f" title='{html_escape(tooltip)}'" if tooltip else ""
        wchip = f"<span class='rhk-schip rhk-schip--{wtone}'{tattr}>Warnungen: {wcnt}</span>"

    hemo_cat = str(der.get("hemo_category") or "unknown")
    hemo_map = {
        "precap": "präkapillär",
        "ipcph": "iPcPH",
        "cpcph": "cPcPH",
        "no_ph": "keine PH",
        "unknown": "unklar",
    }
    hemo_txt = hemo_map.get(hemo_cat, hemo_cat)

    mpap = der.get("mpap_rest")
    pawp = der.get("pawp_rest")
    rap = der.get("rap_rest")
    pvr = der.get("pvr_rest")
    ci = der.get("ci_rest")

    # Risk badge: prioritize ESC/ERS 4-strata if present, else REVEAL Lite 2
    esc4 = scores.get("esc_ers_4s")
    rl2 = scores.get("reveal_lite2")
    risk_txt = "–"
    risk_tone = "warn"
    if isinstance(esc4, str) and esc4:
        risk_txt = f"ESC/ERS 4-Strata: {esc4}"
        risk_tone = "good" if esc4 == "low" else ("bad" if esc4 == "high" else "warn")
    elif isinstance(rl2, str) and rl2:
        risk_txt = f"REVEAL Lite 2: {rl2}"
        _l = rl2.strip().lower()
        risk_tone = "good" if _l.startswith("nied") else ("bad" if _l.startswith("hoch") else "warn")

    # Optional compare hint
    prev_mpap = ui.get("prev_mpap")
    prev_pvr = ui.get("prev_pvr")
    cmp_hint = ""
    try:
        if prev_mpap not in (None, "") and mpap not in (None, ""):
            d = float(mpap) - float(prev_mpap)
            arrow = "↑" if d > 1 else ("↓" if d < -1 else "±")
            cmp_hint = f"<span class='rhk-schip rhk-schip--info'>ΔmPAP: {arrow} {d:+.0f}</span>"
        elif prev_pvr not in (None, "") and pvr not in (None, ""):
            d = float(pvr) - float(prev_pvr)
            arrow = "↑" if d > 0.5 else ("↓" if d < -0.5 else "±")
            cmp_hint = f"<span class='rhk-schip rhk-schip--info'>ΔPVR: {arrow} {d:+.1f}</span>"
    except Exception:
        cmp_hint = ""

    # Status chips (saved/dirty/stale)
    status_chips = ""
    if flags:
        try:
            has_report = bool(flags.get("has_report"))
            stale = bool(flags.get("report_stale"))
            dirty = bool(flags.get("dirty"))
            saved_at = flags.get("saved_at")

            if has_report:
                status_chips += "<span class='rhk-schip rhk-schip--warn'>Befund veraltet</span>" if stale else "<span class='rhk-schip rhk-schip--good'>Befund aktuell</span>"
            if dirty:
                status_chips += "<span class='rhk-schip rhk-schip--warn'>Änderungen nicht gespeichert</span>"
            elif saved_at:
                status_chips += "<span class='rhk-schip rhk-schip--good'>Gespeichert</span>"
        except Exception:
            status_chips = ""

    return (
        "<div class='rhk-summarybar'>"
        f"<span class='rhk-schip rhk-schip--info'>Hämodynamik: {html_escape(hemo_txt)}</span>"
        f"<span class='rhk-schip'>RAP: {_fmt_or_dash(rap,0)}</span>"
        f"<span class='rhk-schip'>mPAP: {_fmt_or_dash(mpap,0)}</span>"
        f"<span class='rhk-schip'>PAWP: {_fmt_or_dash(pawp,0)}</span>"
        f"<span class='rhk-schip'>PVR: {_fmt_or_dash(pvr,1)}</span>"
        f"<span class='rhk-schip'>CI: {_fmt_or_dash(ci,2)}</span>"
        f"<span class='rhk-schip rhk-schip--{risk_tone}'>Risiko: {html_escape(risk_txt)}</span>"
        f"{wchip}"
        f"{cmp_hint}"
        f"{status_chips}"
        "</div>"
    )


def build_compare_overview_html(case: Optional[Dict[str, Any]]) -> str:
    if not case:
        return ""
    ui = case.get("ui") or {}
    der = case.get("derived") or {}

    rows = [
        ("RAP (mmHg)", ui.get("prev_rap"), der.get("rap_rest"), 0, 1.0),
        ("mPAP (mmHg)", ui.get("prev_mpap"), der.get("mpap_rest"), 0, 1.0),
        ("PAWP (mmHg)", ui.get("prev_pawp"), der.get("pawp_rest"), 0, 1.0),
        ("CI (l/min/m²)", ui.get("prev_ci"), der.get("ci_rest"), 2, 0.15),
        ("PVR (WU)", ui.get("prev_pvr"), der.get("pvr_rest"), 1, 0.5),
    ]

    def _delta_cell(prev, cur, nd, thr):
        try:
            if prev in (None, "") or cur in (None, ""):
                return "<span class='cmp-delta-flat'>–</span>"
            d = float(cur) - float(prev)
            if d > thr:
                cls = "cmp-delta-up"
                arrow = "↑"
            elif d < -thr:
                cls = "cmp-delta-down"
                arrow = "↓"
            else:
                cls = "cmp-delta-flat"
                arrow = "±"
            fmt = f"{{:{'+.'}{nd}f}}" if nd > 0 else "{:+.0f}"
            val = fmt.format(d)
            return f"<span class='{cls}'>{arrow} {val}</span>"
        except Exception:
            return "<span class='cmp-delta-flat'>–</span>"

    any_prev = any((p not in (None, "") for (_n, p, _c, _nd, _thr) in rows))
    if not any_prev:
        return ""

    prev_date = str(ui.get("prev_rhk_date") or "").strip()
    cur_date = str(ui.get("rhk_date") or "").strip()
    note = "Vorher/Nachher basierend auf Vor-RHK Feldern und aktuellen Ruhewerten."
    if prev_date and cur_date:
        note = f"Zeitraum: {html_escape(prev_date)} → {html_escape(cur_date)}. {note}"
    elif prev_date:
        note = f"Referenz: Vor-RHK {html_escape(prev_date)}. {note}"
    elif cur_date:
        note = f"Aktueller RHK: {html_escape(cur_date)}. {note}"

    tr = []
    for name, prev, cur, nd, thr in rows:
        tr.append(
            "<tr>"
            f"<td>{html_escape(name)}</td>"
            f"<td>{_fmt_or_dash(prev,nd)}</td>"
            f"<td>{_fmt_or_dash(cur,nd)}</td>"
            f"<td>{_delta_cell(prev,cur,nd,thr)}</td>"
            "</tr>"
        )

    return (
        "<div class='cmp-wrap'>"
        "<div class='cmp-head'>"
        "<div class='cmp-title'>Vergleich Vorher vs Jetzt</div>"
        f"<div class='cmp-note'>{note}</div>"
        "</div>"
        "<table>"
        "<thead><tr>""<th>Parameter</th>" + (f"<th>Vorher<br><span class='cmp-date'>{html_escape(prev_date)}</span></th>" if prev_date else "<th>Vorher</th>") + (f"<th>Jetzt<br><span class='cmp-date'>{html_escape(cur_date)}</span></th>" if cur_date else "<th>Jetzt</th>") + "<th>Δ</th></tr></thead>"
        f"<tbody>{''.join(tr)}</tbody>"
        "</table>"
        "</div>"
    )




def build_docx_status_html(docx_cur: dict | None, docx_prev: dict | None) -> str:
    def _phases(payload: dict | None) -> str:
        if not payload:
            return ""
        ph = payload.get("phases") or {}
        order = ["base1", "base2", "exercise", "post", "no", "o2"]
        seen = [p for p in order if p in ph]
        for k in ph.keys():
            if k not in seen:
                seen.append(k)
        name = {
            "base1": "Base 1",
            "base2": "Base 2",
            "exercise": "Ergometrie",
            "post": "Post Intervention",
            "no": "NO",
            "o2": "O2",
        }
        return ", ".join([name.get(k, k) for k in seen]) if seen else ""

    def _date(payload: dict | None) -> str:
        try:
            return (payload or {}).get("patient", {}).get("exam_date") or ""
        except Exception:
            return ""

    def _quality(payload: dict | None) -> tuple[str, str]:
        q = (payload or {}).get("quality") or {}
        return (q.get("status") or "", "; ".join(q.get("reasons") or []))

    cur_ph = _phases(docx_cur)
    prev_ph = _phases(docx_prev)
    cur_date = _date(docx_cur)
    prev_date = _date(docx_prev)

    cur_status, cur_reasons = _quality(docx_cur)
    prev_status, prev_reasons = _quality(docx_prev)

    def chip(label: str, value: str) -> str:
        if not value:
            return ""
        return f"<span class='chip'><span class='chip-lab'>{_html.escape(label)}</span> {_html.escape(value)}</span>"

    def block(title: str, date: str, ph: str, status: str, reasons: str) -> str:
        if not (date or ph or status or reasons):
            return ""
        warn = " warn" if status and status not in ("ok", "green") else ""
        rs = f"<div class='small'>{_html.escape(reasons)}</div>" if reasons else ""
        return (
            f"<div class='docx-box{warn}'>"
            f"<div class='docx-title'>{_html.escape(title)}</div>"
            f"<div class='docx-row'>"
            f"{chip('Datum', date)}{chip('Phasen', ph)}{chip('Qualität', status)}"
            f"</div>"
            f"{rs}"
            f"</div>"
        )

    html = (
        "<div class='docx-status'>"
        + block("Aktueller RHK Import", cur_date, cur_ph, cur_status, cur_reasons)
        + block("Vor-RHK Import", prev_date, prev_ph, prev_status, prev_reasons)
        + "</div>"
    )

    # Tabellenübersicht: immer direkt sichtbar (kompakt), damit nichts "versteckt" ist.
    # Die Risikoklassen-Tabelle aus dem Dokument wird in der Übersicht bewusst ausgeblendet.
    try:
        tables_html = build_docx_tables_overview_html(docx_cur, docx_prev)
    except Exception:
        tables_html = ""
    if tables_html:
        html += (
            "<div class='docx-muted'>Hinweis: Die Risikoklassen-Tabelle aus dem Dokument wird absichtlich ausgeblendet.</div>"
            + tables_html
        )

    return "" if "docx-box" not in html else html




def build_docx_tables_overview_html(docx_cur: dict | None, docx_prev: dict | None) -> str:
    """Compact, source-of-truth overview (tables only, no narrative).

    Shows what was extracted from DOCX so nothing is "hidden" in the UI. The
    risk-class table (if present) is intentionally skipped.
    """

    import re

    def fmt(x: object) -> str:
        if x is None:
            return ""
        try:
            # keep readable; MacLab often has 1-2 decimals
            if isinstance(x, float):
                return f"{x:.2f}".rstrip("0").rstrip(".")
            if isinstance(x, int):
                return str(x)
            # numeric strings
            sx = str(x)
            return sx
        except Exception:
            return ""

    def mk_table(headers: list[str], rows: list[list[object]], *, cls: str = "rhk-tbl") -> str:
        th = "".join([f"<th>{_html.escape(h)}</th>" for h in headers])
        body_rows = []
        for r in rows:
            tds = "".join([f"<td>{_html.escape(fmt(c))}</td>" for c in r])
            body_rows.append(f"<tr>{tds}</tr>")
        tbody = "".join(body_rows)
        return f"<table class='{cls}'><thead><tr>{th}</tr></thead><tbody>{tbody}</tbody></table>"

    def get_nested(d: dict, path: list[str]):
        cur = d
        for p in path:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(p)
        return cur

    def render(payload: dict, label: str) -> str:
        phases = (payload or {}).get("phases") or {}
        if not phases:
            return ""

        # Spaltenreihenfolge wie im klinischen Denken:
        # Base 1 -> Base 2 -> Ergometrie bzw. Intervention
        order = ["base1", "base2", "exercise", "post"]
        keys = [k for k in order if k in phases]
        if not keys:
            keys = list(phases.keys())

        name_map = {
            "base1": "Base 1",
            "base2": "Base 2",
            "exercise": "Ergometrie",
            "post": "Intervention",
        }
        cols = [name_map.get(k, k) for k in keys]

        def p(ph: str, *path: str):
            return get_nested(phases.get(ph) or {}, list(path))

        rows_core: list[list[object]] = []
        def add_row(name: str, vals: list[object]):
            rows_core.append([name] + vals)


        # Pressures (aus der Druckzusammenfassung, ohne Fließtext-Inferenz)
        add_row("RAP A/V/mean [mmHg]", [
            "/".join([fmt(p(k, "pressures", "ra", "a")), fmt(p(k, "pressures", "ra", "v")), fmt(p(k, "pressures", "ra", "mean"))]).strip("/")
            for k in keys
        ])
        add_row("RV s/d/EDP [mmHg]", [
            "/".join([fmt(p(k, "pressures", "rv", "sys")), fmt(p(k, "pressures", "rv", "dia")), fmt(p(k, "pressures", "rv", "edp"))]).strip("/")
            for k in keys
        ])
        add_row("PAP s/d/m [mmHg]", [
            "/".join([fmt(p(k, "pressures", "pa", "sys")), fmt(p(k, "pressures", "pa", "dia")), fmt(p(k, "pressures", "pa", "mean"))]).strip("/")
            for k in keys
        ])
        add_row("PCWP A/V/mean [mmHg]", [
            "/".join([fmt(p(k, "pressures", "pcw", "a")), fmt(p(k, "pressures", "pcw", "v")), fmt(p(k, "pressures", "pcw", "mean"))]).strip("/")
            for k in keys
        ])

        # CO/CI

        # CO/CI
        add_row("CO TD [L/min]", [p(k, "co", "td_co") for k in keys])
        add_row("CI TD [L/min/m²]", [p(k, "co", "td_ci") for k in keys])
        add_row("CO Fick [L/min]", [p(k, "co", "fick_co") for k in keys])
        add_row("CI Fick [L/min/m²]", [p(k, "co", "fick_ci") for k in keys])


        # Resistance (Dokumentwerte; keine Interpretation)
        add_row("PVR [WU] / [dyn·s·cm⁻⁵]", [
            "/".join([fmt(p(k, "resistance", "pvr", "wu")), fmt(p(k, "resistance", "pvr", "dyn"))]).strip("/")
            for k in keys
        ])
        add_row("PVRI [WU·m²] / [dyn·s·cm⁻⁵·m²]", [
            "/".join([fmt(p(k, "resistance", "pvri", "wu")), fmt(p(k, "resistance", "pvri", "dyn"))]).strip("/")
            for k in keys
        ])
        add_row("TPR [WU] / [dyn·s·cm⁻⁵]", [
            "/".join([fmt(p(k, "resistance", "tpr", "wu")), fmt(p(k, "resistance", "tpr", "dyn"))]).strip("/")
            for k in keys
        ])
        add_row("TPRI [WU·m²] / [dyn·s·cm⁻⁵·m²]", [
            "/".join([fmt(p(k, "resistance", "tpri", "wu")), fmt(p(k, "resistance", "tpri", "dyn"))]).strip("/")
            for k in keys
        ])
        add_row("TVR [WU] / [dyn·s·cm⁻⁵]", [
            "/".join([fmt(p(k, "resistance", "tvr", "wu")), fmt(p(k, "resistance", "tvr", "dyn"))]).strip("/")
            for k in keys
        ])

        # Derived gradients

        # Derived gradients (from pressures)
        def tpg_for(ph: str):
            mpap = p(ph, "pressures", "pa", "mean")
            pcw = p(ph, "pressures", "pcw", "mean")
            try:
                if mpap is None or pcw is None:
                    return None
                return float(mpap) - float(pcw)
            except Exception:
                return None

        def dpg_for(ph: str):
            d = p(ph, "pressures", "pa", "dia")
            pcw = p(ph, "pressures", "pcw", "mean")
            try:
                if d is None or pcw is None:
                    return None
                return float(d) - float(pcw)
            except Exception:
                return None

        add_row("TPG [mmHg]", [tpg_for(k) for k in keys])
        add_row("DPG [mmHg]", [dpg_for(k) for k in keys])

        def papi_for(ph: str):
            try:
                s = p(ph, "pressures", "pa", "sys")
                d = p(ph, "pressures", "pa", "dia")
                ra = p(ph, "pressures", "ra", "mean")
                if s is None or d is None or ra in (None, 0):
                    return None
                return (float(s) - float(d)) / float(ra)
            except Exception:
                return None

        def sv_for(ph: str):
            try:
                co = p(ph, "co", "td_co") or p(ph, "co", "fick_co")
                hr = p(ph, "co", "fick_hr")
                if co is None or hr in (None, 0):
                    return None
                return float(co) * 1000.0 / float(hr)
            except Exception:
                return None

        add_row("PAPI", [papi_for(k) for k in keys])
        add_row("SV [ml] (CO/HR)", [sv_for(k) for k in keys])

        core_html = mk_table(["Parameter"] + cols, rows_core, cls="rhk-tbl")

        # Blood gas / oximetry (raw)
        bg = ((payload or {}).get("timeseries") or {}).get("bloodgas") or []
        bg_rows: list[list[object]] = []
        for r in bg[:80]:
            if not isinstance(r, dict):
                continue
            bg_rows.append([
                r.get("time"),
                r.get("site"),
                r.get("group"),
                r.get("hb_g_dl"),
                r.get("sat_pct"),
                r.get("po2_mmhg"),
                r.get("content_ml_dl"),
            ])
        bg_html = ""
        if bg_rows:
            bg_html = mk_table([
                "Zeit", "Ort", "Gruppe", "Hb [g/dl]", "Sättigung [%]", "pO₂ [mmHg]", "O₂-Content [ml/dl]",
            ], bg_rows, cls="rhk-tbl")

        def _is_risk_like_table(title: str, matrix: list[list[object]]) -> bool:
            # Das gesamte ESC/ERS Risiko-Range-Kapitel ist nicht patient*innenspezifisch.
            # Es soll weder extrahiert noch als "roh" angezeigt werden.
            t = (title or "").strip()
            if re.search(r"risiko|risk", t, flags=re.IGNORECASE):
                return True
            # Viele dieser Range-Tabellen haben keinen klaren Titel in der ersten Zelle.
            # Deshalb zusätzlich auf Inhalte prüfen (nur wenige Zeilen scannen).
            try:
                sample = " ".join([" ".join([str(c) for c in row]) for row in (matrix or [])[:4]])
            except Exception:
                sample = ""
            if re.search(r"WHO\-Funktionsklasse|REVEAL|COMPERA|Geringes\s+R|Intermedi|Hohes\s+R", sample, flags=re.IGNORECASE):
                return True
            if re.search(r"Biomarker", sample, flags=re.IGNORECASE) and re.search(r"NT\-?proBNP|BNP\b", sample, flags=re.IGNORECASE) and re.search(r"<|>", sample):
                return True
            return False

        # All extracted tables (except risk-like tables)
        all_tables = ((payload or {}).get("raw_tables") or {}).get("all_tables") or []
        tbl_html_parts: list[str] = []
        for t in all_tables:
            try:
                title = (t.get("title") or "").strip()
                matrix = t.get("matrix") or []
                if _is_risk_like_table(title, matrix):
                    continue
                if not matrix:
                    continue
                # "Max.Last" Spalte: In manchen MacLab-Tabellen ist die letzte Kopfzelle leer.
                # Wenn eine Ergometrie-Spalte existiert, füllen wir "Max.Last" mit den Ergo-Werten
                # (rein für Transparenz in der Rohdarstellung).
                try:
                    header = list(matrix[0]) if matrix and matrix[0] else []
                    if header and len(header) >= 5:
                        ergo_idx = None
                        for j, h in enumerate(header):
                            if isinstance(h, str) and re.search(r"ergometrie", h, flags=re.IGNORECASE):
                                ergo_idx = j
                                break
                        if (ergo_idx is not None) and (str(header[-1]).strip() == ""):
                            header[-1] = "Max.Last"
                            # copy matrix for display only
                            patched = [header]
                            for rr in matrix[1:]:
                                r = list(rr)
                                # ensure length
                                if len(r) < len(header):
                                    r = r + [""] * (len(header) - len(r))
                                if str(r[-1]).strip() == "" and ergo_idx < len(r):
                                    r[-1] = r[ergo_idx]
                                patched.append(r)
                            matrix = patched
                except Exception:
                    pass
                # limit extremely large tables to keep UI snappy
                max_rows = 120
                matrix_show = matrix[:max_rows]
                headers = [str(x) for x in matrix_show[0]]
                rows = [list(row) for row in matrix_show[1:]]
                tbl = mk_table(headers, rows, cls="rhk-tbl")
                more = "" if len(matrix) <= max_rows else f"<div class='docx-muted'>… {len(matrix)-max_rows} weitere Zeilen ausgeblendet</div>"
                tbl_html_parts.append(
                    f"<details class='docx-details'><summary>{_html.escape(title or 'Tabelle')}</summary>{tbl}{more}</details>"
                )
            except Exception:
                continue

        tables_html = "".join(tbl_html_parts)

        qual = (payload or {}).get("quality") or {}
        qual_status = _html.escape(str(qual.get("status") or ""))
        qual_reasons = qual.get("reasons") or []
        qual_html = ""
        if qual_status:
            reasons = "".join([f"<li>{_html.escape(str(x))}</li>" for x in qual_reasons])
            qual_html = f"<div class='docx-muted'>Import-Qualität: {qual_status}</div>" + (f"<ul class='docx-list'>{reasons}</ul>" if reasons else "")

        parts = [
            f"<div class='docx-title'>{_html.escape(label)} – Tabellenübersicht (Quelle: DOCX)</div>",
            qual_html,
            core_html,
        ]
        if bg_html:
            parts.append(f"<details class='docx-details'><summary>Oximetrie und BGA (roh)</summary>{bg_html}</details>")
        if tables_html:
            parts.append(f"<details class='docx-details'><summary>Alle extrahierten Tabellen (roh)</summary>{tables_html}</details>")

        return "<div class='docx-box'>" + "".join(parts) + "</div>"

    html_parts = []
    if docx_cur:
        html_parts.append(render(docx_cur, "Aktueller RHK"))
    if docx_prev:
        html_parts.append(render(docx_prev, "Vor-RHK"))

    return "".join([p for p in html_parts if p])

def build_rhk_plots_html(case: dict, docx_cur: dict | None, docx_prev: dict | None) -> str:
    if not isinstance(case, dict):
        return ""
    der = case.get("derived") or {}
    raw = case.get("raw") or {}

    charts: list[str] = []

    # 1) Phasen-Verlauf aus Docx (Base 1/2/Ergo/Post)
    if isinstance(docx_cur, dict) and (docx_cur.get("phases") or {}):
        ph = docx_cur.get("phases") or {}
        order = ["base1", "base2", "exercise", "post", "no", "o2"]
        phase_keys = [k for k in order if k in ph]
        for k in ph.keys():
            if k not in phase_keys:
                phase_keys.append(k)
        label_map = {
            "base1": "Base 1",
            "base2": "Base 2",
            "exercise": "Ergo",
            "post": "Post",
            "no": "NO",
            "o2": "O2",
        }
        labels = [label_map.get(k, k) for k in phase_keys]

        def _get_val(k: str, path: tuple[str, ...]) -> float | None:
            try:
                cur = ph.get(k) or {}
                for p in path:
                    cur = cur.get(p) if isinstance(cur, dict) else None
                return cur if isinstance(cur, (int, float)) else None
            except Exception:
                return None

        mpap = [_get_val(k, ("pressures", "pa", "mean")) for k in phase_keys]
        pawp = [_get_val(k, ("pressures", "pcw", "mean")) for k in phase_keys]
        rap = [_get_val(k, ("pressures", "ra", "mean")) for k in phase_keys]

        co_td = [_get_val(k, ("co", "td_co")) for k in phase_keys]
        co_fk = [_get_val(k, ("co", "fick_co")) for k in phase_keys]
        ci_td = [_get_val(k, ("co", "td_ci")) for k in phase_keys]
        ci_fk = [_get_val(k, ("co", "fick_ci")) for k in phase_keys]

        pvr = [_get_val(k, ("resistance", "pvr", "wu")) for k in phase_keys]
        pvri = [_get_val(k, ("resistance", "pvri", "wu")) for k in phase_keys]

        if any(v is not None for v in mpap + pawp + rap):
            charts.append(
                svg_series_over_phases(
                    labels,
                    {"mPAP": mpap, "PAWP": pawp, "RAP": rap},
                    "Zentrale Drücke (Phasen)",
                    "mmHg",
                )
            )

        if any(v is not None for v in co_td + co_fk):
            charts.append(
                svg_series_over_phases(
                    labels,
                    {"HZV TD": co_td, "HZV Fick": co_fk},
                    "HZV Verlauf (Phasen)",
                    "l/min",
                )
            )

        if any(v is not None for v in ci_td + ci_fk):
            charts.append(
                svg_series_over_phases(
                    labels,
                    {"CI TD": ci_td, "CI Fick": ci_fk},
                    "CI Verlauf (Phasen)",
                    "l/min/m²",
                )
            )

        if any(v is not None for v in pvr + pvri):
            charts.append(
                svg_series_over_phases(
                    labels,
                    {"PVR": pvr, "PVRI": pvri},
                    "Widerstände (Phasen)",
                    "WU",
                )
            )

    # 2) mPAP/PAWP gegen HZV (Rest -> Peak)
    if bool(raw.get("exercise_done")):
        charts.append(svg_mpap_pawp_vs_co(
            der.get("mpap"), der.get("pawp"), der.get("co"),
            der.get("mpap_peak"), der.get("pawp_peak"), der.get("co_peak"),
            title="Ergometrie: Druck gegen HZV"
        ))

    # 3) Vorher vs Jetzt (Delta-Bars) – fokussiert auf Basis-Hämodynamik
    prev = {
        "mPAP": raw.get("prev_mpap"),
        "PAWP": raw.get("prev_pawp"),
        "RAP": raw.get("prev_rap"),
        "CI": raw.get("prev_ci"),
        "PVR": raw.get("prev_pvr"),
    }
    cur = {
        "mPAP": der.get("mpap"),
        "PAWP": der.get("pawp"),
        "RAP": der.get("rap"),
        "CI": der.get("ci"),
        "PVR": der.get("pvr"),
    }
    delta_items = []
    for k in ("mPAP", "PAWP", "RAP", "CI", "PVR"):
        try:
            if prev.get(k) is None or cur.get(k) is None:
                continue
            delta_items.append((k, float(cur[k]) - float(prev[k])))
        except Exception:
            continue
    if delta_items:
        charts.append(svg_delta_bars(delta_items, "Vorher vs Jetzt (Differenz)", "Delta", note="Delta = Jetzt minus Vorher"))

    # 3b) Vorher vs Jetzt (Absolute Werte) – eigene, schnelle Übersicht
    try:
        press_items = []
        if prev.get("mPAP") is not None and cur.get("mPAP") is not None:
            press_items.append(("mPAP", float(prev["mPAP"]), float(cur["mPAP"])))
        if prev.get("PAWP") is not None and cur.get("PAWP") is not None:
            press_items.append(("PAWP", float(prev["PAWP"]), float(cur["PAWP"])))
        if prev.get("RAP") is not None and cur.get("RAP") is not None:
            press_items.append(("RAP", float(prev["RAP"]), float(cur["RAP"])))
        if press_items:
            charts.append(svg_compare_bars(press_items, "Vorher vs Jetzt (Drücke)", "mmHg"))

        ci_items = []
        if prev.get("CI") is not None and cur.get("CI") is not None:
            ci_items.append(("CI", float(prev["CI"]), float(cur["CI"])))
        if ci_items:
            charts.append(svg_compare_bars(ci_items, "Vorher vs Jetzt (Cardiac Index)", "l/min/m²"))

        pvr_items = []
        if prev.get("PVR") is not None and cur.get("PVR") is not None:
            pvr_items.append(("PVR", float(prev["PVR"]), float(cur["PVR"])))
        if pvr_items:
            charts.append(svg_compare_bars(pvr_items, "Vorher vs Jetzt (PVR)", "WU"))
    except Exception:
        pass

    # 4) Volumenchallenge (Pre -> Post)
    if bool(raw.get("volume_challenge_done")):
        try:
            pawp_pre = raw.get("pawp_pre")
            pawp_post = raw.get("pawp_post")
            mpap_pre = raw.get("mpap_pre")
            mpap_post = raw.get("mpap_post")
            items = []
            if pawp_pre is not None and pawp_post is not None:
                items.append(("PAWP", float(pawp_post) - float(pawp_pre)))
            if mpap_pre is not None and mpap_post is not None:
                items.append(("mPAP", float(mpap_post) - float(mpap_pre)))
            if items:
                charts.append(svg_delta_bars(items, "Volumenchallenge (Post minus Pre)", "mmHg"))
        except Exception:
            pass

    if not charts:
        return ""

    return "<div class='rhk-viz-grid'>" + "".join([f"<div class='rhk-viz-item'>{c}</div>" for c in charts if c]) + "</div>"

def build_p_module_cards_html(blocks: Dict[str, Any], case: Optional[Dict[str, Any]]) -> str:
    if not case:
        return ""
    der = case.get("derived") or {}
    decision = case.get("decision") or {}
    ui = case.get("ui") or {}

    policy = der.get("p_module_policy") or {}
    levels = policy.get("levels") or {}
    disabled = policy.get("disabled") or {}

    auto_mods = _normalize_module_ids(decision.get("modules") or [])
    sel_mods = _normalize_module_ids(ui.get("modules") or [])
    # Keep selection order stable (auto first)
    sel_mods = list(dict.fromkeys(auto_mods + sel_mods))

    def lvl_chip(lvl: int) -> str:
        if lvl == 1:
            return "<span class='pmod-chip pmod-chip--lvl1'>Level I</span>"
        if lvl == 2:
            return "<span class='pmod-chip pmod-chip--lvl2'>Level II</span>"
        return "<span class='pmod-chip pmod-chip--lvl3'>Level III</span>"

    # Reduce visual overload: show primarily Level I/II + currently selected modules.
    # Locked modules are displayed separately via `build_disabled_p_modules_html()`.
    allowed = set(policy.get("allowed") or [])
    pids_to_show: List[str] = []
    for pid in _ALL_P_MODULE_IDS:
        if pid in disabled:
            continue
        if allowed and pid not in allowed:
            continue
        try:
            lvl = int(levels.get(pid, 3) or 3)
        except Exception:
            lvl = 3
        if lvl <= 2 or pid in sel_mods or pid in auto_mods:
            pids_to_show.append(pid)

    cards = []
    for pid in pids_to_show:
        b = blocks.get(pid)
        title = b.title if b else pid
        subtitle = ""
        try:
            subtitle = b.subtitle if b and getattr(b, "subtitle", None) else ""
        except Exception:
            subtitle = ""

        lvl = int(levels.get(pid, 3) or 3)
        locked_reason = None
        is_locked = False

        is_auto = pid in auto_mods
        is_selected = pid in sel_mods
        is_manual = (is_selected and not is_auto)

        meta = [lvl_chip(lvl)]
        if is_auto:
            meta.append("<span class='pmod-chip pmod-chip--auto'>Auto</span>")
        elif is_manual:
            meta.append("<span class='pmod-chip pmod-chip--manual'>Manuell</span>")

        tip = ""
        if is_locked and locked_reason:
            tip = html_escape(str(locked_reason))

        cards.append(
            f"<div class='pmod-card' title='{tip}'>"
            f"<div class='pmod-title'>{pid} – {html_escape(str(title))}</div>"
            f"<div class='pmod-sub'>{html_escape(str(subtitle))}</div>"
            f"<div class='pmod-meta'>{''.join(meta)}</div>"
            "</div>"
        )

    auto_n = len(auto_mods)
    manual_n = len([m for m in sel_mods if (m not in auto_mods)])
    locked_n = len(disabled)

    shown_n = len(pids_to_show)
    header = (
        "<div class='rhk-summarybar' style='margin: 4px 0 8px;'>"
        f"<span class='rhk-schip rhk-schip--info'>Module: Auto {auto_n}</span>"
        f"<span class='rhk-schip'>Manuell {manual_n}</span>"
        f"<span class='rhk-schip rhk-schip--warn'>Gesperrt {locked_n}</span>"
        f"<span class='rhk-schip'>Anzeige: {shown_n}/{len(_ALL_P_MODULE_IDS)} (Level I–II + ausgewählt)</span>"
        "</div>"
    )

    if not cards:
        return header
    return header + "<div class='pmod-grid'>" + "".join(cards) + "</div>"


def build_demo() -> Tuple[gr.Blocks, str, gr.Theme]:
    blocks = load_textdb_blocks()
    rules = load_rulebook(DEFAULT_RULEBOOK_PATH)
    rulebook_meta = load_rulebook_meta(DEFAULT_RULEBOOK_PATH)

    # Gradio versions differ; themes are available in newer builds.
    theme = None
    try:
        if hasattr(gr, "themes"):
            theme = gr.themes.Soft()
    except Exception:
        theme = None

    # Gradio 6 moved theme/css/js/head from the Blocks constructor to `.launch()`.
    # We want:
    # - zero warnings on Gradio 6+
    # - full compatibility with Gradio 5
    def _gradio_major() -> int:
        import re
        v = str(getattr(gr, "__version__", ""))
        m = re.match(r"\s*(\d+)", v)
        if not m:
            return 0
        try:
            return int(m.group(1))
        except Exception:
            return 0

    _major = _gradio_major()

    launch_kwargs: Dict[str, Any] = {"css": CSS, "js": JS_ON_LOAD, "head": HEAD_HTML}
    if theme is not None:
        launch_kwargs["theme"] = theme

    if _major >= 6:
        # 6.x+: pass assets to launch() (constructor must stay clean)
        demo_ctx = gr.Blocks(title=APP_TITLE)
        setattr(demo_ctx, "_rhk_launch_kwargs", launch_kwargs)
    else:
        # 5.x: assets belong to Blocks constructor
        blocks_kwargs: Dict[str, Any] = {"title": APP_TITLE, "css": CSS, "js": JS_ON_LOAD, "head": HEAD_HTML}
        if theme is not None:
            blocks_kwargs["theme"] = theme
        demo_ctx = gr.Blocks(**blocks_kwargs)
        setattr(demo_ctx, "_rhk_launch_kwargs", {})

    with demo_ctx as demo:
        # Header
        gr.HTML(RHK_HEADER_HTML)
        gr.Markdown(f"<div class='whatsnew'>{WHATS_NEW}</div>")

        # Sticky live preview (always visible)
        sticky_summary_html = gr.HTML(
            value=build_sticky_summary_html(None),
            elem_id="rhk_summarybar_wrapper",
        )
# Buttons top
        with gr.Row():
            btn_example_top = gr.Button("Beispiel laden (random)", variant="secondary", elem_id="btn_example_top")
            btn_generate_top = gr.Button("Befund erstellen/aktualisieren", variant="secondary", elem_id="btn_generate_top")
            btn_clear_top = gr.Button("Befunde leeren", variant="secondary", elem_id="btn_clear_top")
            save_btn_top = gr.Button("Fall speichern (.json)", variant="secondary", elem_id="btn_save_top")
            load_btn_top = gr.UploadButton("Fall laden (.json)", file_types=[".json"], variant="secondary", elem_id="btn_load_top")
        docx_btn_top = gr.UploadButton("RHK import (.docx)", file_types=[".docx"], variant="primary", elem_id="btn_docx_top")
        # DOCX Import Übersicht wird im RHK-Tab angezeigt (Accordion, open=True).
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
                        add("sex", gr.Dropdown(label="Geschlecht", choices=["keine Angabe", "weiblich", "männlich"], value="keine Angabe"))
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
                        add("chd_type", gr.Dropdown(label="Welche Diagnose? (optional)", choices=["keine Angabe", "ASD (Vorhofseptumdefekt)", "VSD (Ventrikelseptumdefekt)", "PDA (Ductus arteriosus persistens)", "AVSD (atrioventrikulärer Septumdefekt)", "Komplexer Herzfehler / univentrikulär", "Eisenmenger-Syndrom", "Status nach Korrektur (z.B. Shunt-Verschluss)", "Sonstiges/unklar"], value="keine Angabe"))
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
                                "keine Angabe",
                                "PAH (Gruppe 1)",
                                "PH bei Linksherzerkrankung / HFpEF (Gruppe 2)",
                                "PH bei Lungenerkrankung / Hypoxie (Gruppe 3)",
                                "CTEPH (Gruppe 4)",
                                "Sonstige/unklar (Gruppe 5)",
                            ],
                            value="keine Angabe",
                        ))
                        add("ph_known_subtype", gr.Textbox(label="Subtyp / Kontext (optional)", lines=2, placeholder="z.B. Systemsklerose, Portopulmonal, idiopathisch …"))
                        with gr.Row():
                            add("ph_first_dx", gr.Textbox(label="Erstdiagnose (MM/JJJJ)", placeholder="z.B. 03/2021"))
                            add("ph_reason_rhk", gr.Dropdown(
                                label="Grund der aktuellen Untersuchung",
                                choices=["keine Angabe", "Verlaufskontrolle", "Therapieentscheidung", "Neusymptomatik", "vor Eingriff/OP", "Sonstiges"],
                                value="keine Angabe",
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
                        add("who_fc", gr.Dropdown(label="WHO-FC", choices=["keine Angabe", "I", "II", "III", "IV"], value="keine Angabe"))
                        add("six_mwd_m", gr.Number(label="6MWD (m)"))
                        add("syncope", gr.Dropdown(label="Synkope", choices=["keine Angabe", "keine", "gelegentlich", "wiederholt"], value="keine Angabe"))
                    with gr.Row():
                        add("hemoptysis", gr.Checkbox(label="Hämoptyse"))
                        add("dizziness", gr.Checkbox(label="Schwindel"))
                        add("stairs_flights", gr.Number(label="Treppen (Etagen) bis Pause", precision=0))

                    gr.Markdown("### Labor")
                    with gr.Row():
                        add("hb_g_dl", gr.Number(label="Hb (g/dl)"))
                        anemia_type = add("anemia_type", gr.Dropdown(
                            label="Anämie-Typ (falls Anämie vorliegt)",
                            choices=["keine Angabe", "mikrozytär", "normozytär", "makrozytär", "hämolytisch", "akute Blutung/Blutverlust", "unklar"],
                            value="keine Angabe",
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
                        add("congestive_organopathy", gr.Radio(label="Hinweis auf congestive Organopathie?", choices=["keine Angabe", "ja", "nein"], value="keine Angabe"))

                    gr.Markdown("### Medikation & wichtige Zusatzangaben")

                    # Antikoagulation (wichtig v.a. für CTEPH-/Embolie-Logik)
                    with gr.Row():
                        anticoag_status = add("anticoag_status", gr.Dropdown(
                            label="Antikoagulation (Blutverdünnung)?",
                            choices=["keine Angabe", "ja", "nein", "unklar"],
                            value="keine Angabe",
                        ))
                        anticoag_substance = add("anticoag_substance", gr.Dropdown(
                            label="Substanz / Klasse (falls ja)",
                            choices=[
                                "keine Angabe",
                                "DOAC (Apixaban, Rivaroxaban, Edoxaban, Dabigatran)",
                                "VKA (Phenprocoumon/Warfarin)",
                                "Heparin/LMWH",
                                "Fondaparinux",
                                "sonstiges",
                            ],
                            value="keine Angabe",
                            visible=False,
                        ))
                    with gr.Row():
                        anticoag_indication = add("anticoag_indication", gr.Dropdown(
                            label="Indikation (falls ja)",
                            # NOTE: "keine Angabe" als explizite (leere) Option – verhindert Legacy-Load-Errors
                            choices=["keine Angabe", "Vorhofflimmern", "Venenthrombose/Lungenembolie", "CTEPH/CTEPD", "Mechanische Klappe", "Andere/unklar"],
                            value="keine Angabe",
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
                            choices=["keine Angabe", "ja", "nein", "unklar"],
                            value="keine Angabe",
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
                            choices=["keine Angabe", "ja", "nein", "unklar"],
                            value="keine Angabe",
                        ))
                        with gr.Row():
                            antifib_drug = add("antifibrotic_drug", gr.Dropdown(
                                label="Präparat (falls ja)",
                                choices=["keine Angabe", "Nintedanib", "Pirfenidon", "sonstiges"],
                                value="keine Angabe",
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
                    echo_ui = build_echo_section(add)
                    import_pdf_cur = echo_ui["import_pdf_cur"]
                    import_pdf_prev = echo_ui["import_pdf_prev"]
                    import_preview_cur_html = echo_ui["import_preview_cur_html"]
                    import_preview_prev_html = echo_ui["import_preview_prev_html"]
                    compare_echo_html = echo_ui["compare_html"]
                    state_echo_cur = echo_ui["state_echo_cur"]
                    state_echo_prev = echo_ui["state_echo_prev"]
                    btn_echo_apply = echo_ui["btn_apply"]
                    btn_echo_clear = echo_ui["btn_clear_cur"]
                    btn_echo_clear_prev = echo_ui["btn_clear_prev"]


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
                    rhk_ui = build_rhk_tab(add)
                    import_status_html = rhk_ui["import_status_html"]
                    rhk_plots_html = rhk_ui["rhk_plots_html"]
                    compare_overview_html = rhk_ui["compare_overview_html"]
                    prev_docx_btn = rhk_ui["prev_docx_btn"]
                    auto_mpap = rhk_ui["auto_mpap"]
                    auto_ci = rhk_ui["auto_ci"]
                    auto_pvr = rhk_ui["auto_pvr"]
                    auto_pvri = rhk_ui["auto_pvri"]
                    auto_tpg = rhk_ui["auto_tpg"]
                    auto_dpg = rhk_ui["auto_dpg"]

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
                    base_module_choices: List[str] = []
                    for pid in p_ids:
                        if pid in blocks:
                            base_module_choices.append(f"{pid} – {blocks[pid].title}")

                    # Visual Card Layer (Auto/Manuell/Gesperrt + Level)
                    # Wichtig: Diese Übersicht soll NICHT überladen wirken. Daher:
                    # - Karten zeigen standardmäßig nur Level I/II + ausgewählte Module.
                    # - Die eigentliche Auswahl erfolgt im Accordion "Module auswählen".
                    modules_cards_html = gr.HTML(value="", elem_id="pmods_cards")

                    # Nicht anwählbare Module inkl. medizinischer Begründung (Tooltip) – bleibt sichtbar
                    modules_disabled_html = gr.HTML(value="", elem_id="modules_disabled")

                    with gr.Accordion("P-Module auswählen / bearbeiten", open=False, elem_id="pmods_accordion"):
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

                    add("procedere_free", gr.Textbox(label="Procedere – Freitext", lines=3, elem_id="procedere_free"))
                    gr.Markdown("Hinweis: Bereits durchgeführte Untersuchungen werden in den Modulen möglichst ausgefiltert (z.B. V/Q, CT, Echo, Lufu).")

            with gr.Column(scale=5):
                dashboard = gr.HTML(value=build_dashboard_html(None))

                # Copy/paste helpers (plain text, no formatting chaos)
                with gr.Row(elem_id="rhk_copy_row"):
                    btn_copy_doc = gr.Button("Arztbericht komplett kopieren", variant="secondary", elem_id="btn_copy_doc")
                    btn_copy_pat = gr.Button("Patient*innenbrief komplett kopieren", variant="secondary", elem_id="btn_copy_pat")
                    btn_copy_rhk = gr.Button("nur RHK Abschnitt kopieren", variant="secondary", elem_id="btn_copy_rhk")
                copy_feedback = gr.Markdown("", elem_id="rhk_copy_feedback")

                # Clipboard payloads MUST stay in DOM for robust cross-browser copy.
                # We hide them via CSS (display:none) instead of Gradio's visible=False,
                # because visible=False may not render the component at all.
                copy_doc_plain = gr.Textbox(
                    value="",
                    label="",
                    show_label=False,
                    interactive=False,
                    elem_id="copy_doc_plain",
                    elem_classes=["rhk-hidden-payload"],
                )
                copy_pat_plain = gr.Textbox(
                    value="",
                    label="",
                    show_label=False,
                    interactive=False,
                    elem_id="copy_pat_plain",
                    elem_classes=["rhk-hidden-payload"],
                )
                copy_rhk_plain = gr.Textbox(
                    value="",
                    label="",
                    show_label=False,
                    interactive=False,
                    elem_id="copy_rhk_plain",
                    elem_classes=["rhk-hidden-payload"],
                )

                copy_doc_html = gr.Textbox(
                    value="",
                    label="",
                    show_label=False,
                    interactive=False,
                    elem_id="copy_doc_html",
                    elem_classes=["rhk-hidden-payload"],
                )
                copy_pat_html = gr.Textbox(
                    value="",
                    label="",
                    show_label=False,
                    interactive=False,
                    elem_id="copy_pat_html",
                    elem_classes=["rhk-hidden-payload"],
                )
                copy_rhk_html = gr.Textbox(
                    value="",
                    label="",
                    show_label=False,
                    interactive=False,
                    elem_id="copy_rhk_html",
                    elem_classes=["rhk-hidden-payload"],
                )

                with gr.Tabs(elem_id="rhk_output_tabs"):
                    with gr.TabItem("Arztbericht"):
                        out_doc = gr.Markdown(elem_id="out_doc", elem_classes=["rhk-scrollbox"])
                    with gr.TabItem("Echo Arztbefund (extended)"):
                        out_echo_doc = gr.Markdown(elem_id="out_echo_doc", elem_classes=["rhk-scrollbox"])
                    with gr.TabItem("Patientenbericht"):
                        out_pat = gr.Markdown(elem_id="out_pat", elem_classes=["rhk-scrollbox"])
                    with gr.TabItem("Echo Patientenbericht"):
                        out_echo_pat = gr.Markdown(elem_id="out_echo_pat", elem_classes=["rhk-scrollbox"])
                    with gr.TabItem("Intern"):
                        out_int = gr.Markdown(elem_id="out_int", elem_classes=["rhk-scrollbox"])
                    with gr.TabItem("Summary (JSON)"):
                        out_summary_json = gr.Code(language="json", elem_id="out_summary_json", elem_classes=["rhk-scrollbox"])
                    with gr.TabItem("Debug"):
                        out_json = gr.Code(language="json", elem_id="out_json", elem_classes=["rhk-scrollbox"])

        # Buttons bottom (mirrored)
        with gr.Row():
            btn_example_bottom = gr.Button("Beispiel laden (random)", variant="secondary", elem_id="btn_example_bottom")
            btn_generate_bottom = gr.Button("Befund erstellen/aktualisieren", variant="secondary", elem_id="btn_generate_bottom")
            btn_clear_bottom = gr.Button("Befunde leeren", variant="secondary", elem_id="btn_clear_bottom")
            save_btn_bottom = gr.Button("Fall speichern (.json)", variant="secondary", elem_id="btn_save_bottom")
            load_btn_bottom = gr.UploadButton("Fall laden (.json)", file_types=[".json"], variant="secondary", elem_id="btn_load_bottom")
            docx_btn_bottom = gr.UploadButton("RHK import (.docx)", file_types=[".docx"], variant="primary", elem_id="btn_docx_bottom")

        file_out = gr.File(label="Download: gespeicherter Fall (.json)", visible=False)
        file_summary_out = gr.File(label="Download: Summary (.json)", visible=False)

        # Single "dirty" ping from the browser (debounced). Avoids binding change-handlers to dozens of fields.
        dirty_ping = gr.Textbox(value="", visible=False, elem_id="rhk_dirty_ping")

        state_case = gr.State(value=None)
        state_pmods_selected = gr.State(value={"lvl1": [], "lvl2": [], "lvl3": []})
        state_flags = gr.State(value={"dirty": False, "saved_at": None, "has_report": False, "report_stale": False})

        # DOCX import cache (current + previous catheter). Must exist even if user never imports.
        # Stored as full parsed payload dict (or None).
        state_docx_cur = gr.State(value=None)
        state_docx_prev = gr.State(value=None)

        # Echo PDF Import bindings (Textlayer only)
        try:
            bind_echo_import(echo_ui, field_components=field_components)
        except Exception:
            # UI must stay alive even if import bindings fail
            pass


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

        def _bind_change(comp, fn, inputs=None, outputs=None):
            """Bind lightweight change callbacks without queue/loading flicker (best-effort across Gradio versions)."""
            try:
                # Newer Gradio: hide any progress UI (prevents "pulse"/fade on newly visible blocks)
                comp.change(
                    fn,
                    inputs=inputs,
                    outputs=outputs,
                    trigger_mode="always_last",
                    queue=False,
                    show_progress="hidden",
                    scroll_to_output=False,
                )
            except TypeError:
                try:
                    # Older Gradio: no show_progress/scroll_to_output
                    comp.change(fn, inputs=inputs, outputs=outputs, trigger_mode="always_last", queue=False)
                except TypeError:
                    comp.change(fn, inputs=inputs, outputs=outputs)

        _bind_change(field_components["virology_pos"], lambda x: (gr.update(visible=bool(x)), gr.update(visible=bool(x))), inputs=[field_components["virology_pos"]], outputs=[viro_items, viro_desc])
        _bind_change(field_components["immunology_pos"], lambda x: (gr.update(visible=bool(x)), gr.update(visible=bool(x))), inputs=[field_components["immunology_pos"]], outputs=[immun_items, immun_desc])
        _bind_change(field_components["mutation_pos"], lambda x: (gr.update(visible=bool(x)), gr.update(visible=bool(x))), inputs=[field_components["mutation_pos"]], outputs=[mut_items, mut_desc])
        _bind_change(field_components["chd_pos"], lambda x: gr.update(visible=bool(x)), inputs=[field_components["chd_pos"]], outputs=[chd_details])
        _bind_change(field_components["abd_sono_done"], lambda x: _toggle_desc_text(x), inputs=[field_components["abd_sono_done"]], outputs=[abd_desc])
        _bind_change(field_components["ltot"], lambda x: _toggle_ltot(x), inputs=[field_components["ltot"]], outputs=[ltot_flow])

        # Anemia type show/hide when Hb or sex changes
        _bind_change(field_components["hb_g_dl"], _toggle_anemia, inputs=[field_components["hb_g_dl"], field_components["sex"]], outputs=[anemia_type])
        _bind_change(field_components["sex"], _toggle_anemia, inputs=[field_components["hb_g_dl"], field_components["sex"]], outputs=[anemia_type])
        # Bekannte PH: Details + Exklusivität in EINEM Callback (reduziert Re-Renders / Loading-Fades)
        def _ph_known_changed(known: bool):
            k = bool(known)
            # Details sichtbar nur bei "PH-Diagnose bekannt".
            # Wenn Diagnose bekannt: Verdachtsdiagnose automatisch aus.
            return (
                gr.update(visible=k),
                False if k else gr.update(),
            )

        def _ph_suspected_changed(suspected: bool):
            s = bool(suspected)
            # Wenn Verdacht gesetzt: Diagnose bekannt automatisch aus und Details ausblenden.
            if s:
                return (
                    False,
                    gr.update(visible=False),
                )
            return (
                gr.update(),
                gr.update(),
            )

        _bind_change(
            field_components["ph_known"],
            _ph_known_changed,
            inputs=[field_components["ph_known"]],
            outputs=[ph_known_details, field_components["ph_suspected"]],
        )
        _bind_change(
            field_components["ph_suspected"],
            _ph_suspected_changed,
            inputs=[field_components["ph_suspected"]],
            outputs=[field_components["ph_known"], ph_known_details],
        )

        # Antikoagulation: Detailfelder nur bei "ja"
        def _toggle_anticoag(status: str):
            on = str(status or "").strip().lower() == "ja"
            return (
                gr.update(visible=on),
                gr.update(visible=on),
                gr.update(visible=on),
                gr.update(visible=on),
            )
        _bind_change(field_components["anticoag_status"], _toggle_anticoag, inputs=[field_components["anticoag_status"]], outputs=[anticoag_substance, anticoag_indication, anticoag_since, anticoag_note])

        # ILD – Antifibrotika: Block nur bei ILD; Detailfelder nur bei "ja"
        _bind_change(field_components["ct_ild"], lambda x: _toggle_desc(x), inputs=[field_components["ct_ild"]], outputs=[ild_tx_details])

        def _toggle_antifib(status: str):
            on = str(status or "").strip().lower() == "ja"
            return (
                gr.update(visible=on),
                gr.update(visible=on),
                gr.update(visible=on),
            )
        _bind_change(field_components["antifibrotic_status"], _toggle_antifib, inputs=[field_components["antifibrotic_status"]], outputs=[antifib_drug, antifib_since, antifib_note])


        # --- Helpers to map UI dict to component list ---
        input_components = [field_components[k] for k in field_components.keys()]
        input_keys = list(field_components.keys())

        def ui_get_raw(*vals):
            return {k: v for k, v in zip(input_keys, vals)}

        # Default UI snapshot (used to hard-reset patient-specific state before DOCX import).
        DEFAULT_UI: Dict[str, Any] = {}
        for k, comp in zip(input_keys, input_components):
            try:
                DEFAULT_UI[k] = getattr(comp, 'value', None)
            except Exception:
                DEFAULT_UI[k] = None
        # Dropdowns that must never be invalid (avoid 'value not in choices' crashes)
        if 'anticoag_indication' in DEFAULT_UI:
            DEFAULT_UI['anticoag_indication'] = 'keine Angabe'


        def apply_ui_to_components(ui_dict: Dict[str, Any]) -> List[Any]:
            import re
            def _choice_values(comp) -> List[Any]:
                """Return the *values* accepted by a choice component (supports (label,value) tuples)."""
                try:
                    ch = list(getattr(comp, "choices", []) or [])
                except Exception:
                    return []
                vals: List[Any] = []
                for c in ch:
                    if isinstance(c, (tuple, list)) and len(c) >= 1:
                        vals.append(c[1] if len(c) >= 2 else c[0])
                    else:
                        vals.append(c)
                return vals

            def _strip_level_prefix(s: str) -> str:
                # e.g. "[I] P01 – ..." -> "P01 – ..."
                return re.sub(r"^\s*\[[^\]]+\]\s*", "", s or "").strip()

            def _norm_choice_text(x: Any) -> str:
                """Normalize labels/choices for robust equality across browsers/encodings.

                - strips level prefixes ([I]/[II]/[III])
                - normalizes whitespace (incl. NBSP)
                - normalizes dash variants to ' – '
                - lowercases
                """
                s = "" if x is None else str(x)
                s = _strip_level_prefix(s)
                s = s.replace("\u00a0", " ")
                # Normalize dash variants and surrounding whitespace
                s = re.sub(r"\s*[-–—]\s*", " – ", s)
                s = re.sub(r"\s+", " ", s).strip()
                return s.lower()

            def _try_map_to_choice(v: Any, choices: List[Any]) -> Any:
                """Map legacy/variant values to one of current choices when possible."""
                if not choices:
                    return None

                # Fast path: exact match
                try:
                    if v in choices:
                        return v
                except Exception:
                    pass

                vs = "" if v is None else str(v).strip()
                if not vs:
                    return None

                # Build normalized lookup -> original choice
                norm_map: Dict[str, Any] = {}
                for ch in choices:
                    norm_map[_norm_choice_text(ch)] = ch

                v_norm = _norm_choice_text(vs)
                if v_norm in norm_map:
                    return norm_map[v_norm]

                # If an ID like "P01" is present, map to the choice that starts with that ID
                m = re.search(r"\b(P\d{2})\b", _strip_level_prefix(vs), flags=re.IGNORECASE)
                pid = m.group(1).upper() if m else None
                if pid:
                    for ch in choices:
                        ch_clean = _strip_level_prefix(str(ch))
                        if ch_clean.startswith(pid):
                            return ch
                    # As a fallback, map by normalized prefix match
                    pid_norm = _norm_choice_text(pid)
                    for ch in choices:
                        if _norm_choice_text(str(ch)).startswith(pid_norm):
                            return ch

                return None

            def _coerce_for_component(k: str, v: Any) -> Any:
                comp = field_components.get(k)
                cname = (comp.__class__.__name__ if comp else "").lower()

                # Defaults for cleared/missing values:
                # IMPORTANT: numbers must stay None (not 0), otherwise we create physiologically impossible zeros
                # and override auto-calculations (e.g., mPAP).
                if v is None:
                    if "checkboxgroup" in cname:
                        return []
                    if "checkbox" in cname and "checkboxgroup" not in cname:
                        return False
                    if "number" in cname:
                        return None
                    if "slider" in cname:
                        return 0
                    if hasattr(comp, "choices"):
                        choices = _choice_values(comp)
                        if "keine Angabe" in choices:
                            return "keine Angabe"
                        return choices[0] if choices else ""
                    return ""

                # Coerce numbers from legacy string values
                if ("number" in cname or "slider" in cname) and isinstance(v, str):
                    s = v.strip()
                    if s == "":
                        return None if "number" in cname else 0
                    try:
                        return float(s.replace(",", "."))
                    except Exception:
                        return None if "number" in cname else 0

                # Coerce checkbox groups to list
                if "checkboxgroup" in cname:
                    if isinstance(v, (set, tuple)):
                        v = list(v)
                    elif not isinstance(v, list):
                        v = [v] if v not in ("", None) else []
                    # If choices exist, filter/migrate values to current choices
                    if hasattr(comp, "choices"):
                        choices = _choice_values(comp)
                        out: List[Any] = []
                        for it in v:
                            mapped = _try_map_to_choice(it, choices)
                            if mapped is not None:
                                out.append(mapped)
                        return out
                    return v

                # Guard any single-choice component with choices
                if hasattr(comp, "choices"):
                    choices = _choice_values(comp)
                    if choices and v not in choices:
                        mapped = _try_map_to_choice(v, choices)
                        if mapped is not None:
                            return mapped
                        # safe fallback
                        if "keine Angabe" in choices:
                            return "keine Angabe"
                        return choices[0] if choices else ""

                return v

            out: List[Any] = []
            for k in field_components.keys():
                out.append(_coerce_for_component(k, ui_dict.get(k)))
            return out
        def _generate(flags_state, pmods_state, docx_cur_state, docx_prev_state, *vals):
            flags = dict(flags_state or {})
            raw = ui_get_raw(*vals)
            # Module kommen aus der UI als IDs (Choices liefern Value=Pxx); zusätzlich robust normalisieren.
            # Module kommen aus der UI als IDs (Choices liefern Value=Pxx).
            # Beim Laden von Beispielen/JSON-Fällen halten wir die CheckboxGroup in Stage-1 absichtlich leer,
            # um Gradio "Value not in choices"-Fehler zu vermeiden. In diesem Fall übernehmen wir die
            # gewünschte Auswahl aus pmods_state (Seed), aber nur solange noch kein Report existiert und der Fall nicht "dirty" ist.
            ui_mods = _normalize_module_ids((raw.get("modules_lvl1") or []) + (raw.get("modules_lvl2") or []) + (raw.get("modules_lvl3") or []) + (raw.get("modules") or []))
            seed_mods = _normalize_module_ids(((pmods_state or {}).get("lvl1") or []) + ((pmods_state or {}).get("lvl2") or []) + ((pmods_state or {}).get("lvl3") or []))
            if (not ui_mods) and seed_mods and (not flags.get("dirty")) and (not flags.get("has_report")):
                raw["modules"] = seed_mods
            else:
                raw["modules"] = ui_mods
            case = build_case(raw, rules)

            doc = build_doctor_report(case, blocks)
            pat = build_patient_report(case)
            echo_doc = build_echo_doctor_report_extended(case)
            echo_pat = build_echo_patient_report(case)
            internal = build_internal_report(case)
            dash = build_dashboard_html(case)

            # Structured summary (stable schema) for studies/registries/QA
            try:
                summary_dict = build_summary_dict(case, rulebook_meta)
                case["summary"] = summary_dict
                summary_json = json.dumps(summary_dict, ensure_ascii=False, indent=2)
            except Exception:
                summary_dict = {}
                summary_json = "{}"
            # Copy/paste payloads
            # - plain text for systems that break on rich formatting
            # - HTML for Word (clipboard text/html)
            try:
                doc_plain = markdown_to_plain(doc)
                pat_plain = markdown_to_plain(pat)
                rhk_section = extract_markdown_section(doc, "Rechtsherzkatheter", "Beurteilung")
                rhk_plain = markdown_to_plain(rhk_section)

                doc_html = markdown_to_word_html(doc)
                pat_html = markdown_to_word_html(pat)
                rhk_html = markdown_to_word_html(rhk_section)
            except Exception:
                doc_plain = ""
                pat_plain = ""
                rhk_plain = ""
                doc_html = ""
                pat_html = ""
                rhk_html = ""

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

            # --- Live preview layers ---
            # Status: report is now up-to-date
            flags["has_report"] = True
            flags["report_stale"] = False
            flags["generated_at"] = _dt.datetime.now().isoformat(timespec="seconds")
            try:
                flags["warnings"] = case.get("warnings") or []
            except Exception:
                flags["warnings"] = []

            summary_html = build_sticky_summary_html(case, flags)
            compare_html = build_compare_overview_html(case)
            cards_html = build_p_module_cards_html(blocks, case)
            # --- DOCX Import: attach raw payloads into case for transparency/QA ---
            try:
                case.setdefault("imports", {})["docx_current"] = docx_cur_state
                case.setdefault("imports", {})["docx_prev"] = docx_prev_state
            except Exception:
                pass

            # --- Import status + plots (never raise) ---
            try:
                status_html = build_docx_status_html(docx_cur_state, docx_prev_state)
            except Exception:
                status_html = ""
            try:
                plots_html = build_rhk_plots_html(case, docx_cur_state, docx_prev_state)
            except Exception:
                plots_html = ""

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


            # --- P-Module UI: robust gegen Gradio-Versionen ---
            # Wir nutzen reine Label-Strings als Choices und Values.
            # Label ohne '[I]/[II]/[III]' Prefix, da Level bereits durch getrennte Gruppen abgebildet wird.
            import re
            def _clean_pmod_label(lab: Any) -> str:
                s = str(lab) if lab is not None else ""
                s = re.sub(r"^\s*\[[^\]]+\]\s*", "", s).strip()
                return s
            
            levels_map = (policy.get("levels") or {}) if isinstance(policy, dict) else {}
            id_to_label = {mid: _clean_pmod_label(lab) for (lab, mid) in mod_choices}
            id_to_level = {mid: int(levels_map.get(mid, 3)) for (_lab, mid) in mod_choices}
            
            choices_lvl1 = [id_to_label[mid] for (_lab, mid) in mod_choices if id_to_level.get(mid, 3) == 1]
            choices_lvl2 = [id_to_label[mid] for (_lab, mid) in mod_choices if id_to_level.get(mid, 3) == 2]
            choices_lvl3 = [id_to_label[mid] for (_lab, mid) in mod_choices if id_to_level.get(mid, 3) not in (1, 2)]
            
            allowed_lvl1_ids = {mid for (_lab, mid) in mod_choices if id_to_level.get(mid, 3) == 1}
            allowed_lvl2_ids = {mid for (_lab, mid) in mod_choices if id_to_level.get(mid, 3) == 2}
            allowed_lvl3_ids = {mid for (_lab, mid) in mod_choices if id_to_level.get(mid, 3) not in (1, 2)}
            
            selected_lvl1_ids = [m for m in sel_vals if m in allowed_lvl1_ids]
            selected_lvl2_ids = [m for m in sel_vals if m in allowed_lvl2_ids]
            selected_lvl3_ids = [m for m in sel_vals if m in allowed_lvl3_ids]
            
            selected_lvl1 = [id_to_label.get(mid) for mid in selected_lvl1_ids if id_to_label.get(mid)]
            selected_lvl2 = [id_to_label.get(mid) for mid in selected_lvl2_ids if id_to_label.get(mid)]
            selected_lvl3 = [id_to_label.get(mid) for mid in selected_lvl3_ids if id_to_label.get(mid)]

            pmods_sel_state = {
                "lvl1": selected_lvl1,
                "lvl2": selected_lvl2,
                "lvl3": selected_lvl3,
            }

            
            modules_lvl1_update = gr.update(choices=choices_lvl1, value=[])
            modules_lvl2_update = gr.update(choices=choices_lvl2, value=[])
            modules_lvl3_update = gr.update(choices=choices_lvl3, value=[])
            return (
                der.get("mpap_calc"), ci_calc, der.get("pvr_calc"), der.get("pvri"), der.get("tpg"), der.get("dpg"),
                dash, doc, pat, echo_doc, echo_pat, internal,
                summary_json,
                json.dumps(case, ensure_ascii=False, indent=2),
                doc_plain, pat_plain, rhk_plain,
                doc_html, pat_html, rhk_html,
                "",  # copy feedback reset
                case,
                flags,
                pmods_sel_state,
                docx_cur_state,
                docx_prev_state,
                modules_lvl1_update,
                modules_lvl2_update,
                modules_lvl3_update,
                disabled_html,
                summary_html,
                compare_html,
                plots_html,
                status_html,
                cards_html,
            )

        def _apply_pmods_values(sel_state: Optional[Dict[str, Any]]):
            """2nd stage: set CheckboxGroup values AFTER choices were updated (robust mapping)."""
            import re
            def _clean(s: Any) -> str:
                return re.sub(r"^\s*\[[^\]]+\]\s*", "", str(s) if s is not None else "").strip()
            def _map_list(vals: Any, comp) -> List[str]:
                if not vals:
                    return []
                if isinstance(vals, (set, tuple)):
                    vals = list(vals)
                elif not isinstance(vals, list):
                    vals = [vals]
                choices = list(getattr(comp, "choices", []) or [])
                choice_set = set(str(c) for c in choices)
                out: List[str] = []
                for v in vals:
                    vv = _clean(v)
                    if not vv:
                        continue
                    if vv in choice_set:
                        out.append(vv)
                        continue
                    # map by ID (Pxx) to the matching choice label
                    m = re.match(r"^(P\d{2})\b", vv)
                    if m:
                        pid = m.group(1)
                        hit = None
                        for c in choices:
                            cs = _clean(c)
                            if cs.startswith(pid + " –") or cs.startswith(pid + " -"):
                                hit = cs
                                break
                        if hit and hit in choice_set:
                            out.append(hit)
                # de-dup while preserving order
                return list(dict.fromkeys(out))
            try:
                return (
                    gr.update(value=_map_list((sel_state or {}).get("lvl1"), modules_lvl1_comp)),
                    gr.update(value=_map_list((sel_state or {}).get("lvl2"), modules_lvl2_comp)),
                    gr.update(value=_map_list((sel_state or {}).get("lvl3"), modules_lvl3_comp)),
                )
            except Exception:
                return (gr.update(value=[]), gr.update(value=[]), gr.update(value=[]))

        generate_outputs = [
            auto_mpap, auto_ci, auto_pvr, auto_pvri, auto_tpg, auto_dpg,
            dashboard,
            out_doc, out_pat, out_echo_doc, out_echo_pat, out_int,
            out_summary_json,
            out_json,
            copy_doc_plain, copy_pat_plain, copy_rhk_plain,
            copy_doc_html, copy_pat_html, copy_rhk_html,
            copy_feedback,
            state_case,
            state_flags,
            state_pmods_selected,
            state_docx_cur,
            state_docx_prev,
            modules_lvl1_comp, modules_lvl2_comp, modules_lvl3_comp,
            modules_disabled_html,
            sticky_summary_html,
            compare_overview_html,
            rhk_plots_html,
            import_status_html,
            modules_cards_html,
        ]

        btn_generate_top.click(_generate, inputs=[state_flags, state_pmods_selected, state_docx_cur, state_docx_prev] + input_components, outputs=generate_outputs)\
            .then(_apply_pmods_values, inputs=[state_pmods_selected], outputs=[modules_lvl1_comp, modules_lvl2_comp, modules_lvl3_comp])
        btn_generate_bottom.click(_generate, inputs=[state_flags, state_pmods_selected, state_docx_cur, state_docx_prev] + input_components, outputs=generate_outputs)\
            .then(_apply_pmods_values, inputs=[state_pmods_selected], outputs=[modules_lvl1_comp, modules_lvl2_comp, modules_lvl3_comp])
        # --- Live status update (debounced client ping) ---
        # Instead of attaching a .change handler to dozens of inputs (slow + triggers during bulk programmatic updates),
        # we use ONE hidden textbox that the browser updates (debounced) whenever the user edits any input.
        # Procedere/Module are handled by _update_procedere_only and therefore excluded from the client ping.
        def _on_dirty_ping(flags_state, case_state, _ping_val: str):
            flags = dict(flags_state or {})

            flags["dirty"] = True
            if bool(flags.get("has_report")):
                flags["report_stale"] = True

            # Keep warnings from last generation for visibility; do not recompute.
            try:
                if "warnings" not in flags or flags.get("warnings") is None:
                    flags["warnings"] = (case_state or {}).get("warnings") or []
                else:
                    flags["warnings"] = list(flags.get("warnings") or [])
            except Exception:
                flags["warnings"] = []

            case_for_ui = case_state if isinstance(case_state, dict) else None
            return flags, build_sticky_summary_html(case_for_ui, flags)

        try:
            dirty_ping.change(
                _on_dirty_ping,
                inputs=[state_flags, state_case, dirty_ping],
                outputs=[state_flags, sticky_summary_html],
                trigger_mode="always_last",
                queue=False,
            )
        except TypeError:
            dirty_ping.change(
                _on_dirty_ping,
                inputs=[state_flags, state_case, dirty_ping],
                outputs=[state_flags, sticky_summary_html],
            )


        # --- Live-Update: Procedere/Module sollen deterministisch im Bericht landen ---
        # Häufiger UX-Fehler: User ändert Module/Freitext nach dem Generieren und erwartet, dass der Bericht folgt.
        # Wir aktualisieren daher den Bericht direkt aus dem bestehenden Case-State, ohne alle Ableitungen neu zu rechnen.
        def _update_procedere_only(flags_state, case_state, m1, m2, m3, free_text):
            if not case_state:
                # Noch kein Fall generiert – nichts zu aktualisieren.
                return (
                    gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),  # doc, pat, echo_doc, echo_pat, int, summary
                    gr.update(), gr.update(), gr.update(),  # copy payloads (plain)
                    gr.update(), gr.update(), gr.update(),  # copy payloads (html)
                    gr.update(),  # copy feedback
                    None,  # state_case
                    dict(flags_state or {}),  # state_flags
                    build_sticky_summary_html(None, dict(flags_state or {})),
                    gr.update(),
                )
            flags = dict(flags_state or {})
            try:
                ui = dict(case_state.get("ui") or {})
                ui["modules_lvl1"] = m1 or []
                ui["modules_lvl2"] = m2 or []
                ui["modules_lvl3"] = m3 or []
                ui["procedere_free"] = free_text or ""
                ui["modules"] = _normalize_module_ids(
                    (ui.get("modules_lvl1") or []) + (ui.get("modules_lvl2") or []) + (ui.get("modules_lvl3") or [])
                )
                case_state["ui"] = ui

                doc = build_doctor_report(case_state, blocks)
                pat = build_patient_report(case_state)
                echo_doc = build_echo_doctor_report_extended(case_state)
                echo_pat = build_echo_patient_report(case_state)
                internal = build_internal_report(case_state)

                # Structured summary + debug
                try:
                    summary_dict = build_summary_dict(case_state, rulebook_meta)
                    case_state["summary"] = summary_dict
                    summary_json = json.dumps(summary_dict, ensure_ascii=False, indent=2)
                except Exception:
                    summary_json = "{}"
                dbg = json.dumps(case_state, ensure_ascii=False, indent=2)
                # Copy/paste payloads
                # - plain text for systems that break on rich formatting
                # - HTML for Word (clipboard text/html)
                try:
                    doc_plain = markdown_to_plain(doc)
                    pat_plain = markdown_to_plain(pat)
                    rhk_section = extract_markdown_section(doc, "Rechtsherzkatheter", "Beurteilung")
                    rhk_plain = markdown_to_plain(rhk_section)

                    doc_html = markdown_to_word_html(doc)
                    pat_html = markdown_to_word_html(pat)
                    rhk_html = markdown_to_word_html(rhk_section)
                except Exception:
                    doc_plain = ""
                    pat_plain = ""
                    rhk_plain = ""
                    doc_html = ""
                    pat_html = ""
                    rhk_html = ""

                cards_html = build_p_module_cards_html(blocks, case_state)

                # Status: report stays current (we just updated it), but changes are unsaved
                flags["dirty"] = True
                flags["has_report"] = True
                flags["report_stale"] = False
                try:
                    flags["warnings"] = case_state.get("warnings") or []
                except Exception:
                    flags["warnings"] = []

                sticky = build_sticky_summary_html(case_state, flags)
                return (
                    doc,
                    pat,
                    echo_doc,
                    echo_pat,
                    internal,
                    summary_json,
                    dbg,
                    doc_plain,
                    pat_plain,
                    rhk_plain,
                    doc_html,
                    pat_html,
                    rhk_html,
                    "",  # copy feedback reset
                    case_state,
                    flags,
                    sticky,
                    cards_html,
                )
            except Exception:
                # Fail-safe: do not break UI on minor issues
                sticky = build_sticky_summary_html(case_state, flags)
                return (
                    gr.update(), gr.update(), gr.update(), gr.update(), gr.update(),
                    gr.update(), gr.update(), gr.update(),
                    gr.update(), gr.update(), gr.update(),
                    gr.update(),
                    case_state,
                    flags,
                    sticky,
                    gr.update(),
                )

        _procedere_inputs = [state_flags, state_case, modules_lvl1_comp, modules_lvl2_comp, modules_lvl3_comp, field_components["procedere_free"]]
        _procedere_outputs = [
            out_doc, out_pat, out_echo_doc, out_echo_pat, out_int,
            out_summary_json,
            out_json,
            copy_doc_plain, copy_pat_plain, copy_rhk_plain,
            copy_doc_html, copy_pat_html, copy_rhk_html,
            copy_feedback,
            state_case,
            state_flags,
            sticky_summary_html,
            modules_cards_html,
        ]

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

        def _load_example_ui():
            ui = random_example()

            # --- P-Module preselection (robust & leak-free) ---
            # Important: On example load we must NOT set CheckboxGroup values to non-existing choices.
            # Otherwise Gradio can throw "Value ... is not in list of choices" BEFORE we get to update choices.
            # Strategy:
            #   1) Extract desired selection into state_pmods_selected (IDs or labels are OK).
            #   2) Force UI checkbox values to [] for the first stage.
            #   3) _generate() will merge pmods_state into raw['modules'] and compute valid choices.
            #   4) _apply_pmods_values() sets the checkbox values after choices are updated.
            pending = {
                "lvl1": ui.get("modules_lvl1") or [],
                "lvl2": ui.get("modules_lvl2") or [],
                "lvl3": ui.get("modules_lvl3") or (ui.get("modules") or []),
            }

            # Ensure previous example selections do not leak into the UI stage
            ui["modules_lvl1"] = []
            ui["modules_lvl2"] = []
            ui["modules_lvl3"] = []

            vals = apply_ui_to_components(ui)
            return (*vals, pending)

        def _reset_flags_after_load():
            # New loaded example/file should be treated as clean until user edits.
            return {"dirty": False, "saved_at": None, "has_report": False, "report_stale": False, "warnings": []}

        def _reset_docx_states():
            return None, None


        
        def _reset_echo_import_states():
            echo_pdf_cur_reset = gr.update(value=None)
            echo_preview_cur_reset = "<div class='docx-muted'>Noch kein Echo-PDF importiert.</div>"
            echo_state_cur_reset = {"parsed": None, "meta": None}

            echo_pdf_prev_reset = gr.update(value=None)
            echo_preview_prev_reset = "<div class='docx-muted'>Noch kein Vor-Echo importiert.</div>"
            echo_state_prev_reset = {"parsed": None, "meta": None}

            echo_compare_reset = "<div class='docx-muted'>Kein Echo-Vergleich (Vor-Echo und/oder aktuelles Echo fehlt).</div>"

            return (
                echo_pdf_cur_reset,
                echo_preview_cur_reset,
                echo_state_cur_reset,
                echo_pdf_prev_reset,
                echo_preview_prev_reset,
                echo_state_prev_reset,
                echo_compare_reset,
            )

        btn_example_top.click(_load_example_ui, inputs=[], outputs=input_components + [state_pmods_selected])\
            .then(_reset_flags_after_load, inputs=[], outputs=[state_flags])\
            .then(_reset_docx_states, inputs=[], outputs=[state_docx_cur, state_docx_prev])\
            .then(_reset_echo_import_states, inputs=[], outputs=[import_pdf_cur, import_preview_cur_html, state_echo_cur, import_pdf_prev, import_preview_prev_html, state_echo_prev, compare_echo_html])\
            .then(_generate, inputs=[state_flags, state_pmods_selected, state_docx_cur, state_docx_prev] + input_components, outputs=generate_outputs)\
            .then(_apply_pmods_values, inputs=[state_pmods_selected], outputs=[modules_lvl1_comp, modules_lvl2_comp, modules_lvl3_comp])
        btn_example_bottom.click(_load_example_ui, inputs=[], outputs=input_components + [state_pmods_selected])\
            .then(_reset_flags_after_load, inputs=[], outputs=[state_flags])\
            .then(_reset_docx_states, inputs=[], outputs=[state_docx_cur, state_docx_prev])\
            .then(_reset_echo_import_states, inputs=[], outputs=[import_pdf_cur, import_preview_cur_html, state_echo_cur, import_pdf_prev, import_preview_prev_html, state_echo_prev, compare_echo_html])\
            .then(_generate, inputs=[state_flags, state_pmods_selected, state_docx_cur, state_docx_prev] + input_components, outputs=generate_outputs)\
            .then(_apply_pmods_values, inputs=[state_pmods_selected], outputs=[modules_lvl1_comp, modules_lvl2_comp, modules_lvl3_comp])


        # --- Clear all (Befunde leeren) ---
        # Reset inputs to safe defaults and clear all outputs/state.
        # IMPORTANT: Must return exactly len(load_outputs) values.
        load_outputs = [*input_components, *generate_outputs, import_pdf_cur, import_preview_cur_html, state_echo_cur, import_pdf_prev, import_preview_prev_html, state_echo_prev, compare_echo_html]

        def _clear_all():
            # Inputs: build empty UI dict and let apply_ui_to_components normalize legacy/defaults.
            empty_ui = {k: None for k in input_keys}
            for lk in ("meds", "comorbidities", "modules", "modules_lvl1", "modules_lvl2", "modules_lvl3"):
                if lk in empty_ui:
                    empty_ui[lk] = []
            # Dropdowns that must never be invalid (avoid "value not in choices" crashes)
            empty_ui["anticoag_indication"] = "keine Angabe"

            vals = apply_ui_to_components(empty_ui)

            flags0 = {"dirty": False, "saved_at": None, "has_report": False, "report_stale": False, "warnings": []}

            # Reset module UI deterministically
            modules_lvl1_update = gr.update(choices=[], value=[])
            modules_lvl2_update = gr.update(choices=[], value=[])
            modules_lvl3_update = gr.update(choices=base_module_choices, value=[])

            # Outputs (mirror generate_outputs order)
            cleared_outputs = (
                None, None, None, None, None, None,  # auto_mpap..auto_dpg
                build_dashboard_html(None),           # dashboard
                "", "", "", "", "",                    # out_doc, out_pat, out_echo_doc, out_echo_pat, out_int
                "{}",                                 # out_summary_json
                "{}",                                 # out_json
                "", "", "",                           # copy_*_plain
                "", "", "",                           # copy_*_html
                "",                                   # copy_feedback
                None,                                 # state_case
                flags0,                                # state_flags
                {"lvl1": [], "lvl2": [], "lvl3": []},  # state_pmods_selected
                None,                                 # state_docx_cur
                None,                                 # state_docx_prev
                modules_lvl1_update,
                modules_lvl2_update,
                modules_lvl3_update,
                "",                                   # modules_disabled_html
                build_sticky_summary_html(None, flags0),
                "",                                   # compare_overview_html
                "",                                   # rhk_plots_html
                "",                                   # import_status_html
                "",                                   # modules_cards_html
            )
            echo_pdf_cur_reset = gr.update(value=None)
            echo_preview_cur_reset = "<div class='docx-muted'>Noch kein Echo-PDF importiert.</div>"
            echo_state_cur_reset = {"parsed": None, "meta": None}

            echo_pdf_prev_reset = gr.update(value=None)
            echo_preview_prev_reset = "<div class='docx-muted'>Noch kein Vor-Echo importiert.</div>"
            echo_state_prev_reset = {"parsed": None, "meta": None}

            echo_compare_reset = "<div class='docx-muted'>Kein Echo-Vergleich (Vor-Echo und/oder aktuelles Echo fehlt).</div>"

            return (
                *vals,
                *cleared_outputs,
                echo_pdf_cur_reset,
                echo_preview_cur_reset,
                echo_state_cur_reset,
                echo_pdf_prev_reset,
                echo_preview_prev_reset,
                echo_state_prev_reset,
                echo_compare_reset,
            )

        try:
            btn_clear_top.click(_clear_all, inputs=[], outputs=load_outputs, queue=False)
            btn_clear_bottom.click(_clear_all, inputs=[], outputs=load_outputs, queue=False)
        except TypeError:
            # Older Gradio builds may not support queue=...
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
            flags0 = {"dirty": False, "saved_at": None, "has_report": False, "report_stale": False, "warnings": []}
            return (
                *vals,
                None, None, None, None, None, None,   # auto_* (6)
                dash,
                "", "", "", "", "",              # doc, patient, echo doc, echo patient, internal
                "{}",                                # out_summary_json
                "{}",                                # out_json
                "", "", "",                         # copy payloads
                "",                                  # copy feedback
                None,                                 # state_case
                flags0,                               # state_flags
                {"lvl1": [], "lvl2": [], "lvl3": []},   # state_pmods_selected
                modules_lvl1_update, modules_lvl2_update, modules_lvl3_update,
                "",                                  # disabled html
                build_sticky_summary_html(None, flags0),  # sticky summary
                "",                                  # compare overview
                "",                                  # module cards
            )

        def _save_case(case_state, flags_state):
            # Save should never throw a Gradio "Error" banner.
            # Local/Desktop: ask user for a folder (native dialog) and save there.
            # Web/Cloud: provide downloadable files via gr.File components.

            if not case_state:
                # Hide both downloads
                return (
                    gr.update(visible=False, value=None),
                    gr.update(visible=False, value=None),
                    dict(flags_state or {}),
                    build_sticky_summary_html(None, dict(flags_state or {})),
                    "",
                )

            flags = dict(flags_state or {})
            ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")

            def _is_cloud_env() -> bool:
                # Render/Cloud environments usually set PORT.
                return bool(os.environ.get("PORT")) or bool(os.environ.get("RENDER")) or bool(os.environ.get("K_SERVICE"))

            # Decide target directory
            target_dir = None
            if not _is_cloud_env() and os.environ.get("RHK_SAVE_MODE", "").lower() != "download":
                # Local mode: use native folder picker if available
                try:
                    import tkinter as _tk
                    from tkinter import filedialog as _filedialog

                    root = _tk.Tk()
                    root.withdraw()
                    try:
                        root.attributes("-topmost", True)
                    except Exception:
                        pass

                    target_dir = _filedialog.askdirectory(title="Ordner zum Speichern auswählen")
                    try:
                        root.destroy()
                    except Exception:
                        pass

                    if not target_dir:
                        return (
                            gr.update(visible=False, value=None),
                            gr.update(visible=False, value=None),
                            flags,
                            build_sticky_summary_html(case_state, flags),
                            "ℹ️ Speichern abgebrochen.",
                        )
                except Exception:
                    target_dir = None

            # Fallback: cross-platform temp directory (Windows has no /tmp)
            if not target_dir:
                try:
                    import tempfile
                    tmp_root = tempfile.gettempdir()
                    target_dir = os.path.join(tmp_root, "rhk_befunder")
                    os.makedirs(target_dir, exist_ok=True)
                except Exception:
                    target_dir = os.getcwd()

            case_path = os.path.join(target_dir, f"rhk_case_{ts}.json")
            summary_path = os.path.join(target_dir, f"rhk_summary_{ts}.json")

            # Ensure summary is present
            try:
                summary_dict = case_state.get("summary")
                if not isinstance(summary_dict, dict) or not summary_dict:
                    summary_dict = build_summary_dict(case_state, rulebook_meta)
                    case_state["summary"] = summary_dict
            except Exception:
                summary_dict = {}

            try:
                export_json(case_state, case_path)
                export_summary_json(summary_dict, summary_path)
            except Exception as e:
                # Do not crash the UI; show a clear message and keep downloads hidden.
                return (
                    gr.update(visible=False, value=None),
                    gr.update(visible=False, value=None),
                    flags,
                    build_sticky_summary_html(case_state, flags),
                    f"❌ Speichern fehlgeschlagen: {type(e).__name__}: {e}",
                )

            flags["dirty"] = False
            flags["saved_at"] = _dt.datetime.now().isoformat(timespec="seconds")
            try:
                flags["warnings"] = case_state.get("warnings") or []
            except Exception:
                pass

            sticky = build_sticky_summary_html(case_state, flags)
            # Provide downloads as well (user can choose location in browser download dialog).
            return (
                gr.update(visible=True, value=case_path),
                gr.update(visible=True, value=summary_path),
                flags,
                sticky,
                "✅ Gespeichert. (Bei Bedarf über die Download-Links herunterladen.)",
            )

        _save_outputs = [file_out, file_summary_out, state_flags, sticky_summary_html, copy_feedback]

        save_btn_top.click(_save_case, inputs=[state_case, state_flags], outputs=_save_outputs)
        save_btn_bottom.click(_save_case, inputs=[state_case, state_flags], outputs=_save_outputs)

        # --- Load case ---

        def _load_case_ui(file):
            # Returns values for: input_components + [state_pmods_selected]
            empty_pending = {"lvl1": [], "lvl2": [], "lvl3": []}
            if file is None:
                return [c.value for c in input_components] + [empty_pending]
            try:
                import json as _json
                with open(file.name, "r", encoding="utf-8") as f:
                    data = _json.load(f)
            except Exception:
                data = {}

            ui_dict = data.get("ui") if isinstance(data, dict) and "ui" in data else data
            if not isinstance(ui_dict, dict):
                ui_dict = {}

            # Extract desired P-module selection (legacy-friendly)
            pending = {
                "lvl1": ui_dict.get("modules_lvl1") or [],
                "lvl2": ui_dict.get("modules_lvl2") or [],
                "lvl3": ui_dict.get("modules_lvl3") or (ui_dict.get("modules") or []),
            }

            # Avoid Gradio choice-errors during stage-1 load: keep UI checkbox values empty.
            ui_dict["modules_lvl1"] = []
            ui_dict["modules_lvl2"] = []
            ui_dict["modules_lvl3"] = []

            vals = apply_ui_to_components(ui_dict)
            return (*vals, pending)

        


        # -------------------------
        # DOCX Import (Mac-Lab)
        # -------------------------
        DOCX_WIPE_CURRENT = {
            # rest hemo
            "spap_rest": None, "dpap_rest": None, "mpap_rest": None, "pawp_rest": None, "rap_rest": None,
            "co_rest": None, "ci_rest": None, "pvr_rest": None, "co_method": None,
            # exercise
            "exercise_done": False,
            "spap_peak": None, "dpap_peak": None, "mpap_peak": None, "pawp_peak": None,
            "co_peak": None, "ci_peak": None,
            # volume
            "volume_challenge_done": False,
            "pawp_pre": None, "pawp_post": None, "mpap_pre": None, "mpap_post": None,
            # vaso
            "vaso_test_done": False,
            "vaso_agent": "", "vaso_response_desc": "",
            "vaso_mpap_pre": None, "vaso_co_pre": None, "vaso_mpap_post": None, "vaso_co_post": None,
            # oximetry
            "sat_svc": None, "sat_ivc": None, "sat_ra": None, "sat_rv": None, "sat_pa": None, "sat_ao": None,
            # vitals
            "bp_sys": None, "bp_dia": None, "bp_mean": None, "hr": None, "spo2": None,
        }

        DOCX_WIPE_PREV = {
            "prev_rhk_date": "",
            "prev_spap": None, "prev_dpap": None, "prev_mpap": None, "prev_pawp": None, "prev_rap": None,
            "prev_co": None, "prev_ci": None, "prev_pvr": None,
        }

        FILL_FROM_PREV_IF_MISSING = ["age", "sex", "height_cm", "weight_kg", "hb_g_dl"]

        def _docx_import_current(file, *vals):
            # HARD-RESET: prevent stale values from previous cases from leaking into the report.
            # This is essential to avoid 'Phantasiebefunde' after importing a new DOCX.
            import copy
            ui_dict = copy.deepcopy(DEFAULT_UI)
            # Avoid Gradio choice-errors during stage-1 load: keep module UI checkbox values empty.
            ui_dict["modules"] = []
            ui_dict["modules_lvl1"] = []
            ui_dict["modules_lvl2"] = []
            ui_dict["modules_lvl3"] = []

            payload = parse_maclab_docx(file.name if hasattr(file, "name") else str(file))
            updates = map_payload_to_ui(payload, target="current")
            ui_dict.update(updates)

            vals_out = apply_ui_to_components(ui_dict)
            return (*vals_out, payload)

        def _docx_import_prev(file, *vals):
            ui_dict = ui_get_raw(*vals)
            for k, v in DOCX_WIPE_PREV.items():
                ui_dict[k] = v

            payload = parse_maclab_docx(file.name if hasattr(file, "name") else str(file))
            updates_prev = map_payload_to_ui(payload, target="prev")
            ui_dict.update(updates_prev)

            # Option: aus Vor-RHK fehlende Demografie/Laborwerte ergänzen (nur wenn aktuell leer)
            updates_cur = map_payload_to_ui(payload, target="current")
            for k in FILL_FROM_PREV_IF_MISSING:
                if (ui_dict.get(k) in (None, "", 0)) and (updates_cur.get(k) is not None):
                    ui_dict[k] = updates_cur.get(k)

            vals_out = apply_ui_to_components(ui_dict)
            return (*vals_out, payload)


        def _reset_pmods_after_import():
            # Reset pending module selection to avoid stale templates influencing a new import.
            return {"lvl1": [], "lvl2": [], "lvl3": []}

        docx_btn_top.upload(_docx_import_current, inputs=[docx_btn_top] + input_components, outputs=input_components + [state_docx_cur])\
            .then(_reset_pmods_after_import, inputs=[], outputs=[state_pmods_selected])\
            .then(_reset_flags_after_load, inputs=[], outputs=[state_flags])\
            .then(_generate, inputs=[state_flags, state_pmods_selected, state_docx_cur, state_docx_prev] + input_components, outputs=generate_outputs)\
            .then(_apply_pmods_values, inputs=[state_pmods_selected], outputs=[modules_lvl1_comp, modules_lvl2_comp, modules_lvl3_comp])

        docx_btn_bottom.upload(_docx_import_current, inputs=[docx_btn_bottom] + input_components, outputs=input_components + [state_docx_cur])\
            .then(_reset_pmods_after_import, inputs=[], outputs=[state_pmods_selected])\
            .then(_reset_flags_after_load, inputs=[], outputs=[state_flags])\
            .then(_generate, inputs=[state_flags, state_pmods_selected, state_docx_cur, state_docx_prev] + input_components, outputs=generate_outputs)\
            .then(_apply_pmods_values, inputs=[state_pmods_selected], outputs=[modules_lvl1_comp, modules_lvl2_comp, modules_lvl3_comp])

        prev_docx_btn.upload(_docx_import_prev, inputs=[prev_docx_btn] + input_components, outputs=input_components + [state_docx_prev])\
            .then(_reset_flags_after_load, inputs=[], outputs=[state_flags])\
            .then(_generate, inputs=[state_flags, state_pmods_selected, state_docx_cur, state_docx_prev] + input_components, outputs=generate_outputs)\
            .then(_apply_pmods_values, inputs=[state_pmods_selected], outputs=[modules_lvl1_comp, modules_lvl2_comp, modules_lvl3_comp])

        load_btn_top.upload(_load_case_ui, inputs=[load_btn_top], outputs=input_components + [state_pmods_selected])\
            .then(_reset_flags_after_load, inputs=[], outputs=[state_flags])\
            .then(_reset_docx_states, inputs=[], outputs=[state_docx_cur, state_docx_prev])\
            .then(_reset_echo_import_states, inputs=[], outputs=[import_pdf_cur, import_preview_cur_html, state_echo_cur, import_pdf_prev, import_preview_prev_html, state_echo_prev, compare_echo_html])\
            .then(_generate, inputs=[state_flags, state_pmods_selected, state_docx_cur, state_docx_prev] + input_components, outputs=generate_outputs)\
            .then(_apply_pmods_values, inputs=[state_pmods_selected], outputs=[modules_lvl1_comp, modules_lvl2_comp, modules_lvl3_comp])

        load_btn_bottom.upload(_load_case_ui, inputs=[load_btn_bottom], outputs=input_components + [state_pmods_selected])\
            .then(_reset_flags_after_load, inputs=[], outputs=[state_flags])\
            .then(_reset_docx_states, inputs=[], outputs=[state_docx_cur, state_docx_prev])\
            .then(_reset_echo_import_states, inputs=[], outputs=[import_pdf_cur, import_preview_cur_html, state_echo_cur, import_pdf_prev, import_preview_prev_html, state_echo_prev, compare_echo_html])\
            .then(_generate, inputs=[state_flags, state_pmods_selected, state_docx_cur, state_docx_prev] + input_components, outputs=generate_outputs)\
            .then(_apply_pmods_values, inputs=[state_pmods_selected], outputs=[modules_lvl1_comp, modules_lvl2_comp, modules_lvl3_comp])
        # Copy-to-Word buttons are handled by the HEAD script (cross-browser; no Gradio _js dependency).


    return demo, CSS, theme