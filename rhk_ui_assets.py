#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI assets for RHK Befundassistent.

Contains:
- CSS
- JavaScript (on-load handlers)
- HTML header injections

Split out of rhk_ui.py to keep the main UI module focused on layout and bindings.
"""

from __future__ import annotations

import os

# NOTE: Everything below is copied from the original monolithic rhk_ui.py.
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
  top: 170px;
  z-index: 10001;
  max-width: 1600px;
  margin: 0 auto 10px;
  padding: 0 24px;
}

/* ------------------------------------------------------------------
   Pre-Cath Safety Header (second sticky bar under hemodynamics)
   ------------------------------------------------------------------ */

#rhk_pre_cath_home_wrapper{
  position: sticky;
  top: 118px; /* above summarybar */
  z-index: 10002;
  max-width: 1600px;
  margin: 0 auto 8px;
  padding: 0 24px;
}

#rhk_pre_cath_wrapper{
  position: sticky;
  top: 170px; /* below summarybar */
  z-index: 10000;
  max-width: 1600px;
  margin: 0 auto 10px;
  padding: 0 24px;
}
#rhk_pre_cath_wrapper .rhk-pre-cath-bar{
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

# Backwards-compatible alias: some modules may import `JS`.
JS = JS_ON_LOAD
