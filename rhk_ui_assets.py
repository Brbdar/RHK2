#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Refactor v1.51: rhk_ui_assets.py - Quick-Navigation + Tab-UX-Performance (leichteres Observer-/Overflow-Handling)
# Refactor v1.50: rhk_ui_assets.py - Apple-inspirierter Design-Refresh (Design-Tokens, visuelle Hierarchie, Controls/Tabs/Cards modernisiert)
# Refactor v1.47: rhk_ui_assets.py - Workflow-Übersicht Styling + Tab-Subtitle Mapping für nummerierte Tabs
# Refactor v1.38: rhk_ui_assets.py - Hosted hotfix: force-enable Browser-OCR/PDF + CDN in cloud runtimes unless OFFLINE/PRIVACY (fixes "Browser-OCR deaktiviert" despite deploy)
# Refactor v1.37: rhk_ui_assets.py - Browser-OCR/PDF default-on (online), robust env parsing (blank->default), CDN fallback on unless RHK_OFFLINE/RHK_PRIVACY_MODE
# Refactor v1.24: rhk_ui_assets.py - Datenschutz: keine externen CDN-Assets default, Browser-Import optional, OCR/PDF Loader gehärtet



"""UI assets for RHK Befundassistent.

Contains:
- CSS
- JavaScript (on-load handlers)
- HTML header injections

Refactor v1.38
- Hosted hotfix: In Cloud-Runtimes werden Browser-PDF/OCR + CDN-Fallback standardmäßig erzwungen aktiv,
  um „deaktiviert“ durch persistente/alte Env-Vars zu verhindern.
  Opt-out: `RHK_FORCE_HOSTED_BROWSER_TOOLS=0` oder OFFLINE/PRIVACY.

Refactor v1.37
- Online Defaults: Browser-PDF + Browser-OCR sind standardmäßig aktiv (auch on-prem/online), sofern nicht explizit deaktiviert.
- Robust env parsing: leere Env-Werte gelten als *nicht gesetzt* (fallback auf Default).
- Performance: Tesseract wird lazy-loaded (kein Heavy-Load beim App-Start).
- Debuggability: UI-Gating entspricht realer Asset-Policy (Vendor oder CDN).

Refactor v1.24
- Privacy-by-default: keine externen CDN-Assets ohne explizite Freigabe (RHK_ALLOW_CDN_ASSETS=1).
- Browser-Import (PDF.js / Tesseract.js) optional und UI-seitig detektierbar.
- Robustere, deterministische Client-Hooks (kein stilles Failover zu externen Quellen).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from rhk_i18n import dump_ui_i18n_payload

# -----------------------------------------------------------------------------
# Runtime detection (for safe defaults in hosted deployments)
# -----------------------------------------------------------------------------
IS_RENDER_NATIVE: bool = bool(os.environ.get("RENDER_SERVICE_ID") or os.environ.get("RENDER"))
# NOTE: "Online" deployments are not limited to Render/HF. Many platforms set PORT.
IS_CLOUD_RUNTIME: bool = bool(
    IS_RENDER_NATIVE
    or os.environ.get("SPACE_ID")
    or os.environ.get("HF_SPACE")
    or os.environ.get("KAGGLE_URL_BASE")
    or os.environ.get("PORT")
)


def _env_flag(key: str, default: str) -> bool:
    """Parse a boolean env var with an explicit default.

    Safety/ops principle:
    - If the variable is *unset*: use the provided default.
    - If the variable exists but is an empty string: treat as unset (use default).
    - Otherwise: parse usual boolean strings.

    This avoids accidental "disable" when hosted platforms inject empty env vars.
    """
    if key in os.environ:
        raw = os.environ.get(key)
        if raw is None or str(raw).strip() == "":
            raw = default
    else:
        raw = default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


# -----------------------------------------------------------------------------
# Asset policy (clinical defaults)
# -----------------------------------------------------------------------------
# Clinical default: do NOT load external JS/CSS from CDNs (privacy + reproducibility).
# Hosted demo runtimes (Render/HF) default to enabling browser import + OCR so the
# Echo OCR/PDF tools work out-of-the-box unless explicitly disabled via env vars.
# Optional: force-disable all network-delivered browser import features (strict offline/privacy mode).
# If enabled, browser-side PDF/OCR features are gated off and CDN fallback is disabled.
OFFLINE_MODE: bool = bool(
    _env_flag("RHK_OFFLINE", "0")
    or _env_flag("RHK_OFFLINE_MODE", "0")
    or _env_flag("RHK_PRIVACY_MODE", "0")
)

# Defaults:
# - Online (default): enable browser import + OCR and allow CDN fallback (vendor-first).
# - Offline/privacy mode: disable these by default.
DEFAULT_ALLOW_CDN: str = "0" if OFFLINE_MODE else "1"
DEFAULT_BROWSER_IMPORT: str = "0" if OFFLINE_MODE else "1"
DEFAULT_BROWSER_OCR: str = "0" if OFFLINE_MODE else "1"

ALLOW_CDN_ASSETS: bool = _env_flag("RHK_ALLOW_CDN_ASSETS", DEFAULT_ALLOW_CDN)
ENABLE_BROWSER_IMPORT: bool = _env_flag("RHK_ENABLE_BROWSER_IMPORT", DEFAULT_BROWSER_IMPORT)
ENABLE_BROWSER_OCR: bool = _env_flag("RHK_ENABLE_BROWSER_OCR", DEFAULT_BROWSER_OCR)

# Optional: preload heavy OCR engine on initial page load (not recommended).
PRELOAD_TESSERACT: bool = _env_flag("RHK_PRELOAD_TESSERACT", "0")
_HERE = Path(__file__).resolve().parent
_HAS_VENDOR_PDFJS = (_HERE / "assets" / "vendor" / "pdf" / "pdf.min.js").exists() and (_HERE / "assets" / "vendor" / "pdf" / "pdf.worker.min.js").exists()
_HAS_VENDOR_TESSERACT = (_HERE / "assets" / "vendor" / "tesseract" / "tesseract.min.js").exists()

# -----------------------------------------------------------------------------
# Hosted hotfix
# -----------------------------------------------------------------------------
# Some hosted platforms keep old env vars (often set to "0") across deploys.
# In those cases the UI would show "Browser-OCR deaktiviert" even though the
# intent is to have OCR available online.
#
# Policy v1.38:
# - If we are in a cloud runtime AND we are not in OFFLINE/PRIVACY mode,
#   we force-enable browser import + OCR and allow CDN fallback by default.
# - Operators can explicitly opt out via: RHK_FORCE_HOSTED_BROWSER_TOOLS=0
FORCE_HOSTED_BROWSER_TOOLS: bool = _env_flag("RHK_FORCE_HOSTED_BROWSER_TOOLS", "1")
if IS_CLOUD_RUNTIME and (not OFFLINE_MODE) and FORCE_HOSTED_BROWSER_TOOLS:
    ENABLE_BROWSER_IMPORT = True
    ENABLE_BROWSER_OCR = True
    ALLOW_CDN_ASSETS = True

# Exposed flags for Python-side UI gating (rhk_ui_echo).
BROWSER_PDF_IMPORT_AVAILABLE: bool = bool(_HAS_VENDOR_PDFJS or ALLOW_CDN_ASSETS)
BROWSER_OCR_AVAILABLE: bool = bool(_HAS_VENDOR_TESSERACT or ALLOW_CDN_ASSETS)

# URL lists for the JS loader (local first).
_PDFJS_URLS: list[str] = []
_PDFJS_WORKER_URLS: list[str] = []
_TESSERACT_URLS: list[str] = []

# Local vendor assets first (offline/on-prem friendly).
if _HAS_VENDOR_PDFJS:
    _PDFJS_URLS.append("/file=assets/vendor/pdf/pdf.min.js")
    _PDFJS_WORKER_URLS.append("/file=assets/vendor/pdf/pdf.worker.min.js")
if _HAS_VENDOR_TESSERACT:
    _TESSERACT_URLS.append("/file=assets/vendor/tesseract/tesseract.min.js")
if ALLOW_CDN_ASSETS:
    _PDFJS_URLS += [
        "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.10.38/pdf.min.js",
        "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.min.js",
        "https://unpkg.com/pdfjs-dist@4.10.38/build/pdf.min.js",
    ]
    _PDFJS_WORKER_URLS += [
        "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.10.38/pdf.worker.min.js",
        "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.worker.min.js",
        "https://unpkg.com/pdfjs-dist@4.10.38/build/pdf.worker.min.js",
    ]
    _TESSERACT_URLS += [
        "https://unpkg.com/tesseract.js@5.0.5/dist/tesseract.min.js",
    ]

# Inject URL arrays into the browser so the loader can stay static (no f-strings inside JS).
_ASSET_URLS_SCRIPT = "<script>" + \
    "window.RHK_PDFJS_URLS=" + json.dumps(_PDFJS_URLS) + ";" + \
    "window.RHK_PDFJS_WORKER_URLS=" + json.dumps(_PDFJS_WORKER_URLS) + ";" + \
    "window.RHK_TESSERACT_URLS=" + json.dumps(_TESSERACT_URLS) + ";" + \
    "window.RHK_ASSET_POLICY={allowCdn:" + ("true" if ALLOW_CDN_ASSETS else "false") + "};" + \
    "</script>"
_I18N_PAYLOAD_JSON = dump_ui_i18n_payload()
_I18N_SCRIPT = "<script>" + "window.RHK_I18N=" + _I18N_PAYLOAD_JSON + ";" + "</script>"

# Choose a single Tesseract script source (avoid multiple loads).
# By default we lazy-load Tesseract only when the user triggers OCR.
# Optional preload: set RHK_PRELOAD_TESSERACT=1.
_TESSERACT_SCRIPT_SRC: str | None = None
if PRELOAD_TESSERACT and ENABLE_BROWSER_IMPORT and ENABLE_BROWSER_OCR:
    if _HAS_VENDOR_TESSERACT:
        _TESSERACT_SCRIPT_SRC = _TESSERACT_URLS[0]
    elif ALLOW_CDN_ASSETS and len(_TESSERACT_URLS) > 1:
        _TESSERACT_SCRIPT_SRC = _TESSERACT_URLS[-1]
TESSERACT_SCRIPT_TAG: str = (f'<script src="{_TESSERACT_SCRIPT_SRC}"></script>' if _TESSERACT_SCRIPT_SRC else "")

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
        _ASSET_URLS_SCRIPT,
        _I18N_SCRIPT,
        # Client-side PDF text extraction (Echo PDFs) – keeps PHI on the client.
        # Asset policy: local vendor files first; optional CDN fallback only if explicitly enabled.
        r"""
<script>
(function(){
  const PDFJS_URLS = (window.RHK_PDFJS_URLS && window.RHK_PDFJS_URLS.length)
    ? window.RHK_PDFJS_URLS
    : ['/file=assets/vendor/pdf/pdf.min.js'];
  const WORKER_URLS = (window.RHK_PDFJS_WORKER_URLS && window.RHK_PDFJS_WORKER_URLS.length)
    ? window.RHK_PDFJS_WORKER_URLS
    : ['/file=assets/vendor/pdf/pdf.worker.min.js'];

  function loadScript(src){
    return new Promise((resolve,reject)=>{
      const s=document.createElement('script');
      s.src=src; s.async=true;
      s.onload=()=>resolve(true);
      s.onerror=()=>reject(new Error('Failed to load '+src));
      document.head.appendChild(s);
    });
  }

  async function ensurePdfJs(){
    if(window.pdfjsLib && window.pdfjsLib.getDocument) return;
    var loadedIdx = -1;
    for(var i=0;i<PDFJS_URLS.length;i++){
      var url = PDFJS_URLS[i];
      try{
        await loadScript(url);
        if(window.pdfjsLib && window.pdfjsLib.getDocument){
          loadedIdx = i;
          console.log('RHK: PDF.js loaded from', url);
          break;
        }
      }catch(e){ /* try next */ }
    }
    if(!(window.pdfjsLib && window.pdfjsLib.getDocument)){
      throw new Error('PDF.js nicht geladen. (Lokal + CDN fehlgeschlagen)');
    }
    try{
      if(window.pdfjsLib && window.pdfjsLib.GlobalWorkerOptions){
        // match worker to the source we loaded (local first, then CDN).
        var wi = (loadedIdx >= 0 && loadedIdx < WORKER_URLS.length) ? loadedIdx : 0;
        window.pdfjsLib.GlobalWorkerOptions.workerSrc = WORKER_URLS[wi];
      }
    }catch(e){}
  }

  window.rhkEnsurePdfJs = ensurePdfJs;
})();
</script>

""",
        # Client-side OCR engine loader (Tesseract.js) – lazy-load on demand (faster startup).
        r"""
<script>
(function(){
  const TESS_URLS = (window.RHK_TESSERACT_URLS && window.RHK_TESSERACT_URLS.length)
    ? window.RHK_TESSERACT_URLS
    : ['/file=assets/vendor/tesseract/tesseract.min.js'];

  function loadScript(src){
    return new Promise((resolve,reject)=>{
      const s=document.createElement('script');
      s.src=src; s.async=true;
      s.onload=()=>resolve(true);
      s.onerror=()=>reject(new Error('Failed to load '+src));
      document.head.appendChild(s);
    });
  }

  async function ensureTesseract(){
    if(window.Tesseract && window.Tesseract.recognize) return;
    for(var i=0;i<TESS_URLS.length;i++){
      var url=TESS_URLS[i];
      try{
        await loadScript(url);
        if(window.Tesseract && window.Tesseract.recognize){
          console.log('RHK: Tesseract loaded from', url);
          return;
        }
      }catch(e){ /* try next */ }
    }
    throw new Error('Tesseract.js nicht geladen. (Lokal + CDN fehlgeschlagen)');
  }

  window.rhkEnsureTesseract = ensureTesseract;
})();
</script>
""",
        # Client-side OCR for screenshot imports (keeps PHI on the client)
        # Optional browser OCR (Tesseract.js) – disabled by default; no CDN unless explicitly allowed.
        TESSERACT_SCRIPT_TAG,
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

  function _safeCssId(id){
    try {
      var s = String(id || '');
      if(window.CSS && CSS.escape) return CSS.escape(s);
      return s.replace(/[^a-zA-Z0-9_-]/g, '\\$&');
    } catch(e) {
      return String(id || '');
    }
  }

  var __rhkRootCache = { t: 0, roots: [], ttlMs: 4000 };
  function _invalidateRootCache(){
    try { __rhkRootCache.t = 0; __rhkRootCache.roots = []; } catch(e) {}
  }

  function _collectRoots(){
    try {
      var now = Date.now();
      if(__rhkRootCache.roots && __rhkRootCache.roots.length && (now - __rhkRootCache.t) < (__rhkRootCache.ttlMs || 4000)){
        return __rhkRootCache.roots;
      }
      var roots = [document];
      var seen = [document];
      var app = null;
      var scanFromIdx = 0;
      try { app = document.querySelector('gradio-app'); } catch(e) {}
      if(app && app.shadowRoot && seen.indexOf(app.shadowRoot) < 0){
        roots.push(app.shadowRoot);
        seen.push(app.shadowRoot);
        // Avoid scanning the full document tree when we already have gradio-app shadow root.
        scanFromIdx = 1;
      }
      for(var ri=scanFromIdx; ri<roots.length; ri++){
        var root = roots[ri];
        var hosts = [];
        try { hosts = root.querySelectorAll ? root.querySelectorAll('*') : []; } catch(e) { hosts = []; }
        for(var hi=0; hi<hosts.length; hi++){
          var sr = hosts[hi] && hosts[hi].shadowRoot;
          if(sr && seen.indexOf(sr) < 0){
            roots.push(sr);
            seen.push(sr);
          }
        }
      }
      __rhkRootCache = { t: now, roots: roots, ttlMs: (__rhkRootCache.ttlMs || 4000) };
      return roots;
    } catch(e) {
      return [document];
    }
  }

  function _deepQuerySelector(sel){
    if(!sel) return null;
    var roots = _collectRoots();
    for(var i=0;i<roots.length;i++){
      try {
        var hit = roots[i].querySelector(sel);
        if(hit) return hit;
      } catch(e) {}
    }
    return null;
  }

  function _deepQuerySelectorAll(sel){
    var out = [];
    if(!sel) return out;
    var seen = null;
    try { seen = new Set(); } catch(e) { seen = null; }
    var roots = _collectRoots();
    for(var i=0;i<roots.length;i++){
      try {
        var list = roots[i].querySelectorAll(sel) || [];
        for(var j=0;j<list.length;j++){
          var el = list[j];
          if(!el) continue;
          if(seen){
            if(seen.has(el)) continue;
            seen.add(el);
            out.push(el);
          } else if(out.indexOf(el) < 0){
            out.push(el);
          }
        }
      } catch(e) {}
    }
    return out;
  }

  function _findInEventPath(ev, sel){
    try {
      if(ev && typeof ev.composedPath === 'function'){
        var path = ev.composedPath() || [];
        for(var i=0;i<path.length;i++){
          var n = path[i];
          if(!n || n === window || n === document) continue;
          if(n.matches && n.matches(sel)) return n;
          if(n.closest){
            var c = n.closest(sel);
            if(c) return c;
          }
        }
      }
    } catch(e) {}
    try {
      var t = ev && ev.target;
      if(t && t.closest) return t.closest(sel);
    } catch(e) {}
    return null;
  }

  function byId(id){
    try {
      var direct = document.getElementById(id);
      if(direct) return direct;
    } catch(e) {}
    return _deepQuerySelector('#' + _safeCssId(id));
  }
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
    // Gradio can hot-replace DOM nodes; keep the handler robust across rerenders.
    try{
      if(window.__rhkCopyClickHandler){
        document.removeEventListener('click', window.__rhkCopyClickHandler, true);
      }
    }catch(e){}
	    window.__rhkCopyClickHandler = function(ev){
	      try {
	        var host = _findInEventPath(ev, '#btn_copy_doc, #btn_copy_pat, #btn_copy_rhk');
	        if(!host) return;
	        ev.preventDefault();
        // Do not stopPropagation: allow Gradio's internal UI bookkeeping to proceed.
        var isDoc = host.id === 'btn_copy_doc';
        var isPat = host.id === 'btn_copy_pat';
        var htmlId = isDoc ? 'copy_doc_html' : (isPat ? 'copy_pat_html' : 'copy_rhk_html');
        var plainId = isDoc ? 'copy_doc_plain' : (isPat ? 'copy_pat_plain' : 'copy_rhk_plain');
        var h = getTextboxValue(htmlId);
        var p = getTextboxValue(plainId);
        copyToClipboard(h, p);
      } catch(e) {
        setFeedback('⚠️ Konnte nicht automatisch kopieren.');
      }
    };
    document.addEventListener('click', window.__rhkCopyClickHandler, true);
  }

  function installCopyObserver(){
    if(window.__rhkCopyObserverInstalled) return;
    window.__rhkCopyObserverInstalled = true;
    try{
      var obs = new MutationObserver(function(){
        // Gradio may replace DOM nodes; ensure our delegated handler exists.
        installCopyDelegation();
      });
      obs.observe(document.documentElement || document.body, {childList:true, subtree:true});
    }catch(e){}
  }

  // ------------------------------------------------------------------
  // Tab UX helpers
  // - Subtitle below main tabs for orientation
  // - Small completion dots on tabs (filled vs empty)
  // ------------------------------------------------------------------
  var __rhkTabSubtitleMap = {
    '1. Klinik & Labor': 'Anamnese, Vorerkrankungen, Labor und Basisdaten',
    'Klinik & Labor': 'Anamnese, Vorerkrankungen, Labor und Basisdaten',
    '2. Bildgebung & Echo/CMR': 'CT, V/Q, Echo und CMR Befunde strukturiert erfassen',
    'Bildgebung & Echo/CMR': 'CT, V/Q, Echo und CMR Befunde strukturiert erfassen',
    '3. Lungenfunktion & CPET': 'Spirometrie, Bodyplethysmographie, Diffusion und CPET',
    'Lungenfunktion & CPET': 'Spirometrie, Bodyplethysmographie, Diffusion und CPET',
    'Lungenfunktion': 'Spirometrie, Bodyplethysmographie, Diffusion',
    '4. RHK': 'Invasive Hämodynamik in Ruhe und unter Belastung',
    'RHK': 'Invasive Hämodynamik in Ruhe und unter Belastung',
    '5. Weitere Befunde': '6MWD, NYHA, Scores und ergänzende klinische Parameter',
    'Weitere Befunde': '6MWD, NYHA, Scores und ergänzende klinische Parameter',
    '6. Procedere & Module': 'Empfehlungen, Module, Follow up und Dokumentation',
    'Procedere & Module': 'Empfehlungen, Module, Follow up und Dokumentation'
  };

  function _tabLabel(btn){
    try {
      if(btn && btn.getAttribute){
        var src = btn.getAttribute('data-rhk-i18n-source-label');
        if(src) return String(src).trim();
      }
      return (btn.textContent || '').trim();
    } catch(e) { return ''; }
  }

  function _normText(s){
    try {
      return String(s || '').replace(/\s+/g, ' ').trim().toLowerCase();
    } catch(e) { return ''; }
  }

  function _isMeaningfulValue(v){
    var s = _normText(v);
    if(!s) return false;
    if(
      s === '0' || s === '0.0' || s === '0,0' ||
      s === 'keine angabe' || s === 'noch nicht gefragt' ||
      s === 'unklar / nicht erhoben' || s === 'unklar' ||
      s === 'n/a' || s === 'na' || s === '-' || s === '—' ||
      s === 'none' || s === 'null' || s === 'nicht erhoben'
    ){
      return false;
    }
    return true;
  }

  function _isRelevantInputForProgress(el){
    try {
      if(!el) return false;
      if(el.closest && el.closest('.rhk-hidden-payload, .rhk-hidden-download, [hidden], [aria-hidden="true"]')) return false;
      var type = String(el.type || '').toLowerCase();
      if(type === 'hidden' || type === 'file' || type === 'button' || type === 'submit' || type === 'reset') return false;
      if(!!el.disabled) return false;
      return true;
    } catch(e) { return false; }
  }

  var __rhkPanelInputElsCache = Object.create(null);
  function _invalidatePanelInputElsCache(panelId){
    try {
      if(panelId){
        delete __rhkPanelInputElsCache[String(panelId)];
        return;
      }
      __rhkPanelInputElsCache = Object.create(null);
    } catch(e) {}
  }

  function _panelValueInputs(panel, cacheKey){
    try {
      if(!panel) return [];
      var key = String(cacheKey || panel.id || panel.getAttribute('aria-labelledby') || '');
      if(key && __rhkPanelInputElsCache[key]) return __rhkPanelInputElsCache[key];
      var all = Array.from(panel.querySelectorAll('input, textarea, select') || []);
      var filtered = all.filter(_isRelevantInputForProgress);
      if(key) __rhkPanelInputElsCache[key] = filtered;
      return filtered;
    } catch(e) {
      return [];
    }
  }

  function _panelHasAnyValue(panel, cacheKey){
    try {
      if(!panel) return false;
      var els = _panelValueInputs(panel, cacheKey);
      for(var i=0;i<els.length;i++){
        var el = els[i];
        if(!_isRelevantInputForProgress(el)) continue;

        var type = (el.type || '').toLowerCase();
        if(type === 'checkbox' || type === 'radio'){
          if(!!el.checked) return true;
          continue;
        }

        if(el.tagName && el.tagName.toLowerCase() === 'select'){
          if(_isMeaningfulValue(el.value)) return true;
          continue;
        }

        var v = (typeof el.value === 'string') ? el.value.trim() : el.value;
        if(_isMeaningfulValue(v)) return true;
      }
    } catch(e) {}
    return false;
  }

  var __rhkPanelFillCache = Object.create(null);
  function _invalidatePanelFillCache(panelId){
    try {
      if(panelId){
        delete __rhkPanelFillCache[String(panelId)];
        return;
      }
      __rhkPanelFillCache = Object.create(null);
    } catch(e) {}
  }

  function _markPanelDirtyFromEvent(ev){
    try {
      var panel = _findInEventPath(ev, '#rhk_input_tabs [role="tabpanel"], #rhk_input_tabs .tabitem');
      if(!panel) return;
      var pid = String(panel.id || panel.getAttribute('aria-labelledby') || '');
      if(!pid) return;
      var st = __rhkPanelFillCache[pid] || { value: false, dirty: false };
      st.dirty = true;
      __rhkPanelFillCache[pid] = st;
    } catch(e) {}
  }

  function _ensureDot(btn){
    try {
      if(!btn) return null;
      var dot = btn.querySelector('.rhk-tab-dot');
      if(dot) return dot;
      dot = document.createElement('span');
      dot.className = 'rhk-tab-dot';
      btn.appendChild(dot);
      return dot;
    } catch(e) { return null; }
  }

  function _getTabButtons(rootSel){
    try {
      var root = _deepQuerySelector(rootSel);
      if(!root) return [];
      var selectors = [
        '[role="tablist"] [role="tab"]',
        '[role="tab"]',
        '.tab-nav [role="tab"]',
        '.tab-nav button',
        'button[aria-controls][aria-selected]'
      ];
      var out = [];
      for(var i=0;i<selectors.length;i++){
        var list = [];
        try { list = Array.from(root.querySelectorAll(selectors[i]) || []); } catch(e) { list = []; }
        for(var j=0;j<list.length;j++){
          var el = list[j];
          if(!el || out.indexOf(el) >= 0) continue;
          var lbl = _normText(_tabLabel(el));
          if(!lbl) continue;
          out.push(el);
        }
        if(out.length) break;
      }
      return out;
    } catch(e) {
      return [];
    }
  }

  function _resolveQuickNavTarget(btn){
    var out = { input: '', output: '' };
    try {
      if(!btn || !btn.getAttribute) return out;
      out.input = btn.getAttribute('data-rhk-input-tab') || '';
      out.output = btn.getAttribute('data-rhk-output-tab') || '';
      if(out.input || out.output) return out;

      // Fallback when sanitizer strips data-* attributes:
      // infer target from visible button text.
      var txt = _normText(_tabLabel(btn));
      if(!txt) return out;

      if(txt.indexOf('1 klinik') === 0) out.input = '1. Klinik & Labor';
      else if(txt.indexOf('2 bildgebung') === 0) out.input = '2. Bildgebung & Echo/CMR';
      else if(txt.indexOf('3 lufu') === 0 || txt.indexOf('3 lungenfunktion') === 0) out.input = '3. Lungenfunktion & CPET';
      else if(txt.indexOf('4 rhk') === 0) out.input = '4. RHK';
      else if(txt.indexOf('5 weitere') === 0) out.input = '5. Weitere Befunde';
      else if(txt.indexOf('6 procedere') === 0) out.input = '6. Procedere & Module';
      else if(txt.indexOf('arztbericht') === 0) out.output = 'Arztbericht';
      else if(txt.indexOf('patientenbericht') === 0) out.output = 'Patientenbericht';
      else if(txt.indexOf('intern') === 0) out.output = 'Intern';
      else if(txt.indexOf('summary') === 0) out.output = 'Summary (JSON)';
      else if(txt.indexOf('debug') === 0) out.output = 'Debug';
    } catch(e) {}
    return out;
  }

  function _activateTabByLabel(rootSel, wantedLabel){
    try {
      var want = _normText(wantedLabel);
      if(!want) return false;
      var btns = _getTabButtons(rootSel);
      if(!btns.length) return false;
      var hit = null;
      for(var i=0;i<btns.length;i++){
        var lbl = _normText(_tabLabel(btns[i]));
        if(lbl === want || lbl.indexOf(want) === 0 || want.indexOf(lbl) === 0){
          hit = btns[i];
          break;
        }
      }
      if(!hit){
        for(var j=0;j<btns.length;j++){
          var lbl2 = _normText(_tabLabel(btns[j]));
          if(lbl2.indexOf(want) >= 0 || want.indexOf(lbl2) >= 0){
            hit = btns[j];
            break;
          }
        }
      }
      if(!hit) return false;
      hit.click();
      try { hit.scrollIntoView({block:'nearest', inline:'center', behavior:'smooth'}); } catch(e) {}
      return true;
    } catch(e) {
      return false;
    }
  }

  function _updateQuickNavActive(activeInputLabel, activeOutputLabel, activeInputIndex, activeOutputIndex){
    try {
      var qIn = _deepQuerySelectorAll('#rhk_quick_nav .rhk-qnav-btn');
      var qOut = _deepQuerySelectorAll('#rhk_output_nav .rhk-qnav-btn');
      var inNorm = _normText(activeInputLabel);
      var outNorm = _normText(activeOutputLabel);
      var inIdx = (typeof activeInputIndex === 'number' && activeInputIndex >= 0) ? activeInputIndex : -1;
      var outIdx = (typeof activeOutputIndex === 'number' && activeOutputIndex >= 0) ? activeOutputIndex : -1;

      qIn.forEach(function(btn){
        var on = false;
        var raw = btn.getAttribute && btn.getAttribute('data-rhk-nav-index');
        if(raw !== null && raw !== '' && inIdx >= 0){
          on = (parseInt(raw, 10) === inIdx);
        } else {
          var t = _normText(_resolveQuickNavTarget(btn).input);
          on = !!(inNorm && (t === inNorm || inNorm.indexOf(t) >= 0 || t.indexOf(inNorm) >= 0));
        }
        btn.classList.toggle('is-active', on);
      });
      qOut.forEach(function(btn){
        var on = false;
        var raw2 = btn.getAttribute && btn.getAttribute('data-rhk-nav-index');
        if(raw2 !== null && raw2 !== '' && outIdx >= 0){
          on = (parseInt(raw2, 10) === outIdx);
        } else {
          var t2 = _normText(_resolveQuickNavTarget(btn).output);
          on = !!(outNorm && (t2 === outNorm || outNorm.indexOf(t2) >= 0 || t2.indexOf(outNorm) >= 0));
        }
        btn.classList.toggle('is-active', on);
      });
    } catch(e) {}
  }

  var __rhkTabUxLastRunTs = 0;
  function updateTabUx(force){
    try {
      var isForce = !!force;
      var now = Date.now();
      // Coalesce high-frequency calls from typing/mutations.
      if(!isForce && (now - __rhkTabUxLastRunTs) < 70){
        return;
      }
      __rhkTabUxLastRunTs = now;

      _applyWorkflowOverviewState();
      var inputNav = _deepQuerySelector('#rhk_input_tabs .tab-nav, #rhk_input_tabs [role="tablist"], #rhk_input_tabs [role="tab"]');
      var outputNav = _deepQuerySelector('#rhk_output_tabs .tab-nav, #rhk_output_tabs [role="tablist"], #rhk_output_tabs [role="tab"]');
      if(!inputNav) return;

      // Keep a stable spacer for tab content below sticky tab-nav (prevents overlap)
      try {
        var h = inputNav.offsetHeight || 60;
        document.documentElement.style.setProperty('--rhk-tabnav-h', h + 'px');
      } catch(e) {}

      var inputButtons = _getTabButtons('#rhk_input_tabs');
      if(!inputButtons.length) return;

      // Subtitle (input tabs only)
      var sub = byId('rhk_tab_subtitle');
      var activeInputLabel = '';
      var activeInputIndex = -1;
      for(var i=0;i<inputButtons.length;i++){
        if(inputButtons[i].getAttribute('aria-selected') === 'true'){
          activeInputLabel = _tabLabel(inputButtons[i]);
          activeInputIndex = i;
          break;
        }
      }
      if(sub){
        var txt = __rhkTabSubtitleMap[activeInputLabel] || __rhkTabSubtitleMap[_tabLabel(inputButtons[0])] || '';
        sub.textContent = txt;
      }

      // Input-tab dots
      for(var j=0;j<inputButtons.length;j++){
        var btn = inputButtons[j];
        var dot = _ensureDot(btn);
        if(!dot) continue;
        var panelId = btn.getAttribute('aria-controls');
        var panel = panelId ? byId(panelId) : null;
        var cacheKey = String(panelId || ("idx:" + j));
        var cached = __rhkPanelFillCache[cacheKey];
        var needRecalc = isForce || !cached || !!cached.dirty;
        var filled = false;
        if(needRecalc){
          filled = _panelHasAnyValue(panel, cacheKey);
          __rhkPanelFillCache[cacheKey] = { value: !!filled, dirty: false };
        } else {
          filled = !!cached.value;
        }
        dot.classList.toggle('is-filled', !!filled);
        dot.classList.toggle('is-active', btn.getAttribute('aria-selected') === 'true');
      }

      var activeOutputLabel = '';
      var activeOutputIndex = -1;
      if(outputNav){
        var outputButtons = _getTabButtons('#rhk_output_tabs');
        for(var k=0;k<outputButtons.length;k++){
          if(outputButtons[k].getAttribute('aria-selected') === 'true'){
            activeOutputLabel = _tabLabel(outputButtons[k]);
            activeOutputIndex = k;
            break;
          }
        }
      }

      _updateQuickNavActive(activeInputLabel, activeOutputLabel, activeInputIndex, activeOutputIndex);
    } catch(e) {}
  }

  function scheduleTabUx(delayMs){
    try {
      if(window.__rhkTabUxT) clearTimeout(window.__rhkTabUxT);
      window.__rhkTabUxT = setTimeout(updateTabUx, Math.max(20, Number(delayMs || 80)));
    } catch(e) {}
  }

  function installTabUxObserver(){
    if(window.__rhkTabUxObserverInstalled) return;
    window.__rhkTabUxObserverInstalled = true;
    var lastMutationSchedule = 0;
    try {
      // Observe the document, but only react when tab/workflow subtrees are touched.
      var obs = new MutationObserver(function(muts){
        try {
          var relevant = false;
          for(var i=0;i<(muts || []).length;i++){
            var m = muts[i];
            if(!m) continue;
            var t = m.target;
            if(t && t.closest && t.closest('#rhk_input_tabs, #rhk_output_tabs, #rhk_workflow_overview, #rhk_tab_subtitle')){
              relevant = true;
              break;
            }
            if(m.addedNodes && m.addedNodes.length){
              for(var j=0;j<m.addedNodes.length;j++){
                var n = m.addedNodes[j];
                if(!n || n.nodeType !== 1) continue;
                var hit = false;
                try {
                  hit = (n.matches && n.matches('#rhk_input_tabs, #rhk_output_tabs, #rhk_workflow_overview, #rhk_tab_subtitle'))
                    || (n.querySelector && n.querySelector('#rhk_input_tabs, #rhk_output_tabs, #rhk_workflow_overview, #rhk_tab_subtitle'));
                } catch(e) { hit = false; }
                if(hit){
                  relevant = true;
                  break;
                }
              }
              if(relevant) break;
            }
          }
          if(!relevant) return;
          var now = Date.now();
          if((now - lastMutationSchedule) < 120) return;
          lastMutationSchedule = now;
          _invalidateRootCache();
          _invalidatePanelFillCache();
          _invalidatePanelInputElsCache();
          scheduleTabUx(90);
        } catch(e) {}
      });
      obs.observe(document.documentElement || document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['aria-selected', 'class', 'id']
      });
    } catch(e) {}

    // Event-driven refreshes for data entry and tab switches.
    try {
      document.addEventListener('click', function(ev){
        if(_findInEventPath(ev, '#rhk_input_tabs [role="tab"], #rhk_output_tabs [role="tab"], #rhk_input_tabs .tab-nav button, #rhk_output_tabs .tab-nav button')){
          scheduleTabUx(30);
        }
      }, true);
      document.addEventListener('change', function(ev){
        if(_findInEventPath(ev, '#rhk_input_tabs')){
          _markPanelDirtyFromEvent(ev);
          scheduleTabUx(60);
        }
      }, true);
      document.addEventListener('input', function(ev){
        if(_findInEventPath(ev, '#rhk_input_tabs')){
          _markPanelDirtyFromEvent(ev);
          scheduleTabUx(140);
        }
      }, true);
    } catch(e) {}
  }

  function _activateTabByIndex(rootSel, idx){
    // Gradio splits the tab strip into a visible .tab-container and an
    // .overflow-menu when the tabs don't fit. The visible container holds
    // only the first N tabs; the rest live inside the overflow menu that
    // needs to be opened before its items become clickable. In addition,
    // a .tab-container.visually-hidden sibling always carries ALL tab labels
    // in a fixed, canonical order — we use it as the ground-truth index map.
    try {
      var n = parseInt(idx, 10);
      if(!(n >= 0)) return false;
      var root = _deepQuerySelector(rootSel);
      if(!root) return false;

      // Canonical label for the Nth tab (language-independent position).
      var hiddenStrip = root.querySelector('.tab-container.visually-hidden');
      var hiddenBtns = hiddenStrip ? Array.from(hiddenStrip.querySelectorAll('button')) : [];
      if(!hiddenBtns.length || n >= hiddenBtns.length) return false;
      var wantLabel = _normText(hiddenBtns[n].textContent);
      if(!wantLabel) return false;

      function _clickByLabelInScope(scopeEl){
        if(!scopeEl) return false;
        var btns = Array.from(scopeEl.querySelectorAll('button'));
        for(var i=0;i<btns.length;i++){
          var b = btns[i];
          if(!b) continue;
          if(b.offsetParent === null) continue; // skip hidden
          var lbl = _normText(b.textContent || '');
          if(lbl && lbl === wantLabel){
            b.click();
            try { b.scrollIntoView({block:'nearest', inline:'center', behavior:'smooth'}); } catch(e) {}
            return true;
          }
        }
        return false;
      }

      // 1) Try the visible strip first.
      var visibleStrip = root.querySelector('.tab-container:not(.visually-hidden)');
      if(_clickByLabelInScope(visibleStrip)) return true;

      // 2) Open the overflow menu, then click the matching item.
      var overflow = root.querySelector('.overflow-menu');
      if(!overflow) return false;
      var overflowToggle = overflow.querySelector(':scope > button');
      if(!overflowToggle) return false;

      overflowToggle.click(); // open dropdown so menu items become interactive
      setTimeout(function(){
        try {
          if(_clickByLabelInScope(overflow)) return;
          // If the overflow shuffled the visible strip, try it again too.
          var vs2 = root.querySelector('.tab-container:not(.visually-hidden)');
          _clickByLabelInScope(vs2);
        } catch(e) {}
      }, 60);
      return true;
    } catch(e) {
      return false;
    }
  }

  function installQuickNav(){
    if(window.__rhkQuickNavInstalled) return;
    window.__rhkQuickNavInstalled = true;
    try {
      document.addEventListener('click', function(ev){
        var btn = _findInEventPath(ev, '.rhk-qnav-btn');
        if(!btn) return;
        // Preferred: language-independent index-based dispatch.
        var scope = btn.getAttribute && btn.getAttribute('data-rhk-nav-scope');
        var idxAttr = btn.getAttribute && btn.getAttribute('data-rhk-nav-index');
        if(scope && idxAttr !== null && idxAttr !== ''){
          ev.preventDefault();
          var rootSel = scope === 'output' ? '#rhk_output_tabs' : '#rhk_input_tabs';
          if(_activateTabByIndex(rootSel, idxAttr)){
            scheduleTabUx(30);
            return;
          }
        }
        // Fallback: legacy label-based target (only reliable when UI is in German).
        var target = _resolveQuickNavTarget(btn);
        var inputTarget = target.input;
        var outputTarget = target.output;
        if(inputTarget){
          ev.preventDefault();
          _activateTabByLabel('#rhk_input_tabs', inputTarget);
          scheduleTabUx(30);
          return;
        }
        if(outputTarget){
          ev.preventDefault();
          _activateTabByLabel('#rhk_output_tabs', outputTarget);
          scheduleTabUx(30);
        }
      }, true);
    } catch(e) {}
  }

  var __rhkWorkflowPrefKey = 'rhk.workflow_overview.collapsed';
  function _readWorkflowOverviewCollapsed(){
    // Default to COLLAPSED. The orientation panel is reference material, not
    // primary content — do not dominate the above-the-fold view by default.
    try {
      if(window.__rhkWorkflowCollapsed === true || window.__rhkWorkflowCollapsed === false){
        return !!window.__rhkWorkflowCollapsed;
      }
      var raw = window.localStorage ? window.localStorage.getItem(__rhkWorkflowPrefKey) : null;
      // If the user has never made a choice, start collapsed. Only '0' (explicit
      // "keep expanded") overrides that default.
      window.__rhkWorkflowCollapsed = (raw === null || raw === undefined) ? true : (raw !== '0');
      return !!window.__rhkWorkflowCollapsed;
    } catch(e) {
      return true;
    }
  }

  function _writeWorkflowOverviewCollapsed(collapsed){
    try {
      var on = !!collapsed;
      window.__rhkWorkflowCollapsed = on;
      if(window.localStorage) window.localStorage.setItem(__rhkWorkflowPrefKey, on ? '1' : '0');
    } catch(e) {}
  }

  function _applyWorkflowOverviewState(){
    try {
      var root = byId('rhk_workflow_overview');
      var body = byId('rhk_workflow_overview_body');
      var toggle = byId('rhk_workflow_toggle');
      if(!root || !toggle) return false;

      var collapsed = _readWorkflowOverviewCollapsed();
      root.classList.toggle('is-collapsed', collapsed);
      root.setAttribute('data-rhk-collapsed', collapsed ? '1' : '0');
      toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
      toggle.setAttribute('aria-controls', 'rhk_workflow_overview_body');
      var sourceLabel = collapsed ? 'Einblenden' : 'Ausblenden';
      var lang = window.__rhkUiLanguage;
      if(!lang){
        try { lang = (window.localStorage && window.localStorage.getItem('rhk.ui.language')) || 'de'; }
        catch(e){ lang = 'de'; }
      }
      var exact = (window.RHK_I18N && window.RHK_I18N.exact && window.RHK_I18N.exact[lang]) || {};
      var label = (lang !== 'de' && Object.prototype.hasOwnProperty.call(exact, sourceLabel)) ? exact[sourceLabel] : sourceLabel;
      toggle.textContent = label;
      if(body) body.setAttribute('aria-hidden', collapsed ? 'true' : 'false');
      return true;
    } catch(e) {
      return false;
    }
  }

  function installWorkflowOverviewToggle(){
    if(window.__rhkWorkflowToggleInstalled) return;
    window.__rhkWorkflowToggleInstalled = true;
    try {
      document.addEventListener('click', function(ev){
        var btn = _findInEventPath(ev, '#rhk_workflow_toggle, .rhk-wf-toggle');
        if(!btn) return;
        ev.preventDefault();
        _writeWorkflowOverviewCollapsed(!_readWorkflowOverviewCollapsed());
        _applyWorkflowOverviewState();
        scheduleTabUx(40);
      }, true);
    } catch(e) {}
    _applyWorkflowOverviewState();
    try { setTimeout(_applyWorkflowOverviewState, 400); } catch(e) {}
  }

  // Expose for cross-IIFE callers (i18n language switch needs to re-localize
  // the toggle button because its text is set via textContent, not via a
  // cached __rhkI18nSourceText node).
  try { window.__rhkApplyWorkflowOverviewState = _applyWorkflowOverviewState; } catch(e) {}

  function enforceLight(){
    try {
      document.documentElement.style.colorScheme = 'light';
      if(document.body) document.body.style.colorScheme = 'light';
    } catch(e) {}
  }

  function _ensureInputTabsId(){
    // Gradio renders the 6 input TabItems inside an implicit .tabs container
    // that has no elem_id. The quick-nav dispatch and sticky-bar logic both
    // expect '#rhk_input_tabs'. Locate that container inside the input
    // column and stamp the id onto it so every downstream selector works.
    try {
      if(document.getElementById('rhk_input_tabs')) return true;
      var col = document.getElementById('rhk_input_column');
      if(!col) return false;
      var tabs = col.querySelector('.tabs');
      if(!tabs) return false;
      tabs.id = 'rhk_input_tabs';
      return true;
    } catch(e) {
      return false;
    }
  }

  function boot(){
    enforceLight();
    _invalidateRootCache();
    _invalidatePanelFillCache();
    _ensureInputTabsId();
    installCopyDelegation();
    installCopyObserver();
    installQuickNav();
    installWorkflowOverviewToggle();
    installTabUxObserver();
    updateTabUx(true);
  }

  // Gradio may re-render; bind on load and after short delays.
  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', function(){ boot(); setTimeout(boot, 500); setTimeout(boot, 1500); });
  } else {
    boot(); setTimeout(boot, 500); setTimeout(boot, 1500);
  }
})();
</script>
<script>
// ---------------------------------------------------------------
// RHK: Browser OCR helpers (Echo screenshots)
// - Runs fully client-side via tesseract.js.
// - Writes extracted text into hidden Gradio Textboxes which then
//   trigger Python parsing logic.
// ---------------------------------------------------------------
(function(){
  // Gradio often renders inputs inside a WebComponent with a shadowRoot.
  // Also: components with visible=False may not exist in the DOM.
  // We therefore set values by stable elem_id and search both light DOM and shadow DOM.
  var _ECHO_LABEL_TO_ID = {
    'Echo OCR Text (aktuell, browser)': 'echo_ocr_text_cur',
    'Echo OCR Text (Vor, browser)': 'echo_ocr_text_prev',
    'Echo PDF Text (aktuell, browser)': 'echo_pdf_text_cur',
    'Echo PDF Text (Vor, browser)': 'echo_pdf_text_prev'
  };

  // Robust selector that also searches inside shadow roots (Gradio renders in a shadow DOM).
  function _deepQuerySelector(sel){
    try {
      var direct = document.querySelector(sel);
      if(direct) return direct;
    } catch(e) {}

    var roots = [];
    try {
      roots.push(document);
      // Collect shadow roots recursively
      var all = document.querySelectorAll('*');
      for(var i=0;i<all.length;i++){
        try {
          if(all[i] && all[i].shadowRoot) roots.push(all[i].shadowRoot);
        } catch(e) {}
      }
    } catch(e) {}

    for(var r=0;r<roots.length;r++){
      try {
        var hit = roots[r].querySelector(sel);
        if(hit) return hit;
      } catch(e) {}
    }
    return null;
  }

  function _safeCssId(id){
    try { return CSS && CSS.escape ? CSS.escape(id) : id; } catch(e) { return id; }
  }

  function findGradioInput(elemId, label){
    if(!elemId && !label) return null;

    // 1) Prefer elem_id (stable)
    if(elemId){
      var esc = _safeCssId(elemId);
      var wrapper = _deepQuerySelector('#' + esc);
      if(wrapper){
        var tag = (wrapper.tagName || '').toLowerCase();
        if(tag === 'textarea' || tag === 'input') return wrapper;
        try {
          var inner = wrapper.querySelector('textarea, input');
          if(inner) return inner;
        } catch(e) {}
      }
      // Sometimes Gradio puts the textarea adjacent, but keeps the elem_id on a higher wrapper.
      // Best-effort: find any textarea/input with a closest ancestor matching the elem_id.
      try {
        var cand = _deepQuerySelector('#' + esc + ' textarea') || _deepQuerySelector('#' + esc + ' input');
        if(cand) return cand;
      } catch(e) {}
    }

    // 2) Fallback: aria-label equals component label (less stable)
    if(label){
      try {
        var aria = _deepQuerySelector('textarea[aria-label="' + label.replace(/"/g, '\\"') + '"]') ||
                   _deepQuerySelector('input[aria-label="' + label.replace(/"/g, '\\"') + '"]');
        if(aria) return aria;
      } catch(e) {}
    }

    return null;
  }

  function setGradioTextbox(label, value){
    var elemId = _ECHO_LABEL_TO_ID[label] || label; // allow passing elem_id directly
    var el = findGradioInput(elemId, label);
    if(!el) return false;
    var tag = (el.tagName || '').toLowerCase();
    if(!(tag === 'textarea' || tag === 'input')) return false;
    el.value = value;
    try { el.dispatchEvent(new Event('input', { bubbles:true })); } catch(e) {}
    try { el.dispatchEvent(new Event('change', { bubbles:true })); } catch(e) {}
    return true;
  }
  function setStatus(id, msg){
    var el = document.getElementById(id);
    if(!el) return;
    el.textContent = msg;
  }

  async function runOcr(kind){
    // NOTE: IDs must match the HTML inputs in rhk_ui_echo.py
    var inputId = (kind === 'prev') ? 'rhk_echo_ocr_file_prev' : 'rhk_echo_ocr_file_cur';
    var statusId = (kind === 'prev') ? 'rhk_echo_ocr_status_prev' : 'rhk_echo_ocr_status_cur';
    var tbLabel = (kind === 'prev') ? 'Echo OCR Text (Vor, browser)' : 'Echo OCR Text (aktuell, browser)';

    var fi = document.getElementById(inputId);
    if(!fi || !fi.files || !fi.files[0]){
      setStatus(statusId, 'Bitte Screenshot wählen.');
      return;
    }
    var file = fi.files[0];
    if(!window.Tesseract || !window.Tesseract.recognize){
      try{
        setStatus(statusId, 'OCR Engine laden...');
        if(window.rhkEnsureTesseract) await window.rhkEnsureTesseract();
      }catch(e){
        setStatus(statusId, 'OCR Fehler: Tesseract nicht geladen. ' + (e && e.message ? e.message : e));
        return;
      }
    }
    if(!window.Tesseract || !window.Tesseract.recognize){
      setStatus(statusId, 'OCR Fehler: Engine nicht verfügbar.');
      return;
    }
    setStatus(statusId, 'OCR läuft...');
    try {
      var res = await window.Tesseract.recognize(file, 'deu+eng', {
        logger: function(m){
          if(m && m.status === 'recognizing text' && typeof m.progress === 'number'){
            setStatus(statusId, 'OCR läuft... ' + Math.round(m.progress*100) + '%');
          }
        }
      });
      var txt = (res && res.data && res.data.text) ? String(res.data.text) : '';
      if(!txt.trim()){
        setStatus(statusId, 'Kein Text erkannt.');
        return;
      }
      var ok = setGradioTextbox(tbLabel, txt);
      setStatus(statusId, ok ? 'Text übernommen.' : 'Konnte Text nicht an Gradio übergeben.');
    } catch(e) {
      setStatus(statusId, 'OCR Fehler: ' + (e && e.message ? e.message : e));
    }
  }

  async function runPdf(kind){
    var inputId = (kind === 'prev') ? 'rhk_echo_pdf_file_prev' : 'rhk_echo_pdf_file_cur';
    var statusId = (kind === 'prev') ? 'rhk_echo_pdf_status_prev' : 'rhk_echo_pdf_status_cur';
    var tbLabel = (kind === 'prev') ? 'Echo PDF Text (Vor, browser)' : 'Echo PDF Text (aktuell, browser)';

    var fi = document.getElementById(inputId);
    if(!fi || !fi.files || !fi.files[0]){
      setStatus(statusId, 'Bitte PDF wählen.');
      return;
    }
    var file = fi.files[0];
    if(!file || !String(file.name || '').toLowerCase().endsWith('.pdf')){
      setStatus(statusId, 'Bitte eine PDF Datei wählen.');
      return;
    }

    // Ensure pdf.js
    try {
      setStatus(statusId, 'PDF Engine laden...');
      if(window.rhkEnsurePdfJs) await window.rhkEnsurePdfJs();
    } catch(e) {
      setStatus(statusId, 'PDF Fehler: pdf.js nicht geladen. Offline? Nutze Screenshot OCR oder Legacy Upload.');
      return;
    }
    if(!(window.pdfjsLib && window.pdfjsLib.getDocument)){
      setStatus(statusId, 'PDF Fehler: pdf.js nicht verfügbar.');
      return;
    }
    if(!window.Tesseract || !window.Tesseract.recognize){
      // We can still do textlayer extraction.
      // OCR fallback (scan PDFs) will be unavailable without Tesseract.
    }

    try {
      setStatus(statusId, 'PDF Text extrahieren...');
      var ab = await file.arrayBuffer();
      var loadingTask = window.pdfjsLib.getDocument({data: ab});
      var doc = await loadingTask.promise;
      var maxPages = Math.min(doc.numPages || 1, 3);
      var allText = [];
      for(var p=1; p<=maxPages; p++){
        var page = await doc.getPage(p);
        var tc = await page.getTextContent();
        var items = (tc && tc.items) ? tc.items : [];
        for(var i=0;i<items.length;i++){
          if(items[i] && items[i].str) allText.push(String(items[i].str));
        }
        allText.push('\n');
      }
      var txt = allText.join(' ').replace(/\s+/g,' ').trim();

      // If textlayer is empty-ish, treat as scan and OCR page 1.
      if((!txt || txt.length < 40) && !(window.Tesseract && window.Tesseract.recognize)){
        try{
          setStatus(statusId, 'Scan PDF erkannt. OCR Engine laden...');
          if(window.rhkEnsureTesseract) await window.rhkEnsureTesseract();
        }catch(e){
          setStatus(statusId, 'Scan PDF erkannt, aber OCR Engine nicht verfügbar. Nutze Screenshot OCR oder Legacy Upload.');
          return;
        }
      }
      if((!txt || txt.length < 40) && window.Tesseract && window.Tesseract.recognize){
        setStatus(statusId, 'Scan PDF erkannt. OCR Seite 1 läuft...');
        var page1 = await doc.getPage(1);
        var viewport = page1.getViewport({scale: 2.0});
        var canvas = document.createElement('canvas');
        canvas.width = Math.ceil(viewport.width);
        canvas.height = Math.ceil(viewport.height);
        var ctx = canvas.getContext('2d');
        await page1.render({canvasContext: ctx, viewport: viewport}).promise;
        var blob = await new Promise(function(resolve){
          try { canvas.toBlob(resolve, 'image/png'); } catch(e) { resolve(null); }
        });
        if(!blob){
          setStatus(statusId, 'OCR Fehler: Canvas Export fehlgeschlagen.');
          return;
        }
        var res = await window.Tesseract.recognize(blob, 'deu+eng', {
          logger: function(m){
            if(m && m.status === 'recognizing text' && typeof m.progress === 'number'){
              setStatus(statusId, 'OCR läuft... ' + Math.round(m.progress*100) + '%');
            }
          }
        });
        txt = (res && res.data && res.data.text) ? String(res.data.text) : '';
        txt = txt.replace(/\s+/g,' ').trim();
      }

      if(!txt || !txt.trim()){
        setStatus(statusId, '0 Werte. Kein verwertbarer Textlayer. Nutze Screenshot OCR oder Legacy Upload.');
        return;
      }

      var ok = setGradioTextbox(tbLabel, txt);
      setStatus(statusId, ok ? 'Text übernommen.' : 'Konnte Text nicht an Gradio übergeben.');
    } catch(e) {
      setStatus(statusId, 'PDF Fehler: ' + (e && e.message ? e.message : e));
    }
  }

  async function runClipboardOcr(kind){
    var statusId = (kind === 'prev') ? 'rhk_echo_ocr_status_prev' : 'rhk_echo_ocr_status_cur';
    var tbLabel = (kind === 'prev') ? 'Echo OCR Text (Vor, browser)' : 'Echo OCR Text (aktuell, browser)';

    if(!navigator.clipboard || !navigator.clipboard.read){
      setStatus(statusId, 'Zwischenablage nicht verfügbar (Browser/HTTPS).');
      return;
    }
    if(!window.Tesseract || !window.Tesseract.recognize){
      try{
        setStatus(statusId, 'OCR Engine laden...');
        if(window.rhkEnsureTesseract) await window.rhkEnsureTesseract();
      }catch(e){
        setStatus(statusId, 'OCR Fehler: Tesseract nicht geladen. ' + (e && e.message ? e.message : e));
        return;
      }
    }
    if(!window.Tesseract || !window.Tesseract.recognize){
      setStatus(statusId, 'OCR Fehler: Engine nicht verfügbar.');
      return;
    }

    setStatus(statusId, 'Zwischenablage lesen...');
    try {
      var items = await navigator.clipboard.read();
      var blob = null;
      for(const it of items){
        for(const t of it.types){
          if(t && t.startsWith('image/')){
            blob = await it.getType(t);
            break;
          }
        }
        if(blob) break;
      }
      if(!blob){
        setStatus(statusId, 'Kein Bild in der Zwischenablage.');
        return;
      }

      setStatus(statusId, 'OCR läuft...');
      var res = await window.Tesseract.recognize(blob, 'deu+eng', {
        logger: function(m){
          if(m && m.status === 'recognizing text' && typeof m.progress === 'number'){
            setStatus(statusId, 'OCR läuft... ' + Math.round(m.progress*100) + '%');
          }
        }
      });
      var txt = (res && res.data && res.data.text) ? String(res.data.text) : '';
      if(!txt.trim()){
        setStatus(statusId, 'Kein Text erkannt.');
        return;
      }
      var ok = setGradioTextbox(tbLabel, txt);
      setStatus(statusId, ok ? 'Text übernommen.' : 'Konnte Text nicht an Gradio übergeben.');
    } catch(e) {
      setStatus(statusId, 'Clipboard Fehler: ' + (e && e.message ? e.message : e));
    }
  }

  window.rhkRunEchoOcr = function(kind){
    runOcr(kind === 'prev' ? 'prev' : 'cur');
  };
  // Clipboard OCR (image in clipboard) – name aligned with UI HTML
  window.rhkRunEchoClipboard = function(kind){
    runClipboardOcr(kind === 'prev' ? 'prev' : 'cur');
  };
  // Backward alias (if referenced elsewhere)
  window.rhkRunEchoClipboardOcr = window.rhkRunEchoClipboard;

  // Browser PDF import (no upload)
  window.rhkRunEchoPdf = function(kind){
    runPdf(kind === 'prev' ? 'prev' : 'cur');
  };
})();
</script>
""",
    ]
)

CSS = ("""
/* ------------------------------------------------------------------
   Light UI (robust): enforce readability even if browser/system prefers dark
   ------------------------------------------------------------------ */

/* Hide but keep in DOM so browser-side JS can write into the input reliably */
.rhk-hidden {
  position: absolute !important;
  left: -10000px !important;
  top: auto !important;
  width: 1px !important;
  height: 1px !important;
  overflow: hidden !important;
  opacity: 0 !important;
  pointer-events: none !important;
}

/* ------------------------------------------------------------------
   Pre-RHK PDF button (A4 landscape one-pager)
   Placed at the very bottom of the app (scroll-to) for printing
   right before catheter. Keep it compact and non-dominant.
   ------------------------------------------------------------------ */
/* Pre-RHK PDF export button (in action row) */
#btn_prerhk_pdf .wrap, #btn_prerhk_pdf button{
  border-radius: var(--rhk-radius-sm);
}
#btn_prerhk_pdf button{
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid rgba(148, 163, 184, 0.9);
  background: #ffffff;
  color: var(--rhk-color-text);
  box-shadow: none;
}
#btn_prerhk_pdf button:hover{
  filter: brightness(0.98);
}

/* Inline Pre-RHK PDF download row (next to copy buttons) */
#rhk_prerhk_inline_row{
  align-items: center;
  gap: 10px;
  margin-top: 4px;
}
#file_prerhk_pdf{
  max-width: 260px;
}
#prerhk_status{
  font-size: 12px;
  color: #475569;
}

/* Neutralize "Befund erstellen/aktualisieren" buttons (avoid persistent blue look) */
#btn_generate_top button, #btn_generate_bottom button {
  background: #ffffff;
  color: var(--rhk-color-text);
  border: 1px solid rgba(148, 163, 184, 0.9);
  box-shadow: none;
}
#btn_generate_top button:hover, #btn_generate_bottom button:hover {
  filter: brightness(0.98);
}

/* Top action buttons: keep the same conservative light style */
#btn_example_top button, #btn_example_bottom button,
#btn_clear_top button, #btn_clear_bottom button,
#btn_save_top button, #btn_save_bottom button,
#btn_load_top button, #btn_load_bottom button {
  background: #ffffff;
  color: var(--rhk-color-text);
  border: 1px solid rgba(148, 163, 184, 0.9);
  box-shadow: none;
}
#btn_example_top button:hover, #btn_example_bottom button:hover,
#btn_clear_top button:hover, #btn_clear_bottom button:hover,
#btn_save_top button:hover, #btn_save_bottom button:hover,
#btn_load_top button:hover, #btn_load_bottom button:hover {
  filter: brightness(0.98);
}

/* Workflow overview panel — canonical rules live near the design-token block
   further below (search: "#rhk_workflow_overview{"). This stub only defines
   layout primitives that are structural (display: grid columns, list indent,
   collapsed-state visibility) and depend on nothing else. */
#rhk_workflow_overview .rhk-wf-grid{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
#rhk_workflow_overview.is-collapsed .rhk-wf-body{
  display: none !important;
}
#rhk_workflow_overview ol{
  margin: 0;
  padding-left: 18px;
}
@media (max-width: 900px){
  #rhk_workflow_overview .rhk-wf-grid{
    grid-template-columns: 1fr;
  }
}

/* Copy + download buttons: match the same style (avoid heavy dark blocks) */
#btn_copy_doc button, #btn_download_doc button, #btn_copy_pat button, #btn_copy_rhk button {
  background: #ffffff;
  color: var(--rhk-color-text);
  border: 1px solid rgba(148, 163, 184, 0.9);
  box-shadow: none;
}
#btn_copy_doc button:hover, #btn_download_doc button:hover, #btn_copy_pat button:hover, #btn_copy_rhk button:hover {
  filter: brightness(0.98);
}

/* Make the copy/download button row more compact */
#rhk_copy_row button {
  padding: 4px 10px;
  font-size: 12px;
  line-height: 1.1;
  min-height: 32px;
}



/* Tab content as card: improves scanability on Klinik/Labor, Imaging, Lufu/CPET etc. */
#rhk_input_tabs .tabitem {
  background: #ffffff;
  border: 1px solid rgba(0,0,0,0.10);
  border-radius: var(--rhk-radius-md);
  padding: 14px 14px 10px 14px;
  box-shadow: var(--rhk-shadow-sm);
  margin-bottom: 14px;
}

/* Make section headings within tabs feel like card headers */
#rhk_input_tabs .tabitem h3,
#rhk_input_tabs .tabitem h4 {
  margin-top: 0px;
  margin-bottom: 8px;
}

/* Reduce vertical noise between form rows */
#rhk_input_tabs .tabitem .gr-row {
  gap: 10px;
  margin-bottom: 10px;
}

/* Hidden clipboard payloads must remain in DOM for robust JS copy binding */
.rhk-hidden-payload{ display: none !important; }
/* Hidden but clickable download payloads: keep in layout tree to allow programmatic click */
.rhk-hidden-download{ position: absolute !important; left: -10000px !important; top: -10000px !important; width: 1px !important; height: 1px !important; opacity: 0 !important; pointer-events: auto !important; }


:root,
.dark,
:root[data-theme="dark"], html[data-theme="dark"], body[data-theme="dark"],
:root[data-color-mode="dark"], html[data-color-mode="dark"], body[data-color-mode="dark"],
.gradio-container[data-theme="dark"], .gradio-container[data-color-mode="dark"] {
  color-scheme: light;
  --card-bg: rgba(255,255,255,0.96);
  --border: rgba(0,0,0,0.08);

  /* Gradio CSS vars (override dark defaults) */
  /* Canvas: very light lavender (keeps your existing palette, but less "grau" dominant) */
  --body-background-fill: #faf9ff;
  --background-fill-primary: #ffffff;
  --background-fill-secondary: #faf9ff;
  --block-background-fill: rgba(255,255,255,0.96);
  --block-border-color: rgba(0,0,0,0.08);
  --input-background-fill: #ffffff;
  --input-border-color: rgba(0,0,0,0.18);
  --body-text-color: #111111;
  --input-text-color: #111111;
}

html, body { color-scheme: light; background: #faf9ff; }

.gradio-container { max-width: 1700px; margin: 0 auto; padding-left: 8px; padding-right: 8px; }

/* ------------------------------------------------------------------
   Modern light card-based dashboard
   ------------------------------------------------------------------ */

/* Reusable card wrapper for grouping related parameters */
.rhk-card{
  background: rgba(255,255,255,0.98);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: var(--rhk-radius-md);
  padding: 12px 12px 10px 12px;
  box-shadow: var(--rhk-shadow-sm);
  margin: 6px 0;
}

/* Mode help card — two-span structure so each sentence is a single
   translatable text node. */
.rhk-mode-card .rhk-mode-label{
  font-weight: 700;
  color: var(--ds-text, #0f172a);
}
.rhk-mode-card .rhk-mode-label::after{
  content: ": ";
  font-weight: 700;
}
.rhk-mode-card .rhk-mode-label:lang(zh)::after{
  content: "\FF1A";
}
.rhk-mode-card .rhk-mode-text{
  color: var(--ds-text, #0f172a);
}

/* DOCX import hint — blue callout at top, compact gray version at bottom.
   Two/three spans so each sentence is a single translatable text node. */
.rhk-import-hint-box{
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px;
  background: #eff6ff;
  border-left: 4px solid #3b82f6;
  padding: 10px 14px;
  border-radius: 6px;
  margin: 6px 0 10px 0;
  font-size: 0.93em;
  color: #1e3a5f;
}
.rhk-import-hint-box .rhk-import-hint-icon{
  flex: 0 0 auto;
  font-size: 1.05em;
}
.rhk-import-hint-box .rhk-import-hint-label{
  font-weight: 700;
  color: #1e3a5f;
}
.rhk-import-hint-box .rhk-import-hint-label::after{
  content: ": ";
  font-weight: 700;
}
.rhk-import-hint-box .rhk-import-hint-label:lang(zh)::after{
  content: "\FF1A";
}
.rhk-import-hint-box .rhk-import-hint-text{
  flex: 1 1 280px;
  color: #1e3a5f;
  line-height: 1.5;
}
.rhk-import-hint-compact{
  display: block;
  color: #64748b;
  font-size: 0.9em;
  line-height: 1.45;
}

/* ------------------------------------------------------------------
   Section cards (Apple-like header bar + subtle progress)
   ------------------------------------------------------------------ */

.rhk-section-card{ padding: 0; overflow: hidden; border-radius: var(--rhk-radius-md); }

.rhk-sec-head{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
  background: rgba(168, 85, 247, 0.06); /* unified accent subtle */
}

.rhk-sec-title{
  font-size: 13px;
  font-weight: 850;
  color: var(--rhk-color-text);
  letter-spacing: 0.1px;
}

.rhk-sec-progress{
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

.rhk-sec-progress.is-optional .rhk-sec-bar{ display: none; }

.rhk-sec-progress .rhk-sec-count{
  font-size: 12px;
  font-weight: 750;
  color: rgba(15, 23, 42, 0.70);
}

.rhk-sec-bar{
  width: 64px;
  height: 4px;
  border-radius: var(--rhk-radius-pill);
  background: rgba(15, 23, 42, 0.08);
  overflow: hidden;
}

.rhk-sec-bar > div{
  height: 100%;
  width: 0%;
  border-radius: var(--rhk-radius-pill);
  background: rgba(168, 85, 247, 0.75);
}

.rhk-sec-body{
  padding: 12px 12px 8px 12px;
  background: #ffffff;
}

/* Inside section cards: prevent "graue Streifen" by keeping wrappers transparent */
.rhk-section-card .gr-row,
.rhk-section-card .gr-column,
.rhk-section-card .gr-form,
.rhk-section-card .gr-box,
.rhk-section-card .gr-block,
.rhk-section-card .wrap,
.rhk-section-card .block{
  background: transparent !important;
  box-shadow: none !important;
}

/* Apple-like rounding for input wrappers inside cards */
.rhk-card .gr-text-input,
.rhk-card .gr-number,
.rhk-card .gr-dropdown,
.rhk-card .gr-textbox,
.rhk-card .gradio-dropdown,
.rhk-card .gradio-textbox,
.rhk-card .gradio-number,
.rhk-card .gradio-text-input{
  border-radius: var(--ds-radius-sm);
}

/* Slightly tighter variant */
.rhk-card.rhk-card-tight{
  padding: 12px 12px 8px 12px;
}

/* Make headings inside cards look like card headers (no huge markdown spacing) */
.rhk-card h1, .rhk-card h2, .rhk-card h3{
  margin: 2px 0 10px 0;
  padding: 0;
  font-size: 15px;
  font-weight: 800;
  color: var(--rhk-color-text);
}
.rhk-card h4{
  margin: 2px 0 8px 0;
  padding: 0;
  font-size: 13px;
  font-weight: 700;
  color: var(--rhk-color-text);
  opacity: 0.95;
}

/* Reduce noisy whitespace between inputs */
.rhk-card .gr-form, .rhk-card .gr-box, .rhk-card .gr-block{
  box-shadow: none !important;
}
.rhk-card .gr-row{
  gap: 10px !important;
}

/* Verlauf table (Dashboard) */
.rhk-trend-table{
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  overflow: hidden;
  border: 1px solid rgba(15, 23, 42, 0.10);
  border-radius: var(--rhk-radius-sm);
  background: #ffffff;
}
.rhk-trend-table th,
.rhk-trend-table td{
  padding: 8px 10px;
  font-size: 13px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
}
.rhk-trend-table th{
  background: rgba(246, 247, 251, 0.95);
  font-weight: 800;
  color: var(--rhk-color-text);
}
.rhk-trend-table tr:last-child td{ border-bottom: none; }

/* Inputs: subtle border and consistent radius */
.rhk-card input, .rhk-card textarea, .rhk-card select{
  border-radius: var(--ds-radius-sm);
  border: 1px solid rgba(15, 23, 42, 0.14);
}

/* Accordions should also look like cards */
.gradio-container details{
  border-radius: var(--rhk-radius-md);
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: rgba(255,255,255,0.98);
  box-shadow: var(--rhk-shadow-sm);
}
.gradio-container details > summary{
  padding: 10px 12px;
  font-weight: 800;
  color: var(--rhk-color-text);
}

/* Tabs: keep crisp, dashboard-like */
[role="tablist"] > button{
  border-radius: var(--rhk-radius-pill);
  border: 1px solid rgba(15, 23, 42, 0.10);
  background: rgba(255,255,255,0.9);
}
[role="tablist"] > button[aria-selected="true"]{
  border-color: rgba(37, 99, 235, 0.35);
  box-shadow: var(--rhk-shadow-sm);
}

/* Force light cards/panels even if Gradio or browser applies dark-ish block fills */
.gradio-container .gr-box,
.gradio-container .gr-block,
.gradio-container .panel,
.gradio-container .form,
.gradio-container .wrap {
  background: rgba(255,255,255,0.96);
  color: #111111;
}

/* Prevent any dark mode artefacts */
.dark, .dark * { color-scheme: light; }
.dark body, .dark .gradio-container { background: #f6f7fb; }
.dark .card, .dark .gr-box, .dark .panel { background: var(--card-bg); color: #111; }
.dark .prose, .dark .markdown, .dark .wrap { color: #111; }

/* Force light input fields (some browsers/components keep dark backgrounds) */
.gradio-container input:not([type="checkbox"]):not([type="radio"]),
.gradio-container textarea,
.gradio-container select {
  background: #ffffff;
  color: #111111;
}

/* Make checkbox/radio state clearly visible */
.gradio-container input[type="checkbox"],
.gradio-container input[type="radio"]{
  accent-color: #2563eb;
}

.gradio-container input::placeholder,
.gradio-container textarea::placeholder {
  color: rgba(0,0,0,0.45);
}

/* Hide theme toggle (we enforce light) */
button[aria-label*="dark"],
button[aria-label*="Dark"],
button[title*="dark"],
button[title*="Dark"] {
  display: none;
}
/* Tabs: immer sichtbar, aber ohne Höhen-Drift → horizontal scroll (robust, verhindert Overlap) */
[role="tablist"]{
  flex-wrap: nowrap;
  overflow-x: auto;
  overflow-y: hidden;
  white-space: nowrap;
  gap: 6px;
  scrollbar-width: none;
}
[role="tablist"]::-webkit-scrollbar{ display:none; }
/* volle Tab-Titel (kein Ellipsis) */
[role="tablist"] > button{
  flex: 0 0 auto;
  max-width: none;
  width: auto;
  overflow: visible;
  text-overflow: clip;
  white-space: nowrap;
  margin: 2px 4px;
  padding: 6px 10px;
  font-size: 13px;
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

/* Tab-Content: Platzhalter unter sticky Tab-Leiste (verhindert, dass Überschriften/Progress-Bar "unter" die Tabs rutschen) */
.gradio-container .tabs{
  --rhk-tabnav-h: 60px;
}
.gradio-container .tabs > .tabitem{
  padding-top: 6px;
  scroll-margin-top: calc(74px + var(--rhk-tabnav-h, 60px) + 12px);
}

/* ------------------------------------------------------------------
   v27.2 Tabs: sticky + segmented control + subtitle + completion dots
   ------------------------------------------------------------------ */

/* Make the MAIN tab bar visually dominant and keep it visible while scrolling */
.gradio-container .tabs > .tab-nav,
.gradio-container .tab-nav{
  position: sticky;
  top: 74px; /* below topbar */
  z-index: 9500;
  background: rgba(246, 247, 251, 0.92);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  padding: 10px 6px 14px 6px;
  margin: 0 0 6px 0;
  border-bottom: none;
  display: flex;
  flex-wrap: nowrap;
  overflow-x: auto;
  overflow-y: hidden;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none; /* Firefox */
}
.gradio-container .tab-nav::-webkit-scrollbar{display:none;}

/* Divider under tab pills (prevents the line from visually "cutting" the buttons) */
.gradio-container .tabs > .tab-nav::after,
.gradio-container .tab-nav::after{
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 1px;
  background: rgba(15, 23, 42, 0.08);
  pointer-events: none;
}

/* Segmented control look for tab buttons */
[role="tablist"] > button[role="tab"]{
  border: 1px solid rgba(15, 23, 42, 0.14);
  background: rgba(255,255,255,0.88);
  border-radius: var(--rhk-radius-pill);
  padding: 8px 12px;
  font-weight: 650;
  color: rgba(15,23,42,0.78);
  box-shadow: var(--rhk-shadow-sm);
}
[role="tablist"] > button[role="tab"][aria-selected="true"]{
  background: #ffffff;
  border-color: rgba(37, 99, 235, 0.35);
  color: var(--rhk-color-text);
  font-weight: 800;
  box-shadow: var(--rhk-shadow-sm);
}

/* Small completion dot appended to each tab */
.rhk-tab-dot{
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: var(--rhk-radius-pill);
  margin-left: 8px;
  background: rgba(15,23,42,0.16);
  vertical-align: middle;
}
.rhk-tab-dot.is-filled{ background: rgba(16, 185, 129, 0.95); }
.rhk-tab-dot.is-active{ box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12); }

/* Subtitle line below tabs (orientation) */
#rhk_tab_subtitle{
  display: block;
  margin: 0 0 8px 0;
  padding: 0 4px;
  font-size: 13px;
  color: rgba(15, 23, 42, 0.65);
  font-weight: 600;
}


/* Tabs: robust gegen Gradio 6.x Overflow-Button (… / three-dots) */
#rhk_input_tabs [role="tablist"] button:not([role="tab"]),
#rhk_output_tabs [role="tablist"] button:not([role="tab"]){
  display: none;
}
#rhk_input_tabs [role="tab"], #rhk_output_tabs [role="tab"]{
  white-space: normal;
  text-overflow: clip;
  overflow: visible;
  max-width: none;
}

/* --------------------------------------------------------------
   Force all tabs into the visible pill strip so Quick-Nav works
   language-independently via [data-tab-id].
   Gradio's Svelte tab-strip hides surplus tabs inside an
   ".overflow-menu" dropdown when the row overflows. The menu is
   unreliable for programmatic clicks (Svelte handler does not
   always re-dispatch change_tab), so we suppress it and let the
   pill row wrap onto a second line instead.
   -------------------------------------------------------------- */
#rhk_input_tabs .tab-wrapper,
#rhk_output_tabs .tab-wrapper{
  overflow: visible;
  flex-wrap: wrap;
}
#rhk_input_tabs .overflow-menu,
#rhk_output_tabs .overflow-menu{
  display: none !important;
}
#rhk_input_tabs .tab-container:not(.visually-hidden),
#rhk_output_tabs .tab-container:not(.visually-hidden){
  flex-wrap: wrap;
  overflow: visible;
  max-width: none;
  row-gap: 4px;
}
#rhk_input_tabs .tab-container.visually-hidden,
#rhk_output_tabs .tab-container.visually-hidden{
  position: absolute;
  left: -9999px;
  width: 1px;
  height: 1px;
  overflow: hidden;
  pointer-events: none;
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
  white-space: normal;
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
  border-radius: var(--rhk-radius-sm);
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
  border-radius: var(--rhk-radius-md);
  padding: 14px 16px;
  box-shadow: var(--rhk-shadow-sm);
}
.card-title { font-size: 16px; font-weight: 700; margin-bottom: 6px; }
.row { display:flex; gap:16px; flex-wrap: wrap; margin: 6px 0; }
.badges { display:flex; gap:8px; flex-wrap:wrap; margin: 10px 0 0; }
.badge { padding: 5px 10px; border-radius: var(--rhk-radius-pill); font-size: 12px; border: 1px solid var(--border); background: rgba(0,0,0,0.03); }
.badge-blue { background: rgba(59,130,246,0.12); border-color: rgba(59,130,246,0.25); }
.badge-purple { background: rgba(168,85,247,0.06); border-color: rgba(168,85,247,0.75); }
.badge-orange { background: rgba(249,115,22,0.12); border-color: rgba(249,115,22,0.25); }
.badge-teal { background: rgba(20,184,166,0.12); border-color: rgba(20,184,166,0.25); }
.badge-red { background: rgba(239,68,68,0.12); border-color: rgba(239,68,68,0.25); }

.badge-low { background: rgba(34,197,94,0.14); border-color: rgba(34,197,94,0.30); }
.badge-intermediate { background: rgba(234,179,8,0.16); border-color: rgba(234,179,8,0.32); }
.badge-intermediate-high { background: rgba(249,115,22,0.16); border-color: rgba(249,115,22,0.32); }
.badge-high { background: rgba(239,68,68,0.16); border-color: rgba(239,68,68,0.32); }
.badge-na { background: rgba(0,0,0,0.05); border-color: rgba(0,0,0,0.10); }
.muted { color: rgba(0,0,0,0.55); }
.small { font-size: 12px; color: rgba(0,0,0,0.55); }
.subhead { font-size: 13px; color: rgba(0,0,0,0.65); margin-top: -6px; }
.whatsnew{ margin-top: 6px; font-size: 13px; color: rgba(0,0,0,0.65); }
.whatsnew-details{
  margin: 4px 0 0 0;
  font-size: 12px;
  color: rgba(15, 23, 42, 0.55);
}
.whatsnew-details > summary{
  cursor: pointer;
  font-weight: 600;
  color: var(--ds-text-secondary);
  padding: 2px 0;
  list-style: none;
  user-select: none;
}
.whatsnew-details > summary::-webkit-details-marker{ display: none; }
.whatsnew-details > summary::before{
  content: "▸ ";
  display: inline-block;
  width: 1em;
  transition: transform 120ms ease;
}
.whatsnew-details[open] > summary::before{
  content: "▾ ";
}
.whatsnew-details > .whatsnew{
  padding: 6px 0 2px 1em;
}


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
  border-radius: var(--rhk-radius-md);
  padding: 18px 18px;
  background: rgba(255,255,255,0.98);
  box-shadow: var(--rhk-shadow-sm);
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
  flex-wrap: wrap;
  overflow-x: visible;
  overflow-y: visible;
}
.gradio-container button[aria-label="More"],
.gradio-container button[title="More"],
.gradio-container button[aria-label="Mehr"],
.gradio-container button[title="Mehr"],
.gradio-container .tab-nav__more,
.gradio-container .tab-nav__overflow,
.gradio-container .tab-nav__overflow-menu,
.gradio-container .tab-nav__overflowButton {
  display: none;
}

/* ------------------------------------------------------------------
   v27.2: Main tabs must stay visible and feel like a segmented control
   ------------------------------------------------------------------ */
.gradio-container .tabs > .tab-nav,
.gradio-container .tab-nav{
  position: sticky;
  top: 86px; /* below the glass topbar */
  z-index: 9500;
  background: rgba(246,247,251,0.92);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  padding: 8px 6px;
  margin: 0 0 6px 0;
  border-bottom: 1px solid rgba(15,23,42,0.08);
}

.gradio-container .tab-nav button{
  flex: 0 0 auto;
  border-radius: var(--rhk-radius-pill);
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 700;
  border: 1px solid rgba(15,23,42,0.10);
  background: rgba(255,255,255,0.75);
  color: var(--rhk-color-text);
  box-shadow: var(--rhk-shadow-sm);
  margin: 4px 6px 4px 0;
}
.gradio-container .tab-nav button:hover{
  filter: brightness(0.985);
}
.gradio-container .tab-nav button[aria-selected="true"]{
  background: #ffffff;
  border: 1px solid rgba(15,23,42,0.18);
  box-shadow: var(--rhk-shadow-sm);
  font-weight: 800;
}

/* Subtitle line directly under the tabs */
#rhk_tab_subtitle{
  position: sticky;
  top: 138px; /* tabs + spacing */
  z-index: 9400;
  max-width: 1200px;
  margin: 0 auto 10px auto;
  padding: 0 16px;
  font-size: 12.5px;
  color: rgba(15,23,42,0.65);
  font-weight: 600;
}

/* Completion dot on each tab */
.rhk-tab-dot{
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: var(--rhk-radius-pill);
  margin-left: 8px;
  border: 1px solid rgba(15,23,42,0.18);
  background: rgba(148,163,184,0.35);
  vertical-align: middle;
}
.rhk-tab-dot.is-filled{ background: rgba(34,197,94,0.55); border-color: rgba(34,197,94,0.75); }
.rhk-tab-dot.is-active{ box-shadow: 0 0 0 3px rgba(59,130,246,0.12); }

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
  border-radius: var(--rhk-radius-md);
  box-shadow: var(--rhk-shadow-sm);
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
  border-radius: var(--rhk-radius-sm);
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
  border-radius: var(--rhk-radius-pill);
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
/* Shared sticky-bar look: summary + pre-cath must be identical */
.rhk-summarybar,
.rhk-pre-cath-bar{
  display:flex;
  flex-wrap:wrap;
  align-items:center;
  gap:8px;
  padding:10px 12px;
  background: rgba(255,255,255,0.78);
  backdrop-filter: blur(14px) saturate(160%%);
  -webkit-backdrop-filter: blur(14px) saturate(160%%);
  border: 1px solid rgba(0,0,0,0.06);
  border-radius: var(--rhk-radius-md);
  box-shadow: var(--rhk-shadow-sm);
}
.rhk-summarybar .rhk-schip{
  padding: 6px 12px;
  border-radius: var(--rhk-radius-pill);
  font-size: 12px;
  font-weight: 650;
  background: rgba(255,255,255,0.55);
  border: 1px solid rgba(0,0,0,0.06);
  color: rgba(15,23,42,0.8);
  white-space: nowrap;
}

.rhk-summarybar .rhk-schip.rhk-has-tip{
  position: relative;
  cursor: help;
}
.rhk-summarybar .rhk-schip .rhk-tip{
  position: absolute;
  left: 0;
  bottom: calc(100% + 8px);
  z-index: 9999;
  max-width: 360px;
  white-space: normal;
  line-height: 1.25;
  padding: 8px 10px;
  border-radius: var(--ds-radius-sm);
  font-size: 12px;
  font-weight: 500;
  background: rgba(15,23,42,0.96);
  color: rgba(255,255,255,0.95);
  border: 1px solid rgba(255,255,255,0.12);
  box-shadow: var(--rhk-shadow-sm);
  opacity: 0;
  transform: translateY(3px);
  pointer-events: none;
  transition: opacity .12s ease, transform .12s ease, visibility .12s ease;
  visibility: hidden;
}
.rhk-summarybar .rhk-schip.rhk-has-tip:hover .rhk-tip,
.rhk-summarybar .rhk-schip.rhk-has-tip:focus .rhk-tip{
  opacity: 1;
  transform: translateY(0);
  visibility: visible;
}

.rhk-summarybar .rhk-schip--hint{
  white-space: normal;
  flex: 1 1 100%;
  line-height: 1.25;
}

.rhk-summarybar .rhk-schip--good{ background: rgba(34,197,94,0.14); border-color: rgba(34,197,94,0.26); color:#166534; }
.rhk-summarybar .rhk-schip--warn{ background: rgba(234,179,8,0.16); border-color: rgba(234,179,8,0.28); color:#92400e; }
.rhk-summarybar .rhk-schip--orange{ background: rgba(249,115,22,0.16); border-color: rgba(249,115,22,0.28); color:#9a3412; }
.rhk-summarybar .rhk-schip--bad{ background: rgba(239,68,68,0.12); border-color: rgba(239,68,68,0.22); color:#b91c1c; }
.rhk-summarybar .rhk-schip--info{ background: rgba(37,99,235,0.12); border-color: rgba(37,99,235,0.22); color:#1d4ed8; }

.rhk-summary-stack{
  display:flex;
  flex-direction:column;
  gap:8px;
}

.rhk-safety-todo{
  border: 1px solid rgba(0,0,0,0.08);
  background: rgba(255,255,255,0.88);
  border-radius: var(--rhk-radius-md);
  box-shadow: var(--rhk-shadow-sm);
  padding: 10px 12px;
}

.rhk-todo-head{
  font-size: 13px;
  font-weight: 800;
  color: var(--rhk-color-text);
  margin-bottom: 8px;
}

.rhk-todo-grid{
  display:grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 8px;
}

.rhk-todo-col{
  border: 1px solid rgba(0,0,0,0.08);
  border-radius: var(--rhk-radius-sm);
  background: rgba(248,250,252,0.9);
  padding: 8px;
  min-height: 64px;
}

.rhk-todo-col-head{
  font-size: 12px;
  font-weight: 760;
  color: rgba(15,23,42,0.82);
  margin-bottom: 4px;
}

.rhk-todo-list{
  list-style: none;
  margin: 0;
  padding: 0;
  display:flex;
  flex-direction:column;
  gap: 6px;
}

.rhk-todo-item-title{
  font-size: 12px;
  line-height: 1.25;
  color: var(--rhk-color-text);
}

.rhk-todo-meta{
  margin-top: 2px;
  font-size: 11px;
  line-height: 1.2;
  color: rgba(15,23,42,0.64);
}

.rhk-todo-item--critical{
  border-left: 3px solid rgba(220,38,38,0.7);
  padding-left: 6px;
}
.rhk-todo-item--important{
  border-left: 3px solid rgba(217,119,6,0.7);
  padding-left: 6px;
}
.rhk-todo-item--hint{
  border-left: 3px solid rgba(37,99,235,0.6);
  padding-left: 6px;
}

.rhk-todo-empty{
  font-size: 12px;
  color: rgba(15,23,42,0.56);
}

.rhk-todo-subhead{
  margin-top: 6px;
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 760;
  color: var(--rhk-color-text);
}

.rhk-check-list{
  list-style: none;
  margin: 0;
  padding: 0;
  display:flex;
  flex-direction:column;
  gap: 6px;
}

.rhk-check-item{
  border: 1px solid rgba(0,0,0,0.08);
  border-radius: var(--ds-radius-sm);
  padding: 6px 8px;
  display:flex;
  flex-direction:column;
  gap: 1px;
  background: rgba(255,255,255,0.92);
}
.rhk-check-item--ok{ border-color: rgba(34,197,94,0.28); background: rgba(34,197,94,0.08); }
.rhk-check-item--hint{ border-color: rgba(37,99,235,0.24); background: rgba(37,99,235,0.07); }
.rhk-check-item--important{ border-color: rgba(217,119,6,0.26); background: rgba(217,119,6,0.08); }
.rhk-check-item--critical{ border-color: rgba(220,38,38,0.28); background: rgba(220,38,38,0.08); }

.rhk-check-title{
  font-size: 12px;
  font-weight: 700;
  color: var(--rhk-color-text);
}
.rhk-check-detail{
  font-size: 11px;
  color: rgba(15,23,42,0.7);
}

.rhk-field-marker-payload{ display:none !important; }

.rhk-field .rhk-field-alert-dot{
  display:inline-block;
  width:8px;
  height:8px;
  border-radius: var(--rhk-radius-pill);
  margin-left:6px;
  vertical-align:middle;
  border:1px solid rgba(0,0,0,0.22);
}
.rhk-field .rhk-field-alert-dot--critical{
  background:#dc2626;
  border-color:#b91c1c;
}
.rhk-field .rhk-field-alert-dot--important{
  background:#f59e0b;
  border-color:#d97706;
}
.rhk-field .rhk-field-alert-dot--hint{
  background:#2563eb;
  border-color:#1d4ed8;
}

.rhk-field.rhk-field-marker-critical{
  border: 1px solid rgba(220,38,38,0.36);
  box-shadow: 0 0 0 2px rgba(220,38,38,0.12);
  border-radius: var(--rhk-radius-sm);
}
.rhk-field.rhk-field-marker-important{
  border: 1px solid rgba(217,119,6,0.34);
  box-shadow: 0 0 0 2px rgba(217,119,6,0.10);
  border-radius: var(--rhk-radius-sm);
}
.rhk-field.rhk-field-marker-hint{
  border: 1px solid rgba(37,99,235,0.30);
  box-shadow: 0 0 0 2px rgba(37,99,235,0.10);
  border-radius: var(--rhk-radius-sm);
}

@media (max-width: 1100px){
  .rhk-todo-grid{
    grid-template-columns: 1fr;
  }
}


/* ------------------------------------------------------------------
   Spiro-Logic Wizard (CPET live education)
   ------------------------------------------------------------------ */
.spiro-edu{
  border: 1px solid rgba(0,0,0,0.06);
  background: rgba(255,255,255,0.96);
  border-radius: var(--rhk-radius-md);
  padding: 12px 12px;
  box-shadow: var(--rhk-shadow-sm);
}
.spiro-edu--overall{ background: rgba(168, 85, 247, 0.06); }
.spiro-edu__title{
  font-size: 13px;
  font-weight: 850;
  color: var(--rhk-color-text);
  margin-bottom: 6px;
}
.spiro-edu__sub{
  font-size: 12px;
  font-weight: 800;
  color: rgba(15, 23, 42, 0.72);
  margin-top: 10px;
  margin-bottom: 4px;
}
.spiro-edu__feedback{
  font-size: 13px;
  line-height: 1.35;
  color: rgba(15, 23, 42, 0.85);
}
.spiro-edu__teach{
  font-size: 12px;
  line-height: 1.35;
  color: rgba(15, 23, 42, 0.78);
}
.spiro-edu__follow ul{ margin: 6px 0 0 18px; }
.spiro-edu__follow li{ margin: 4px 0; }

/* Live chip row for predicted values / CI / OUES / VE-VCO2-nadir / VAT */
.cpet-chips{
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 8px 0 4px 0;
}
.cpet-chip{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  font-size: 11px;
  line-height: 1.35;
  border-radius: 999px;
  background: rgba(241, 245, 249, 0.88);
  border: 1px solid rgba(15, 23, 42, 0.08);
  color: rgba(15, 23, 42, 0.82);
}
.cpet-chip-k{ font-weight: 750; color: rgba(15, 23, 42, 0.6); }
.cpet-chip-v{ font-weight: 800; color: rgba(15, 23, 42, 0.9); }
.cpet-chip--good{
  background: rgba(34, 197, 94, 0.10);
  border-color: rgba(34, 197, 94, 0.28);
}
.cpet-chip--warn{
  background: rgba(234, 179, 8, 0.10);
  border-color: rgba(234, 179, 8, 0.34);
}
.cpet-chip--bad{
  background: rgba(239, 68, 68, 0.10);
  border-color: rgba(239, 68, 68, 0.30);
}

/* CPET 9 Felder Übersicht (didaktisches Raster, keine klinische Automatik) */
.cpet9-grid{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: 8px;
}
.cpet9-cell{
  border: 1px solid rgba(0,0,0,0.06);
  background: rgba(248,250,252,0.92);
  border-radius: var(--rhk-radius-md);
  padding: 8px 10px;
}
.cpet9-cell--good{ border-color: rgba(34,197,94,0.22); }
.cpet9-cell--warn{ border-color: rgba(234,179,8,0.28); }
.cpet9-cell--bad{ border-color: rgba(239,68,68,0.22); }
.cpet9-k{
  font-size: 11px;
  font-weight: 850;
  color: rgba(15, 23, 42, 0.72);
  margin-bottom: 4px;
}
.cpet9-v{
  font-size: 12px;
  line-height: 1.35;
  color: rgba(15, 23, 42, 0.86);
}



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
  border-radius: var(--rhk-radius-md);
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
  gap: 8px;
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

/* ------------------------------------------------------------------
   CPET / Spiro-Logic Wizard: harden against "pulsing" / transparency
   Some browsers show perceived flicker when Gradio toggles busy states
   while cards use translucent backgrounds. We enforce full opacity and
   disable transitions/animations inside the CPET card.
   ------------------------------------------------------------------ */
.rhk-cpet-card,
.rhk-cpet-card * {
  opacity: 1 !important;
  filter: none !important;
  animation: none !important;
  transition: none !important;
}
.rhk-cpet-card{
  background: #ffffff;
}
.rhk-cpet-card .rhk-sec-body{
  background: #ffffff;
}
.rhk-cpet-card .rhk-sec-head{
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
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
  border-radius: var(--ds-radius-sm) !important;
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
  border-radius: var(--rhk-radius-md);
  padding: 10px 12px;
  box-shadow: var(--rhk-shadow-sm);
  transition: transform .12s ease, box-shadow .12s ease;
}
#pmods_cards .pmod-card:hover{ transform: translateY(-1px); box-shadow: var(--rhk-shadow-sm); }
#pmods_cards .pmod-title{ font-weight: 800; font-size: 13px; color: var(--rhk-color-text); margin-bottom: 4px; }
#pmods_cards .pmod-sub{ font-size: 12px; color: rgba(15,23,42,0.65); margin-bottom: 8px; }
#pmods_cards .pmod-meta{ display:flex; gap:6px; flex-wrap:wrap; }
#pmods_cards .pmod-chip{ padding: 4px 10px; border-radius: var(--rhk-radius-pill); font-size: 11px; font-weight: 700; border: 1px solid rgba(0,0,0,0.08); background: rgba(255,255,255,0.55); color: rgba(15,23,42,0.75); }
#pmods_cards .pmod-chip--auto{ background: rgba(37,99,235,0.12); border-color: rgba(37,99,235,0.22); color:#1d4ed8; }
#pmods_cards .pmod-chip--manual{ background: rgba(168,85,247,0.06); border-color: rgba(168,85,247,0.75); color:#6d28d9; }
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
  background: linear-gradient(90deg, rgba(37,99,235,0.10), rgba(168,85,247,0.06));/* unified accent-subtle */
  border: 1px solid rgba(37,99,235,0.22);
  border-radius: var(--rhk-radius-md);
  padding: 10px 12px;
  font-weight: 900;
  box-shadow: var(--rhk-shadow-sm);
}
#pmods_accordion summary:hover,
#pmods_accordion button:hover{
  background: linear-gradient(90deg, rgba(37,99,235,0.14), rgba(168,85,247,0.06));
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
  border-radius: var(--rhk-radius-md);
  padding: 12px 12px;
  box-shadow: var(--rhk-shadow-sm);
}
#rhk_compare_overview .cmp-head{ display:flex; gap:10px; flex-wrap:wrap; align-items:center; margin-bottom: 8px; }
#rhk_compare_overview .cmp-title{ font-weight: 900; font-size: 13px; color: var(--rhk-color-text); }
#rhk_compare_overview .cmp-note{ font-size: 12px; color: rgba(15,23,42,0.6); }
#rhk_compare_overview .cmp-date{ font-size: 11px; font-weight: 700; opacity: 0.75; }
#rhk_compare_overview table{ width:100%%; border-collapse: separate; border-spacing: 0; overflow:hidden; border-radius: var(--rhk-radius-md); }
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
.docx-box{border:1px solid rgba(0,0,0,.10);border-radius: var(--rhk-radius-md);padding:10px 12px;background:#fff}
.docx-box.warn{border-color:rgba(220,70,70,.35);background:rgba(220,70,70,.04)}
/* DOCX Import Ampel (UI only; payload provides green/yellow/red) */
.docx-box.good{border-color:rgba(34,197,94,.38);background:rgba(34,197,94,.06)}
.docx-box.yellow{border-color:rgba(234,179,8,.45);background:rgba(234,179,8,.06)}
.docx-box.bad{border-color:rgba(239,68,68,.40);background:rgba(239,68,68,.06)}
.docx-title{font-weight:900;margin:0 0 6px 0}
.docx-row{display:flex;flex-wrap:wrap;gap:8px}
.chip{display:inline-flex;gap:6px;align-items:center;padding:5px 10px;border-radius: var(--rhk-radius-pill);border:1px solid rgba(0,0,0,.10);background:rgba(0,0,0,.02);font-size:12px}
.chip-lab{color:rgba(0,0,0,.60);font-weight:800}
.small{margin-top:6px;color:rgba(0,0,0,.70);font-size:12px;line-height:1.35}

.docx-muted{margin-top:6px;color:rgba(0,0,0,.62);font-size:12px;line-height:1.35}
.docx-details{margin-top:8px}
.docx-details summary{cursor:pointer;font-weight:900;color: var(--rhk-color-text);margin:6px 0}
.docx-list{margin:6px 0 0 18px;color:rgba(0,0,0,.72);font-size:12px;line-height:1.35}
.rhk-tbl{width:100%;border-collapse:separate;border-spacing:0;overflow:hidden;border-radius: var(--rhk-radius-sm);border:1px solid rgba(0,0,0,.08);margin-top:8px}
.rhk-tbl th,.rhk-tbl td{padding:6px 8px;font-size:12px;border-bottom:1px solid rgba(0,0,0,.06);vertical-align:top}
.rhk-tbl th{text-align:left;background:rgba(0,0,0,.03);font-weight:900;color:rgba(15,23,42,.8)}
.rhk-tbl tr:last-child td{border-bottom:none}
/* ------------------------------------------------------------------
   RHK Viz Grid
   ------------------------------------------------------------------ */
.rhk-viz-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
@media (max-width: 1200px){.rhk-viz-grid{grid-template-columns:1fr}}
.rhk-viz-item{width:100%}

/* ------------------------------------------------------------------
   Startseite: Tool-Disclaimer (Footer)
   ------------------------------------------------------------------ */
#rhk_tool_disclaimer_wrapper{margin-top:14px;padding:0 14px 12px 14px}
#rhk_tool_disclaimer{border-top:1px solid rgba(0,0,0,.08);padding-top:10px}
.rhk-disclaimer-inner{max-width:1200px;margin:0 auto}
.rhk-disclaimer-title{font-weight:900;font-size:12px;color:rgba(15,23,42,.75);margin:0 0 4px 0}
.rhk-disclaimer-text{font-size:11px;line-height:1.35;color:rgba(15,23,42,.62)}

/* ------------------------------------------------------------------
   v2.0 Unified Design System (token-first override layer)
   Purpose: final visual source of truth above all legacy CSS fragments.
   ------------------------------------------------------------------ */
:root,
.gradio-container,
html,
body{
  color-scheme: light !important;
  --ds-font-sans: "Avenir Next", "SF Pro Text", "Segoe UI Variable", "Noto Sans SC", "PingFang SC", "Microsoft YaHei", "Noto Sans", "Helvetica Neue", sans-serif;

  --ds-space-1: 4px;
  --ds-space-2: 8px;
  --ds-space-3: 12px;
  --ds-space-4: 16px;
  --ds-space-5: 24px;
  --ds-space-6: 32px;
  --ds-space-7: 48px;

  --ds-radius-sm: 10px;
  --ds-radius-md: 16px;
  --ds-radius-lg: 16px;
  --ds-radius-xl: 16px;
  --ds-radius-pill: 999px;

  --ds-bg: #f4f6f8;
  --ds-surface: #ffffff;
  --ds-surface-soft: #f8fafc;
  --ds-text: #0f172a;
  --ds-text-secondary: #334155;
  --ds-text-muted: #64748b;
  --ds-accent: #0a6fd9;
  --ds-accent-strong: #0857a8;
  --ds-accent-soft: rgba(10, 111, 217, 0.10);
  --ds-border-subtle: rgba(15, 23, 42, 0.10);
  --ds-border-strong: rgba(15, 23, 42, 0.18);
  --ds-shadow-soft: 0 1px 4px rgba(15,23,42,0.06);
  --ds-shadow-medium: 0 2px 10px rgba(15,23,42,0.09);
  --ds-shadow-strong: 0 6px 24px rgba(15,23,42,0.14);
  --ds-shadow-focus: 0 0 0 3px rgba(10, 111, 217, 0.22);

  /* Typography scale — use --ds-font-sm for meta/chips, --ds-font-base for
     sustained reading, --ds-font-lg for section titles. */
  --ds-font-xs: 11px;
  --ds-font-sm: 12px;
  --ds-font-base: 13px;
  --ds-font-md: 14px;
  --ds-font-lg: 16px;

  --rhk-radius-sm: 8px;
  --rhk-radius-md: 16px;
  --rhk-radius-lg: 22px;
  --rhk-radius-pill: 999px;
  --rhk-shadow-sm: 0 1px 4px rgba(15,23,42,0.06);
  --rhk-shadow-md: 0 2px 8px rgba(15,23,42,0.08);
  --rhk-shadow-lg: 0 4px 16px rgba(15,23,42,0.10);
  --rhk-shadow-focus: 0 0 0 2px rgba(139,92,246,0.25);
  --rhk-color-bg: #ffffff;
  --rhk-color-surface: #f8fafc;
  --rhk-color-border: #e2e8f0;
  --rhk-color-text: #0f172a;
  --rhk-color-text-muted: #64748b;
  --rhk-color-text-light: #64748b;
  --rhk-color-primary: #7c3aed;
  --rhk-color-primary-light: rgba(139,92,246,0.08);
  --rhk-color-success: #059669;
  --rhk-color-warning: #d97706;
  --rhk-color-danger: #dc2626;
  --rhk-color-info: #0284c7;
  --rhk-space-xs: 4px;
  --rhk-space-sm: 8px;
  --rhk-space-md: 16px;
  --rhk-space-lg: 24px;
  --rhk-space-xl: 32px;
  --rhk-font-sm: 0.8125rem;
  --rhk-font-base: 0.875rem;
  --rhk-font-lg: 1rem;

  --ds-success: #15803d;
  --ds-warning: #b45309;
  --ds-error: #b91c1c;
  --ds-info: #1d4ed8;

  --body-background-fill: var(--ds-bg) !important;
  --background-fill-primary: var(--ds-surface) !important;
  --background-fill-secondary: var(--ds-surface-soft) !important;
  --block-background-fill: var(--ds-surface) !important;
  --block-border-color: var(--ds-border-subtle) !important;
  --input-background-fill: var(--ds-surface) !important;
  --input-border-color: var(--ds-border-strong) !important;
  --body-text-color: var(--ds-text) !important;
  --input-text-color: var(--ds-text) !important;
}

html,
body{
  font-family: var(--ds-font-sans) !important;
  color: var(--ds-text) !important;
  background:
    radial-gradient(980px 420px at 12% -12%, rgba(10, 111, 217, 0.08), transparent 70%),
    radial-gradient(760px 360px at 98% -10%, rgba(15, 23, 42, 0.05), transparent 74%),
    var(--ds-bg) !important;
}

.gradio-container,
.gradio-container *,
.gradio-container input,
.gradio-container textarea,
.gradio-container select,
.gradio-container button,
.gradio-container .prose,
.gradio-container .markdown{
  font-family: var(--ds-font-sans) !important;
}

.gradio-container{
  max-width: 1760px !important;
  margin: 0 auto !important;
  padding-left: var(--ds-space-3) !important;
  padding-right: var(--ds-space-3) !important;
}

/* App shell */
#rhk_topbar_wrapper .rhk-glass-island,
#rhk_topbar .rhk-topbar{
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid var(--ds-border-subtle);
  border-radius: var(--ds-radius-xl);
  box-shadow: var(--ds-shadow-soft);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}
#rhk_topbar_wrapper .rhk-glass-island::before{
  opacity: 0.42;
}
#rhk_topbar_wrapper .rhk-main-title,
#rhk_topbar .rhk-title{
  color: var(--ds-text);
}
#rhk_topbar_wrapper .rhk-sub-title,
#rhk_topbar .rhk-subtitle{
  color: var(--ds-text-muted);
}
#rhk_topbar_wrapper .rhk-status-chip,
#rhk_topbar .rhk-chip{
  border: 1px solid var(--ds-border-subtle);
  background: rgba(248, 250, 252, 0.94);
  color: var(--ds-text-secondary);
}
#rhk_topbar_wrapper .rhk-status-chip.primary,
#rhk_topbar .rhk-chip--primary{
  border-color: rgba(10, 111, 217, 0.30);
  background: var(--ds-accent-soft);
  color: var(--ds-accent-strong);
}

#rhk_workflow_overview{
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid var(--ds-border-subtle);
  border-radius: var(--ds-radius-lg);
  box-shadow: var(--ds-shadow-soft);
  padding: var(--ds-space-4);
}
#rhk_workflow_overview .rhk-wf-title-row{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ds-space-2);
}
#rhk_workflow_overview .rhk-wf-title{
  font-size: 18px;
  font-weight: 700;
  color: var(--ds-text);
  margin: 0;
}
#rhk_workflow_overview .rhk-wf-toggle{
  border: 1px solid var(--ds-border-subtle);
  border-radius: var(--ds-radius-pill);
  background: var(--ds-surface);
  color: var(--ds-text-secondary);
  min-height: 30px;
  padding: 0 var(--ds-space-3);
  font-size: 12px;
  font-weight: 620;
  cursor: pointer;
  transition: background 150ms ease, border-color 150ms ease, color 150ms ease;
}
#rhk_workflow_overview .rhk-wf-toggle:hover{
  background: var(--ds-surface-soft);
  border-color: rgba(10, 111, 217, 0.30);
  color: var(--ds-text);
}
#rhk_workflow_overview .rhk-wf-body{
  margin-top: var(--ds-space-2);
}
#rhk_workflow_overview.is-collapsed .rhk-wf-body{
  display: none !important;
}
#rhk_workflow_overview .rhk-wf-col{
  border: 1px solid var(--ds-border-subtle);
  border-radius: var(--ds-radius-md);
  background: var(--ds-surface-soft);
  padding: 10px 12px;
}
#rhk_workflow_overview .rhk-wf-head{
  color: var(--ds-text-secondary);
  font-size: var(--ds-font-sm);
  font-weight: 700;
  letter-spacing: .02em;
  text-transform: uppercase;
  margin: 0 0 6px 0;
}
#rhk_workflow_overview li{
  margin: 4px 0;
  color: var(--ds-text);
  font-size: var(--ds-font-base);
  line-height: 1.45;
}
#rhk_workflow_overview .rhk-wf-step-label{
  font-weight: 620;
  color: var(--ds-text);
}
#rhk_workflow_overview .rhk-wf-step-label::after{
  content: ": ";
  font-weight: 620;
  color: var(--ds-text);
}
#rhk_workflow_overview .rhk-wf-step-label:lang(zh)::after{
  content: "\FF1A";
}
#rhk_workflow_overview .rhk-wf-step-text{
  color: var(--ds-text-secondary);
}
#rhk_workflow_overview .rhk-wf-line{
  color: var(--ds-text);
}
#rhk_workflow_overview .rhk-wf-tip{
  margin-top: 8px;
  font-size: var(--ds-font-base);
  color: var(--ds-text-secondary);
}
#rhk_workflow_overview .rhk-qnav{
  gap: var(--ds-space-2);
}
#rhk_workflow_overview .rhk-qnav-btn{
  border: 1px solid var(--ds-border-subtle);
  border-radius: var(--ds-radius-pill);
  background: var(--ds-surface);
  color: var(--ds-text-secondary);
  min-height: 30px;
  padding: 0 var(--ds-space-3);
  transition: background 150ms ease, border-color 150ms ease, box-shadow 150ms ease, transform 120ms ease;
}
#rhk_workflow_overview .rhk-qnav-btn:hover{
  background: var(--ds-surface-soft);
  border-color: rgba(10, 111, 217, 0.28);
  transform: translateY(-1px);
}
#rhk_workflow_overview .rhk-qnav-btn.is-active{
  background: var(--ds-accent-soft);
  border-color: rgba(10, 111, 217, 0.42);
  color: var(--ds-accent-strong);
}

/* Sticky bars */
.rhk-summarybar,
.rhk-pre-cath-bar{
  border: 1px solid var(--ds-border-subtle);
  border-radius: var(--ds-radius-lg);
  background: rgba(255, 255, 255, 0.90);
  box-shadow: var(--ds-shadow-soft);
}

/* Tabs and subtitle */
#rhk_input_tabs [role="tablist"],
#rhk_output_tabs [role="tablist"]{
  position: sticky !important;
  top: 96px !important;
  z-index: 9500 !important;
  display: flex !important;
  gap: var(--ds-space-2);
  padding: var(--ds-space-2);
  border: 1px solid var(--ds-border-subtle) !important;
  border-radius: var(--ds-radius-lg);
  background: rgba(255, 255, 255, 0.86) !important;
  box-shadow: var(--rhk-shadow-sm);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}
#rhk_input_tabs [role="tab"],
#rhk_output_tabs [role="tab"]{
  border-radius: var(--ds-radius-pill);
  border: 1px solid var(--ds-border-subtle) !important;
  background: var(--ds-surface) !important;
  color: var(--ds-text-secondary);
  font-size: 13px;
  font-weight: 620;
  min-height: 34px;
  padding: 0 var(--ds-space-3);
  transition: background 150ms ease, border-color 150ms ease, box-shadow 150ms ease, transform 120ms ease;
}
#rhk_input_tabs [role="tab"]:hover,
#rhk_output_tabs [role="tab"]:hover{
  background: var(--ds-surface-soft);
  transform: translateY(-1px);
}
#rhk_input_tabs [role="tab"][aria-selected="true"],
#rhk_output_tabs [role="tab"][aria-selected="true"]{
  border-color: rgba(10, 111, 217, 0.42);
  color: var(--ds-accent-strong);
  background: rgba(255, 255, 255, 0.98);
  box-shadow: var(--rhk-shadow-sm);
}
#rhk_tab_subtitle{
  position: sticky;
  top: 146px;
  z-index: 9400;
  margin: 0 0 var(--ds-space-2) 0;
  padding: 0 var(--ds-space-2);
  color: var(--ds-text-muted);
  font-size: 13px;
  font-weight: 560;
}

/* Generic cards and content surfaces */
.rhk-card,
.rhk-section-card,
#rhk_input_tabs .tabitem,
#rhk_output_tabs .tabitem,
.gradio-container details,
#pmods_cards .pmod-card,
#rhk_compare_overview .cmp-wrap,
.docx-box,
.rhk-scrollbox{
  border: 1px solid var(--ds-border-subtle);
  border-radius: var(--ds-radius-lg);
  background: var(--ds-surface);
  box-shadow: var(--ds-shadow-soft);
}
#rhk_input_tabs .tabitem,
#rhk_output_tabs .tabitem{
  padding: var(--ds-space-4);
  margin-bottom: var(--ds-space-4);
}
.rhk-screen{
  display: flex;
  flex-direction: column;
  gap: var(--ds-space-4);
}
.rhk-screen .rhk-card{
  margin: 0;
}
.rhk-section-card{
  padding: 0;
  overflow: hidden;
}
.rhk-sec-head{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ds-space-3);
  padding: 11px 14px;
  background: var(--rhk-color-surface);
  border-bottom: 1px solid var(--ds-border-subtle);
}
.rhk-sec-title{
  color: var(--ds-text);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.01em;
}
.rhk-sec-body{
  padding: var(--ds-space-4);
  background: var(--ds-surface);
}
.rhk-sec-progress .rhk-sec-count{
  font-size: 12px;
  color: var(--ds-text-muted);
  font-weight: 620;
}
.rhk-sec-bar{
  width: 64px;
  height: 4px;
  border-radius: var(--ds-radius-pill);
  background: rgba(15, 23, 42, 0.10);
}
.rhk-sec-bar > div{
  background: linear-gradient(90deg, var(--ds-accent), #2a92f5);
}

/* Top 3 migrated screens */
.rhk-screen-clinic .rhk-sec-head{
  background: linear-gradient(90deg, rgba(10, 111, 217, 0.10), #f8fafc 72%);
}
.rhk-screen-imaging .rhk-sec-head{
  background: linear-gradient(90deg, rgba(3, 105, 161, 0.10), #f8fafc 72%);
}
.rhk-screen-cpet .rhk-sec-head{
  background: linear-gradient(90deg, rgba(8, 145, 178, 0.10), #f8fafc 72%);
}

/* Form controls */
.gradio-container label,
.gradio-container [data-testid="block-label"],
.gradio-container .block-label{
  color: var(--ds-text-secondary);
  font-size: 13px;
  font-weight: 620;
}
.gradio-container input:not([type="checkbox"]):not([type="radio"]),
.gradio-container textarea,
.gradio-container select{
  min-height: 38px;
  border-radius: var(--ds-radius-sm);
  border: 1px solid var(--ds-border-strong);
  background: var(--ds-surface);
  color: var(--ds-text);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.55);
}
.gradio-container input::placeholder,
.gradio-container textarea::placeholder{
  color: var(--ds-text-muted);
}
.gradio-container input[type="checkbox"],
.gradio-container input[type="radio"]{
  accent-color: var(--ds-accent);
}

/* Buttons */
.gradio-container button,
.gradio-container .gr-button{
  min-height: 36px;
  border-radius: var(--ds-radius-sm);
  border: 1px solid var(--ds-border-strong);
  background: var(--ds-surface);
  color: var(--ds-text-secondary);
  font-weight: 620;
  box-shadow: var(--rhk-shadow-sm);
  transition: background 150ms ease, border-color 150ms ease, box-shadow 150ms ease, transform 120ms ease;
}
.gradio-container button:hover,
.gradio-container .gr-button:hover{
  border-color: rgba(10, 111, 217, 0.28);
  background: var(--ds-surface-soft);
  transform: translateY(-1px);
}
.gradio-container button:active,
.gradio-container .gr-button:active{
  transform: translateY(0);
}
#btn_generate_top button,
#btn_generate_bottom button{
  background: linear-gradient(180deg, #1a86eb, var(--ds-accent));
  color: #ffffff;
  border-color: rgba(8, 87, 168, 0.55);
  box-shadow: var(--rhk-shadow-sm);
}
#btn_generate_top button:hover,
#btn_generate_bottom button:hover{
  filter: brightness(1.02);
}
#btn_example_top button, #btn_example_bottom button,
#btn_clear_top button, #btn_clear_bottom button,
#btn_save_top button, #btn_save_bottom button,
#btn_load_top button, #btn_load_bottom button,
#btn_load_followup_top button, #btn_load_followup_bottom button,
#btn_docx_top button, #btn_docx_bottom button,
#btn_docx_prev button,
#rhk_copy_row button{
  background: var(--ds-surface);
  color: var(--ds-text-secondary);
}

/* Focus states: always visible for keyboard users */
.gradio-container button:focus-visible,
.gradio-container [role="tab"]:focus-visible,
.gradio-container input:not([type="checkbox"]):not([type="radio"]):focus-visible,
.gradio-container textarea:focus-visible,
.gradio-container select:focus-visible{
  outline: none;
  border-color: rgba(10, 111, 217, 0.62);
  box-shadow: var(--ds-shadow-focus);
}

/* Disabled */
.gradio-container button:disabled,
.gradio-container input:disabled,
.gradio-container textarea:disabled,
.gradio-container select:disabled{
  opacity: 0.6;
  cursor: not-allowed;
  box-shadow: none;
}

/* Tables and report panes */
.rhk-trend-table,
.rhk-tbl,
#rhk_compare_overview table,
.rhk-scrollbox table{
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  border: 1px solid var(--ds-border-subtle);
  border-radius: var(--ds-radius-md);
  overflow: hidden;
  background: var(--ds-surface);
}
.rhk-trend-table th,
.rhk-trend-table td,
.rhk-tbl th,
.rhk-tbl td,
#rhk_compare_overview th,
#rhk_compare_overview td,
.rhk-scrollbox th,
.rhk-scrollbox td{
  padding: 8px 10px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.08);
  color: var(--ds-text-secondary);
  font-size: 13px;
}
.rhk-trend-table th,
.rhk-tbl th,
#rhk_compare_overview th,
.rhk-scrollbox th{
  background: var(--ds-surface-soft);
  color: var(--ds-text);
  font-weight: 680;
}
.rhk-trend-table tr:last-child td,
.rhk-tbl tr:last-child td,
#rhk_compare_overview tr:last-child td,
.rhk-scrollbox tr:last-child td{
  border-bottom: none;
}
.rhk-scrollbox{
  max-height: 74vh;
  padding: var(--ds-space-3);
}
.rhk-scrollbox .prose,
.rhk-scrollbox .markdown,
.rhk-scrollbox .wrap{
  max-width: 78ch;
  margin: 0 auto;
  font-size: 14px;
  line-height: 1.52;
  color: var(--ds-text-secondary);
}

/* Modals / toast-like blocks */
.gradio-container [role="dialog"],
.gradio-container .modal,
.gradio-container .gr-dialog{
  border: 1px solid var(--ds-border-subtle);
  border-radius: var(--ds-radius-lg);
  background: var(--ds-surface);
  box-shadow: var(--rhk-shadow-sm);
}
.gradio-container .toast,
.gradio-container .gradio-toast,
.gradio-container [role="status"]{
  border: 1px solid var(--ds-border-subtle);
  border-radius: var(--ds-radius-sm);
  background: rgba(255, 255, 255, 0.96);
  color: var(--ds-text-secondary);
}

/* Motion */
@keyframes dsFadeInUp{
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
#rhk_workflow_overview,
#rhk_input_tabs .tabitem,
#rhk_output_tabs .tabitem{
  animation: dsFadeInUp 260ms cubic-bezier(0.22, 0.61, 0.36, 1) both;
}
@media (prefers-reduced-motion: reduce){
  *,
  *::before,
  *::after{
    animation: none;
    transition: none;
    scroll-behavior: auto;
  }
}

/* Responsive */
@media (max-width: 1160px){
  .gradio-container{
    padding-left: var(--ds-space-2);
    padding-right: var(--ds-space-2);
  }
  #rhk_input_tabs [role="tablist"],
  #rhk_output_tabs [role="tablist"]{
    top: 82px !important;
  }
  #rhk_tab_subtitle{
    top: 132px;
  }
}
@media (max-width: 900px){
  #rhk_workflow_overview{
    border-radius: var(--ds-radius-md);
    padding: var(--ds-space-3);
  }
  #rhk_copy_row{
    gap: var(--ds-space-2);
  }
}

/* Skip-to-content link (accessibility) */
.rhk-skip-link{
  position: absolute;
  top: -40px;
  left: 0;
  background: var(--rhk-color-primary);
  color: white;
  padding: 8px 16px;
  z-index: 10000;
  transition: top 0.3s;
  text-decoration: none;
  font-weight: 600;
  border-radius: 0 0 8px 0;
}
.rhk-skip-link:focus{
  top: 0;
}

/* Focus-within indicator for cards (accessibility) */
.rhk-card:focus-within{
  outline: 2px solid var(--rhk-color-primary);
  outline-offset: 2px;
}

/* ==================================================================
   TELLO-LAB DESIGN LAYER  (final override, adapted from tello-lab.com)
   ------------------------------------------------------------------
   Goal: apply the calm, modern Tello-Lab visual language (blue/cyan
   palette, Inter typography, subtle gradient accents, refined shadow
   scale) on top of the clinical RHK UI — without adopting any of the
   website's marketing-only effects (full-bleed dark heroes, pulse
   animations, particle backgrounds, animated gradient borders). The
   RHK app is a physician workflow tool; every change here has to pay
   its way in readability or hand-eye ergonomics, not branding.

   Scope:
   - Redefine the primary accent from purple (#7c3aed) to Tello-Lab
     blue (#2563eb), with cyan (#06b6d4) as a complementary accent.
   - Prefer Inter as the system-local font (no external font download
     — DSGVO-safe), keeping the existing Chinese fallback chain.
   - Tighten the shadow scale so hover states read as "gently raised"
     instead of "popping out" — single soft blue-tinted elevation.
   - Add a section-kicker + gradient-title pattern for scannable
     section headers in report/dashboard contexts.
   - Respect prefers-reduced-motion for every transition.
   ================================================================== */
:root,
.gradio-container,
html,
body{
  /* Tello-Lab palette tokens (direct hex to avoid var-alias chains). */
  --tl-primary:        #2563eb;
  --tl-primary-light:  #60a5fa;
  --tl-primary-deep:   #1d4ed8;
  --tl-cyan:           #06b6d4;
  --tl-cyan-light:     #7dd3fc;
  --tl-teal:           #0d9488;
  --tl-violet:         #8b5cf6;
  --tl-indigo:         #6366f1;
  --tl-deep:           #13243f;
  --tl-navy:           #1a3158;
  --tl-light:          #f0f9ff;
  --tl-text:           #1e293b;
  --tl-muted:          #64748b;
  --tl-gold:           #f59e0b;
  --tl-rose:           #f43f5e;

  /* Shadows — blue-tinted, softer than the slate defaults. */
  --tl-shadow-soft:    0 1px 3px rgba(15, 23, 42, 0.06),
                       0 1px 2px rgba(37, 99, 235, 0.04);
  --tl-shadow-medium:  0 4px 12px rgba(15, 23, 42, 0.08),
                       0 2px 4px rgba(37, 99, 235, 0.05);
  --tl-shadow-lift:    0 16px 44px rgba(37, 99, 235, 0.12),
                       0 4px 12px rgba(15, 23, 42, 0.06);
  --tl-focus-ring:     0 0 0 3px rgba(96, 165, 250, 0.55);

  /* Remap existing tokens to the Tello-Lab blue so legacy selectors
     inherit the new palette without touching ~4000 lines of rules. */
  --rhk-color-primary:        var(--tl-primary);
  --rhk-color-primary-light:  rgba(37, 99, 235, 0.08);
  --rhk-shadow-focus:         var(--tl-focus-ring);
  --ds-accent:                var(--tl-primary);
  --ds-accent-strong:         var(--tl-primary-deep);
  --ds-accent-soft:           rgba(37, 99, 235, 0.10);
  --ds-shadow-focus:          var(--tl-focus-ring);

  /* Inter — used locally if installed; otherwise fall through to the
     prior modern-system stack (SF/Segoe/Helvetica). No @font-face
     import so we don't ship a font file or ping Google Fonts. */
  --ds-font-sans: "Inter", "Inter var", "SF Pro Text", "Segoe UI Variable",
                  "Segoe UI", "Noto Sans SC", "PingFang SC", "Microsoft YaHei",
                  "Helvetica Neue", system-ui, -apple-system, sans-serif;
}

/* Lift the primary accent everywhere the prior purple showed up. */
.gradio-container a,
.gradio-container a:visited{
  color: var(--tl-primary-deep);
}
.gradio-container a:hover,
.gradio-container a:focus-visible{
  color: var(--tl-primary);
}

/* Focus ring: single source of truth — crisp blue halo, no double
   outlines. Keeps keyboard navigation obvious against any surface. */
:focus-visible{
  outline: none !important;
  box-shadow: var(--tl-focus-ring) !important;
  border-radius: 6px;
}
button:focus-visible,
[role="button"]:focus-visible,
a:focus-visible,
input:focus-visible,
textarea:focus-visible,
select:focus-visible{
  box-shadow: var(--tl-focus-ring) !important;
}

/* Card elevation — replace the flat legacy card with a softer, more
   physical surface that lifts on hover. Keep the motion tiny (2px)
   so forms don't "jiggle" as the cursor moves through dense inputs. */
.rhk-card,
.rhk-section-card{
  transition: transform 0.22s ease, box-shadow 0.22s ease;
}
.rhk-card:hover,
.rhk-section-card:hover{
  transform: translateY(-2px);
  box-shadow: var(--tl-shadow-lift);
}
@media (prefers-reduced-motion: reduce){
  .rhk-card,
  .rhk-section-card,
  .rhk-card:hover,
  .rhk-section-card:hover{
    transition: none;
    transform: none;
  }
}

/* Gradient accent strip — opt-in via .rhk-card--accent. Static gradient
   (no animation) so it reads as a decorative edge, not motion noise. */
.rhk-card.rhk-card--accent{
  position: relative;
}
.rhk-card.rhk-card--accent::before{
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg,
                var(--tl-primary) 0%,
                var(--tl-cyan) 50%,
                var(--tl-violet) 100%);
  border-top-left-radius: inherit;
  border-top-right-radius: inherit;
  pointer-events: none;
}

/* Section kicker + title pattern (Tello-Lab "section-sub" + "section-title").
   Tiny uppercase letter-spaced label over a bold heading — scannable
   section starts for report/dashboard views. */
.rhk-section-kicker{
  display: inline-block;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2.4px;
  text-transform: uppercase;
  color: var(--tl-primary);
  margin: 0 0 8px 0;
}
.rhk-section-kicker.is-muted{ color: var(--tl-muted); }
.rhk-section-kicker.is-gold{ color: var(--tl-gold); }
.rhk-section-title{
  font-size: 24px;
  font-weight: 800;
  color: var(--tl-text);
  line-height: 1.2;
  letter-spacing: -0.01em;
  margin: 0;
}
.rhk-section-title.is-gradient{
  background: linear-gradient(90deg, var(--tl-primary), var(--tl-cyan));
  -webkit-background-clip: text;
          background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
}

/* Primary CTA variant — adopt the rounded-pill gradient button used
   by Tello-Lab for the lead action. Opt-in via .rhk-btn-primary on the
   Gradio button wrapper; ordinary buttons stay with their current
   neutral-white look so the form doesn't turn into a wall of blue. */
.rhk-btn-primary button,
button.rhk-btn-primary{
  background: linear-gradient(135deg,
                var(--tl-primary) 0%,
                var(--tl-primary-deep) 100%) !important;
  color: #ffffff !important;
  border: 0 !important;
  font-weight: 700 !important;
  letter-spacing: 0.3px;
  border-radius: var(--rhk-radius-pill) !important;
  padding: 10px 22px !important;
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.28),
              0 0 0 1px rgba(255, 255, 255, 0.08) inset !important;
  transition: transform 0.2s ease, box-shadow 0.2s ease, filter 0.2s ease !important;
}
.rhk-btn-primary button:hover,
button.rhk-btn-primary:hover{
  transform: translateY(-1px);
  box-shadow: 0 8px 22px rgba(37, 99, 235, 0.38),
              0 0 0 1px rgba(255, 255, 255, 0.12) inset !important;
  filter: brightness(1.05);
}
@media (prefers-reduced-motion: reduce){
  .rhk-btn-primary button,
  button.rhk-btn-primary,
  .rhk-btn-primary button:hover,
  button.rhk-btn-primary:hover{
    transition: none !important;
    transform: none !important;
  }
}

/* Sticky-status bar: glass effect + soft divider. Preserves the
   existing layout, just replaces the solid white with a frosted pane
   so scrolled content subtly shows through. */
#sticky_case_status_wrapper,
#rhk_sticky_case_status{
  background: rgba(255, 255, 255, 0.92) !important;
  backdrop-filter: blur(14px) saturate(130%);
  -webkit-backdrop-filter: blur(14px) saturate(130%);
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
}

/* Small-chip accent — lift the `.chip` variant that represents a
   primary/positive signal with the Tello-Lab blue/cyan gradient.
   Neutral chips stay neutral. */
.chip.chip-primary{
  background: linear-gradient(135deg,
                rgba(37, 99, 235, 0.10),
                rgba(6, 182, 212, 0.08));
  border-color: rgba(37, 99, 235, 0.22);
  color: var(--tl-primary-deep);
  font-weight: 700;
}

/* Selection color — match the primary accent. */
::selection{
  background: var(--tl-primary);
  color: #ffffff;
}

/* ==================================================================
   TELLO-LAB DESIGN LAYER — PHASE 2: deeper adoption
   ------------------------------------------------------------------
   Pushes the Tello-Lab visual language beyond tokens to full visual
   parity on the surfaces a physician actually looks at every session:
   app title as gradient hero heading, tab bar as underline-on-active
   pattern, primary CTA as pill gradient, cards with animated accent
   strips and frosted-glass variant, mono-gradient numerals for
   hemodynamic metrics, subtle radial glow as page background.

   Design rules still in force:
   - Clinical content surfaces (form inputs, report prose) stay on
     flat white — gradients belong on *chrome*, not on data.
   - Every motion/transition is muted under prefers-reduced-motion.
   - No web fonts are downloaded; Inter is local-only with fallback.
   ================================================================== */

/* Page background — two soft radial glows, one blue top-right, one
   cyan lower-left, fading into the existing pale-slate canvas. Gives
   the empty margins a subtle Tello-Lab hero feel without dimming the
   content surfaces that sit on top. */
body,
.gradio-container{
  background:
    radial-gradient(ellipse 900px 520px at 85% -8%,
                    rgba(37, 99, 235, 0.06),
                    transparent 55%),
    radial-gradient(ellipse 700px 460px at -6% 30%,
                    rgba(6, 182, 212, 0.05),
                    transparent 55%),
    #f6f8fb !important;
}

/* Top-edge breathing room — the sticky glass header uses `top: 16px`,
   which means at scroll position 0 the header's upper edge sits at
   document y=0, hugging the viewport edge. Without a body padding-top
   this reads as "the top is cut off" — the rounded corners and soft
   shadow of the header get clipped by the browser chrome. Add a small
   top inset on the Gradio outer container so the header always has
   visible breathing room above it. */
.gradio-container,
body > gradio-app,
gradio-app > .main{
  padding-top: 18px !important;
}

/* Headings — tighten typography and give the first h1/h2 on any
   report or section the Tello-Lab "big bold" treatment. */
.gradio-container h1,
.gradio-container h2,
.gradio-container h3,
.gradio-container h4{
  color: var(--tl-text);
  font-weight: 800;
  letter-spacing: -0.015em;
}
.gradio-container h1{ font-size: clamp(26px, 2.6vw, 36px); line-height: 1.16; }
.gradio-container h2{ font-size: 22px; line-height: 1.22; }
.gradio-container h3{ font-size: 17px; line-height: 1.3; }

/* Gradient-text utility — opt-in on any heading/paragraph for the
   signature Tello-Lab blue→cyan wash. Also auto-applies to the
   floating app title inside the glass header island. */
.rhk-gradient-text,
.gradio-container h1.rhk-gradient-text,
.gradio-container h2.rhk-gradient-text,
.rhk-main-title{
  background: linear-gradient(90deg,
                var(--tl-deep) 0%,
                var(--tl-primary) 55%,
                var(--tl-cyan) 100%);
  -webkit-background-clip: text;
          background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent !important;
}

/* ---- Tabs: underline-on-active (Tello-Lab nav pattern) ----------
   Notes on the failed approaches we learned from, so the replacement
   doesn't re-break the same edges:

     – `all: unset` on `button[role="tab"]` is too aggressive: Gradio
       stores selected-state mechanics on the element (classes, event
       listeners, ARIA hooks), and resetting everything made the 6th
       tab disappear in v5. We stay with explicit property overrides.
     – The tablist `border-bottom` appeared to paint through the
       middle of tab labels in certain viewport/line-height
       combinations. We move the baseline to a `::after` pseudo on
       the tablist so it sits unambiguously *below* the buttons
       regardless of flex row height, and we no longer set a real
       bottom border on the tablist itself.
     – The strikethrough artifact in earlier screenshots was Gradio
       theme `text-decoration` leaking through span wrappers around
       the label. We force `none` + `transparent` at every level of
       the tab subtree to catch both shorthand and per-line resets. */

/* (1) Outer tab container — transparent, no card chrome. */
.gradio-container .tabs,
.gradio-container .tab-container{
  background: transparent !important;
  border: 0 !important;
  box-shadow: none !important;
  padding: 0 !important;
}

/* (2) Tablist — flex row + wrap, baseline via ::after so nothing
       crosses the buttons visually. */
.gradio-container .tab-nav,
.gradio-container [role="tablist"]{
  position: relative !important;
  display: flex !important;
  flex-wrap: wrap !important;
  gap: 0 !important;
  align-items: flex-end !important;
  background: transparent !important;
  border: 0 !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  padding: 0 !important;
  margin: 0 0 16px 0 !important;
  overflow: visible !important;
}
.gradio-container .tab-nav::after,
.gradio-container [role="tablist"]::after{
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 1px;
  background: rgba(15, 23, 42, 0.10);
  pointer-events: none;
  z-index: 0;
}

/* (3) Tab buttons — flat, text-only, underline on active.

   Sizing: `flex: 1 1 auto` + `min-width: 0` lets all six tabs share
   the row and shrink gracefully on narrow viewports instead of
   wrapping tab 6 off-screen. `justify-content: center` per tab keeps
   the label readable at any width.

   Borders: explicit `border: 0` plus each side individually, because
   Gradio's Svelte theme applies `border-right: 1px solid` per tab to
   visually separate them, which the shorthand `border: 0` alone was
   not beating with the same specificity as the theme's per-side
   rules. */
.gradio-container .tab-nav button,
.gradio-container [role="tablist"] button,
.gradio-container button[role="tab"]{
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  gap: 6px !important;
  padding: 10px 14px !important;
  margin: 0 !important;
  font-family: inherit !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  line-height: 1.3 !important;
  color: #475569 !important;
  background: transparent !important;
  background-color: transparent !important;
  background-image: none !important;
  border: 0 !important;
  border-top: 0 !important;
  border-right: 0 !important;
  border-bottom: 0 !important;
  border-left: 0 !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  cursor: pointer !important;
  position: relative !important;
  white-space: nowrap !important;
  text-decoration: none !important;
  text-decoration-line: none !important;
  text-decoration-color: transparent !important;
  text-decoration-thickness: 0 !important;
  -webkit-text-decoration: none !important;
  -webkit-text-decoration-line: none !important;
  transition: color 0.2s ease !important;
  flex: 1 1 auto !important;
  min-width: 0 !important;
  outline: 0 !important;
  z-index: 1;
}

/* (3b) Every descendant (Gradio injects `<span>` label wrappers). */
.gradio-container .tab-nav button *,
.gradio-container [role="tablist"] button *,
.gradio-container button[role="tab"] *{
  background: transparent !important;
  background-color: transparent !important;
  background-image: none !important;
  border: 0 !important;
  color: inherit !important;
  text-decoration: none !important;
  text-decoration-line: none !important;
  text-decoration-color: transparent !important;
  text-decoration-thickness: 0 !important;
  -webkit-text-decoration: none !important;
  -webkit-text-decoration-line: none !important;
  box-shadow: none !important;
}
.gradio-container button[role="tab"]:hover,
.gradio-container [role="tablist"] > button:hover{
  color: var(--tl-primary) !important;
  background: transparent !important;
}
.gradio-container button[role="tab"][aria-selected="true"],
.gradio-container [role="tablist"] > button.selected,
.gradio-container [role="tablist"] > button[aria-selected="true"]{
  color: var(--tl-primary) !important;
  font-weight: 700 !important;
  background: transparent !important;
}
.gradio-container button[role="tab"][aria-selected="true"]::after,
.gradio-container [role="tablist"] > button.selected::after,
.gradio-container [role="tablist"] > button[aria-selected="true"]::after{
  content: "";
  position: absolute;
  left: 10px;
  right: 10px;
  bottom: 0;
  height: 2px;
  background: linear-gradient(90deg, var(--tl-primary), var(--tl-cyan));
  border-radius: 2px 2px 0 0;
  pointer-events: none;
}

/* ---- Primary buttons: pill + blue gradient ---------------------- */
.gradio-container button.primary,
.gradio-container button.lg.primary,
.gradio-container .primary > button,
.gradio-container [variant="primary"] button{
  background: linear-gradient(135deg,
                var(--tl-primary) 0%,
                var(--tl-primary-deep) 100%) !important;
  color: #ffffff !important;
  border: 0 !important;
  border-radius: 999px !important;
  font-weight: 700 !important;
  letter-spacing: 0.3px !important;
  padding: 10px 24px !important;
  box-shadow:
    0 4px 14px rgba(37, 99, 235, 0.28),
    0 0 0 1px rgba(255, 255, 255, 0.08) inset !important;
  transition: transform 0.2s ease, box-shadow 0.2s ease, filter 0.2s ease !important;
}
.gradio-container button.primary:hover,
.gradio-container button.lg.primary:hover,
.gradio-container .primary > button:hover,
.gradio-container [variant="primary"] button:hover{
  transform: translateY(-1px);
  box-shadow:
    0 8px 22px rgba(37, 99, 235, 0.38),
    0 0 0 1px rgba(255, 255, 255, 0.12) inset !important;
  filter: brightness(1.05);
}
@media (prefers-reduced-motion: reduce){
  .gradio-container button.primary,
  .gradio-container button.lg.primary,
  .gradio-container .primary > button,
  .gradio-container [variant="primary"] button{
    transition: none !important;
    transform: none !important;
  }
}

/* ---- Secondary buttons: outline pill with blue hover -----------  */
.gradio-container button.secondary,
.gradio-container .secondary > button,
.gradio-container [variant="secondary"] button{
  border-radius: 999px !important;
  border: 1px solid rgba(37, 99, 235, 0.28) !important;
  background: rgba(255, 255, 255, 0.85) !important;
  color: var(--tl-primary-deep) !important;
  font-weight: 600 !important;
  padding: 8px 18px !important;
  transition: all 0.2s ease !important;
}
.gradio-container button.secondary:hover,
.gradio-container .secondary > button:hover,
.gradio-container [variant="secondary"] button:hover{
  background: linear-gradient(135deg,
                rgba(37, 99, 235, 0.06),
                rgba(6, 182, 212, 0.05)) !important;
  border-color: rgba(37, 99, 235, 0.55) !important;
  transform: translateY(-1px);
}

/* ---- Animated gradient accent strip on .rhk-card--accent --------
   Upgrades the Phase-1 static strip to the Tello-Lab animated
   three-color border-scroll. 4s is slow enough that it reads as
   "living accent" not "attention-grabbing". */
.rhk-card.rhk-card--accent::before{
  background: linear-gradient(90deg,
                var(--tl-primary),
                var(--tl-cyan),
                var(--tl-violet),
                var(--tl-primary)) !important;
  background-size: 200% 100% !important;
  animation: rhk-gradient-border 4s linear infinite;
}
@keyframes rhk-gradient-border{
  0%   { background-position: 0% 50%; }
  100% { background-position: 200% 50%; }
}
@media (prefers-reduced-motion: reduce){
  .rhk-card.rhk-card--accent::before{ animation: none; }
}

/* ---- Glass card variant (frosted blue-tinted surface) ----------- */
.rhk-card--glass{
  background: rgba(255, 255, 255, 0.62) !important;
  backdrop-filter: blur(14px) saturate(140%);
  -webkit-backdrop-filter: blur(14px) saturate(140%);
  border: 1px solid rgba(37, 99, 235, 0.14) !important;
  box-shadow:
    0 8px 32px rgba(37, 99, 235, 0.08),
    0 0 0 1px rgba(255, 255, 255, 0.6) inset !important;
}

/* ---- Dark card variant (navy with radial glow, for callouts) ---- */
.rhk-card--dark{
  position: relative;
  overflow: hidden;
  background: linear-gradient(135deg,
                var(--tl-deep) 0%,
                var(--tl-navy) 100%) !important;
  color: #ffffff !important;
  border: 1px solid rgba(96, 165, 250, 0.22) !important;
  box-shadow:
    0 16px 48px rgba(19, 36, 63, 0.3),
    0 0 0 1px rgba(255, 255, 255, 0.03) inset !important;
}
.rhk-card--dark::before{
  content: "";
  position: absolute;
  top: 10%;
  right: -15%;
  width: 320px;
  height: 320px;
  border-radius: 50%;
  background: radial-gradient(circle,
                rgba(96, 165, 250, 0.14),
                transparent 70%);
  pointer-events: none;
}
.rhk-card--dark h1,
.rhk-card--dark h2,
.rhk-card--dark h3,
.rhk-card--dark h4,
.rhk-card--dark p,
.rhk-card--dark span{ color: #ffffff !important; }
.rhk-card--dark .rhk-section-kicker{ color: var(--tl-primary-light); }

/* ---- Metric numerals: big mono digits with gradient fill --------
   For hemodynamic values (mPAP, PAWP, PVR, CI, etc.) in dashboard
   or summary displays. Mirror of Tello-Lab's `.hpv-m-num` pattern. */
.rhk-metric-num{
  font-family: "SF Mono", "Monaco", "Cascadia Code", "Roboto Mono",
               ui-monospace, monospace;
  font-size: 28px;
  font-weight: 800;
  line-height: 1.1;
  background: linear-gradient(90deg, var(--tl-primary), var(--tl-cyan));
  -webkit-background-clip: text;
          background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
  letter-spacing: -0.3px;
  font-variant-numeric: tabular-nums;
}
.rhk-metric-num--ok{
  background: linear-gradient(90deg, #34d399, #10b981);
  -webkit-background-clip: text;
          background-clip: text;
  -webkit-text-fill-color: transparent;
}
.rhk-metric-num--warn{
  background: linear-gradient(90deg, #fbbf24, var(--tl-gold));
  -webkit-background-clip: text;
          background-clip: text;
  -webkit-text-fill-color: transparent;
}
.rhk-metric-num--danger{
  background: linear-gradient(90deg, #fb7185, var(--tl-rose));
  -webkit-background-clip: text;
          background-clip: text;
  -webkit-text-fill-color: transparent;
}
.rhk-metric-label{
  font-size: 10px;
  color: var(--tl-muted);
  margin-top: 2px;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  font-weight: 700;
}

/* ---- Sliders: Tello-Lab range-track gradient -------------------- */
.gradio-container input[type="range"]{
  -webkit-appearance: none;
  appearance: none;
  height: 6px !important;
  background: rgba(37, 99, 235, 0.12) !important;
  border-radius: 3px;
  outline: none;
  transition: background 0.2s;
}
.gradio-container input[type="range"]:hover{
  background: rgba(37, 99, 235, 0.2) !important;
}
.gradio-container input[type="range"]::-webkit-slider-thumb{
  -webkit-appearance: none;
  appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--tl-primary), var(--tl-cyan));
  cursor: pointer;
  box-shadow: 0 2px 6px rgba(37, 99, 235, 0.35),
              0 0 0 3px rgba(255, 255, 255, 0.9);
  border: 0;
  transition: transform 0.15s ease;
}
.gradio-container input[type="range"]::-webkit-slider-thumb:hover{
  transform: scale(1.15);
}
.gradio-container input[type="range"]::-moz-range-thumb{
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--tl-primary), var(--tl-cyan));
  cursor: pointer;
  border: 0;
  box-shadow: 0 2px 6px rgba(37, 99, 235, 0.35);
}

/* ---- Scroll progress bar (optional) ----------------------------- */
.rhk-scroll-bar{
  position: fixed;
  top: 0; left: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--tl-primary), var(--tl-cyan));
  z-index: 9999;
  width: var(--rhk-scroll-progress, 0%);
  transition: width 0.1s linear;
  pointer-events: none;
}

/* ---- Glass header island: Inter + refined typography ------------
   The existing `rhk-glass-island` header in rhk_base.py already uses
   the Tello-Lab blue accent and aurora effect. We refine it here to
   inherit Inter, swap the Avenir-first font stack, and ensure the
   main title picks up the gradient-text treatment above. */
#rhk_topbar_wrapper,
#rhk_topbar_wrapper *{
  font-family: var(--ds-font-sans) !important;
}
.rhk-main-title{
  letter-spacing: -0.025em !important;
  font-weight: 900 !important;
}

/* ---- Section-card border refinement ----------------------------- */
.rhk-section-card{
  border: 1px solid rgba(37, 99, 235, 0.08) !important;
  box-shadow: var(--tl-shadow-soft);
  border-radius: 18px !important;
}

/* ---- Accordion headers: muted blue when open -------------------- */
.gradio-container details summary,
.gradio-container .accordion > .label-wrap{
  font-weight: 600;
  color: var(--tl-text);
  transition: color 0.2s ease;
}
.gradio-container details[open] summary,
.gradio-container .accordion[open] > .label-wrap{
  color: var(--tl-primary);
}

/* ---- Section-kicker refinement: adds a subtle dot before the text
   to match the Tello-Lab section-sub pattern (tiny animated dot +
   uppercase letter-spaced label). */
.rhk-section-kicker::before{
  content: "";
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--tl-primary-light), var(--tl-cyan));
  margin-right: 8px;
  vertical-align: middle;
  box-shadow: 0 0 6px rgba(96, 165, 250, 0.5);
}

""".strip())

# Avoid %-formatting pitfalls (Gradio/CSS contains many % characters).
CSS = CSS.replace("__DESKTOP_VIEWPORT_WIDTH_PX__", str(DESKTOP_VIEWPORT_WIDTH_PX)).replace("%%", "%")

JS_ON_LOAD = r"""
(function(){
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
      // Tabs: wrap instead of overflow (restricted scope for performance)
      const tablists = document.querySelectorAll('#rhk_input_tabs [role="tablist"], #rhk_output_tabs [role="tablist"]');
      tablists.forEach((tl) => {
        try {
          tl.style.flexWrap = 'wrap';
          tl.style.overflow = 'visible';
          tl.style.whiteSpace = 'normal';
        } catch (e) {}
      });
      // Tab buttons: never truncate into ellipsis
      document.querySelectorAll('#rhk_input_tabs [role="tab"], #rhk_output_tabs [role="tab"]').forEach((b) => {
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

  const I18N = (() => {
    try {
      if (window.RHK_I18N && typeof window.RHK_I18N === 'object') return window.RHK_I18N;
    } catch (e) {}
    try {
      const fallback = __RHK_I18N_FALLBACK__;
      if (fallback && typeof fallback === 'object') {
        window.RHK_I18N = fallback;
        return fallback;
      }
    } catch (e) {}
    return {
      defaultLanguage: 'de',
      languages: { de: { label: 'Deutsch' }, en: { label: 'English' }, zh: { label: '中文' } },
      messages: {},
      exact: {},
      replacements: {}
    };
  })();
  const I18N_STORAGE_KEY = 'rhk.ui.language';
  const I18N_DEFAULT = String(I18N.defaultLanguage || 'de');
  const I18N_ROOT_SELECTORS = [
    '.rhk-skip-link',
    '#rhk_topbar_wrapper',
    '#rhk_whatsnew_wrapper',
    '#rhk_workflow_overview_wrapper',
    '#rhk_ui_mode',
    '#rhk_ui_mode_help',
    '#rhk_import_hint_top',
    '#rhk_import_hint_bottom',
    '#rhk_actions_top_primary',
    '#rhk_actions_top_expert',
    '#rhk_tab_subtitle',
    '#rhk_input_column',
    '#rhk_output_column',
    '#rhk_output_tabs',
    '#rhk_patient_mode_row',
    '#rhk_copy_row',
    '#rhk_copy_feedback',
    '#rhk_download_files_row',
    '#docx_save_acc',
    '#docx_cloud_hint',
    '#download_diag_acc',
    '#download_diag',
    '#rhk_actions_bottom_primary',
    '#rhk_actions_bottom_expert',
    '#rhk_dashboard_wrapper',
    '#rhk_tool_disclaimer_wrapper',
    '#rhk_pre_cath_home_wrapper',
    '#rhk_summarybar_wrapper',
    '#rhk_desktop_only_overlay',
    'footer'
  ];

  const normalizeI18nText = (value) => {
    try {
      return String(value == null ? '' : value).replace(/\s+/g, ' ').trim();
    } catch (e) {
      return '';
    }
  };

  const preserveEdgeWhitespace = (source, translated) => {
    try {
      const s = String(source == null ? '' : source);
      const m = s.match(/^(\s*)([\s\S]*?)(\s*)$/);
      if (!m) return String(translated == null ? '' : translated);
      return (m[1] || '') + String(translated == null ? '' : translated) + (m[3] || '');
    } catch (e) {
      return String(translated == null ? '' : translated);
    }
  };

  const collectI18nDomRoots = () => {
    try {
      const roots = [];
      const seen = [];
      const queue = [];
      const pushRoot = (root) => {
        if (!root || seen.indexOf(root) >= 0) return;
        seen.push(root);
        roots.push(root);
        queue.push(root);
      };

      pushRoot(document);
      while (queue.length) {
        const root = queue.shift();
        let hosts = [];
        try {
          hosts = root && root.querySelectorAll ? root.querySelectorAll('*') : [];
        } catch (e) {
          hosts = [];
        }
        try {
          hosts.forEach((host) => {
            try {
              if (host && host.shadowRoot) pushRoot(host.shadowRoot);
            } catch (e) {}
          });
        } catch (e) {}
      }
      return roots;
    } catch (e) {
      return [document];
    }
  };

  const deepQuerySelectorAll = (selector) => {
    const out = [];
    if (!selector) return out;
    const roots = collectI18nDomRoots();
    roots.forEach((root) => {
      try {
        const list = root && root.querySelectorAll ? root.querySelectorAll(selector) : [];
        list.forEach((el) => {
          if (el && out.indexOf(el) < 0) out.push(el);
        });
      } catch (e) {}
    });
    return out;
  };

  const findInEventPath = (ev, selector) => {
    try {
      if (ev && typeof ev.composedPath === 'function') {
        const path = ev.composedPath() || [];
        for (let i = 0; i < path.length; i += 1) {
          const n = path[i];
          if (!n || n === window || n === document) continue;
          try {
            if (n.matches && n.matches(selector)) return n;
          } catch (e) {}
          try {
            if (n.closest) {
              const c = n.closest(selector);
              if (c) return c;
            }
          } catch (e) {}
        }
      }
    } catch (e) {}
    try {
      const t = ev && ev.target;
      if (t && t.closest) return t.closest(selector);
    } catch (e) {}
    return null;
  };

  const getCurrentLanguage = () => {
    try {
      const raw = window.localStorage && window.localStorage.getItem(I18N_STORAGE_KEY);
      if (raw && ((I18N.languages || {})[raw])) return raw;
    } catch (e) {}
    return I18N_DEFAULT;
  };

  const setCurrentLanguage = (lang) => {
    const next = ((I18N.languages || {})[lang]) ? lang : I18N_DEFAULT;
    try {
      if (window.localStorage) window.localStorage.setItem(I18N_STORAGE_KEY, next);
    } catch (e) {}
    window.__rhkUiLanguage = next;
    try {
      document.documentElement.setAttribute('data-rhk-language', next);
      document.documentElement.setAttribute('lang', next === 'zh' ? 'zh-CN' : next);
    } catch (e) {}
    return next;
  };

  const translateText = (source, lang) => {
    const text = String(source == null ? '' : source);
    if (!text || lang === 'de') return text;

    const normalized = normalizeI18nText(text);
    if (!normalized) return text;

    const exact = ((I18N.exact || {})[lang]) || {};
    if (Object.prototype.hasOwnProperty.call(exact, normalized)) {
      return preserveEdgeWhitespace(text, exact[normalized]);
    }

    let out = normalized;
    const replacements = ((I18N.replacements || {})[lang]) || [];
    replacements.forEach((pair) => {
      try {
        if (!Array.isArray(pair) || pair.length < 2) return;
        const from = String(pair[0] || '');
        const to = String(pair[1] || '');
        if (!from) return;
        out = out.split(from).join(to);
      } catch (e) {}
    });
    return preserveEdgeWhitespace(text, out);
  };

  const translateNodeText = (node, lang) => {
    try {
      if (!node) return;
      if (node.__rhkI18nSourceText == null) node.__rhkI18nSourceText = node.textContent;
      const next = translateText(node.__rhkI18nSourceText, lang);
      if (typeof next === 'string' && node.textContent !== next) node.textContent = next;
    } catch (e) {}
  };

  const translateAttribute = (el, attr, lang) => {
    try {
      if (!el || !el.getAttribute || !el.hasAttribute(attr)) return;
      if (!el.__rhkI18nAttrSource) el.__rhkI18nAttrSource = {};
      if (!(attr in el.__rhkI18nAttrSource)) el.__rhkI18nAttrSource[attr] = el.getAttribute(attr);
      const src = el.__rhkI18nAttrSource[attr];
      const next = translateText(src, lang);
      if (typeof next === 'string' && el.getAttribute(attr) !== next) el.setAttribute(attr, next);
    } catch (e) {}
  };

  const collectI18nRoots = () => {
    const out = [];
    const pushRoot = (el) => {
      if (el && out.indexOf(el) < 0) out.push(el);
    };

    collectI18nDomRoots().forEach((scope) => {
      I18N_ROOT_SELECTORS.forEach((sel) => {
        try {
          const list = scope && scope.querySelectorAll ? scope.querySelectorAll(sel) : [];
          list.forEach((el) => pushRoot(el));
        } catch (e) {}
      });
    });
    if (!out.length) {
      collectI18nDomRoots().forEach((scope) => {
        if (!scope) return;
        if (scope === document) {
          pushRoot(document.body || document.documentElement);
          return;
        }
        pushRoot(scope);
      });
    }
    return out;
  };

  const shouldSkipI18nNode = (node) => {
    try {
      const el = node && node.parentElement;
      if (!el) return true;
      if (el.closest('script, style, textarea, pre, code, .rhk-hidden-payload')) return true;
      if (el.closest('.rhk-scrollbox')) return true;
      if (el.closest('#rhk_output_tabs') && !el.closest('[role="tablist"]')) return true;
      const tag = String(el.tagName || '').toLowerCase();
      if (tag === 'textarea' || tag === 'input') return true;
      return false;
    } catch (e) {
      return true;
    }
  };

  const translateOptions = (root, lang) => {
    try {
      if (!root || lang === 'de') return;
      const exact = ((I18N.exact || {})[lang]) || {};
      root.querySelectorAll('option, [role="option"], .wrap-inner, input[type="radio"] + label, input[type="checkbox"] + label, .gradio-radio label span, .gradio-checkbox label span').forEach((el) => {
        try {
          if (!el.__rhkI18nOptSource) el.__rhkI18nOptSource = el.textContent;
          const txt = normalizeI18nText(el.__rhkI18nOptSource || '');
          if (txt && Object.prototype.hasOwnProperty.call(exact, txt)) {
            const next = exact[txt];
            if (el.textContent !== next) el.textContent = next;
          }
        } catch (e) {}
      });
    } catch (e) {}
  };

  const applyI18nToRoot = (root, lang) => {
    try {
      if (!root) return;

      root.querySelectorAll('[role="tab"], .rhk-qnav-btn').forEach((el) => {
        try {
          if (!el.getAttribute('data-rhk-i18n-source-label')) {
            el.setAttribute('data-rhk-i18n-source-label', normalizeI18nText(el.textContent || ''));
          }
        } catch (e) {}
      });

      const walker = document.createTreeWalker(
        root,
        NodeFilter.SHOW_TEXT,
        {
          acceptNode: (node) => {
            if (!node || !normalizeI18nText(node.textContent || '')) return NodeFilter.FILTER_REJECT;
            return shouldSkipI18nNode(node) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
          }
        }
      );
      let current = walker.nextNode();
      while (current) {
        translateNodeText(current, lang);
        current = walker.nextNode();
      }

      root.querySelectorAll('[placeholder], [title], [aria-label]').forEach((el) => {
        translateAttribute(el, 'placeholder', lang);
        translateAttribute(el, 'title', lang);
        translateAttribute(el, 'aria-label', lang);
      });

      translateOptions(root, lang);
    } catch (e) {}
  };

  const syncLanguageButtons = (lang) => {
    try {
      deepQuerySelectorAll('.rhk-lang-btn[data-rhk-lang]').forEach((btn) => {
        const active = String(btn.getAttribute('data-rhk-lang') || '') === String(lang || '');
        btn.classList.toggle('is-active', !!active);
        btn.setAttribute('aria-pressed', active ? 'true' : 'false');
      });
      const groups = deepQuerySelectorAll('.rhk-lang-switch');
      const group = groups && groups.length ? groups[0] : null;
      const label = ((I18N.messages || {})[lang] || {}).language_switch_label || 'Sprache wechseln';
      if (group) {
        group.setAttribute('aria-label', label);
        group.setAttribute('title', label);
      }
    } catch (e) {}
  };

  let __rhk_i18n_timer = 0;
  const applyI18n = () => {
    const lang = setCurrentLanguage(window.__rhkUiLanguage || getCurrentLanguage());
    collectI18nRoots().forEach((root) => applyI18nToRoot(root, lang));
    syncLanguageButtons(lang);
    try {
      if (document.title && !window.__rhkI18nTitleSource) window.__rhkI18nTitleSource = document.title;
      if (window.__rhkI18nTitleSource) document.title = translateText(window.__rhkI18nTitleSource, lang);
    } catch (e) {}
    // Re-localize dynamic labels that live outside normal text nodes
    // (workflow toggle text is set via textContent, so MutationObserver alone misses it).
    try { if (typeof window.__rhkApplyWorkflowOverviewState === 'function') window.__rhkApplyWorkflowOverviewState(); } catch (e) {}
  };

  const scheduleI18nApply = () => {
    try {
      if (__rhk_i18n_timer) return;
      __rhk_i18n_timer = window.setTimeout(() => {
        __rhk_i18n_timer = 0;
        applyI18n();
      }, 80);
    } catch (e) {
      applyI18n();
    }
  };

  const setupLanguageSwitcher = () => {
    try {
      if (window.__rhkLangSwitchInstalled) return;
      window.__rhkLangSwitchInstalled = true;
      document.addEventListener('click', (ev) => {
        try {
          const btn = findInEventPath(ev, '.rhk-lang-btn[data-rhk-lang]');
          if (!btn) return;
          const lang = String(btn.getAttribute('data-rhk-lang') || I18N_DEFAULT);
          window.__rhkUiLanguage = setCurrentLanguage(lang);
          scheduleI18nApply();
          try {
            const langEl = document.querySelector('#rhk_ui_lang textarea, #rhk_ui_lang input');
            if (langEl) {
              langEl.value = lang;
              langEl.dispatchEvent(new Event('input', {bubbles: true}));
            }
          } catch (_) {}
        } catch (e) {}
      }, true);
    } catch (e) {}
  };

  const setupI18nObserver = () => {
    try {
      if (window.__rhkI18nObserverInstalled) return;
      window.__rhkI18nObserverInstalled = true;
      const obs = new MutationObserver(() => { scheduleI18nApply(); });
      obs.observe(document.documentElement || document.body, {
        childList: true,
        subtree: true,
        characterData: true,
        attributes: true,
        attributeFilter: ['aria-label', 'title', 'placeholder']
      });
    } catch (e) {}
  };

  const FIELD_MARKER_ROOT = '#rhk_summarybar_wrapper .rhk-field-marker-payload';
  const FIELD_MARKER_CLASSES = ['rhk-field-marker-critical', 'rhk-field-marker-important', 'rhk-field-marker-hint'];

  const clearFieldMarkers = () => {
    try {
      document.querySelectorAll('.rhk-field').forEach((root) => {
        try {
          FIELD_MARKER_CLASSES.forEach((cls) => { root.classList.remove(cls); });
        } catch (e) {}
      });
      document.querySelectorAll('.rhk-field-alert-dot').forEach((dot) => {
        try { dot.remove(); } catch (e) {}
      });
    } catch (e) {}
  };

  const parseFieldMarkerPayload = () => {
    try {
      const node = document.querySelector(FIELD_MARKER_ROOT);
      if (!node) return {};
      const raw = node.getAttribute('data-markers') || '{}';
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== 'object') return {};
      return parsed;
    } catch (e) {
      return {};
    }
  };

  const cssEscape = (s) => {
    try {
      if (window.CSS && typeof window.CSS.escape === 'function') return window.CSS.escape(String(s || ''));
    } catch (e) {}
    return String(s || '').replace(/[^a-zA-Z0-9_-]/g, '_');
  };

  const applyFieldMarkers = () => {
    try {
      clearFieldMarkers();
      const payload = parseFieldMarkerPayload();
      const entries = Object.entries(payload || {});
      if (!entries.length) return;

      entries.forEach(([field, meta]) => {
        try {
          const key = String(field || '').trim();
          if (!key) return;
          const level = String((meta && meta.level) || 'hint').toLowerCase();
          const title = String((meta && meta.title) || '').trim();
          const markerClass = (
            level === 'critical' ? 'rhk-field-marker-critical' :
            (level === 'important' ? 'rhk-field-marker-important' : 'rhk-field-marker-hint')
          );
          const dotClass = (
            level === 'critical' ? 'rhk-field-alert-dot--critical' :
            (level === 'important' ? 'rhk-field-alert-dot--important' : 'rhk-field-alert-dot--hint')
          );

          document.querySelectorAll('.rhk-field-' + cssEscape(key)).forEach((root) => {
            try { root.classList.add(markerClass); } catch (e) {}
            let label = null;
            try {
              label = root.querySelector('label, .label-wrap, .gr-block-title, .wrap > label');
            } catch (e) { label = null; }
            if (!label) return;

            const dot = document.createElement('span');
            dot.className = 'rhk-field-alert-dot ' + dotClass;
            if (title) {
              dot.setAttribute('title', title);
              dot.setAttribute('aria-label', title);
            }
            label.appendChild(dot);
          });
        } catch (e) {}
      });
    } catch (e) {}
  };

  let __rhk_marker_timer = 0;
  const scheduleFieldMarkers = () => {
    try {
      if (__rhk_marker_timer) return;
      __rhk_marker_timer = window.setTimeout(() => {
        __rhk_marker_timer = 0;
        applyFieldMarkers();
      }, 80);
    } catch (e) {
      applyFieldMarkers();
    }
  };

  const setupFieldMarkers = () => {
    try {
      if (window.__rhk_field_markers_setup) return;
      window.__rhk_field_markers_setup = true;
      const host = document.getElementById('rhk_summarybar_wrapper');
      if (!host) {
        window.setTimeout(setupFieldMarkers, 350);
        return;
      }
      const obs = new MutationObserver(() => { scheduleFieldMarkers(); });
      obs.observe(host, { childList: true, subtree: true, attributes: true, attributeFilter: ['data-markers'] });
      scheduleFieldMarkers();
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
    scheduleFieldMarkers();
    scheduleI18nApply();
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

      window.__rhk_dirty_already = false;

      const bumpPing = debounce(() => {
        try {
          if (window.__rhk_dirty_already) return;
          const el = getPingEl();
          if (!el) return;
          el.value = String(Date.now());
          // Only dispatch 'change' to trigger the server-side .change handler.
          el.dispatchEvent(new Event('change', { bubbles: true }));
          window.__rhk_dirty_already = true;
        } catch (e) {}
      }, 900);

      const resetDirtyLocal = () => { try { window.__rhk_dirty_already = false; } catch (e) {} };

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

      const onInputMaybe = (ev) => {
        try {
          const t = ev ? ev.target : null;
          if (!t) return;
          const tag = (t.tagName || '').toLowerCase();
          const type = (t.getAttribute && t.getAttribute('type')) ? String(t.getAttribute('type')).toLowerCase() : '';
          // Avoid a roundtrip on every keystroke in textboxes/textarea.
          if (tag === 'textarea') return;
          if (tag === 'input' && (type === 'text' || type === 'search' || type === 'email' || type === 'url' || type === 'tel' || type === 'password')) return;
          onAnyEdit(ev);
        } catch (e) {}
      };

      document.addEventListener('input', onInputMaybe, true);
      document.addEventListener('change', onAnyEdit, true);

      const armBulk = () => { resetDirtyLocal(); window.__rhk_bulk_until = Date.now() + 1400; };
      [
        'btn_example_top','btn_example_bottom','btn_clear_top','btn_clear_bottom',
        'btn_generate_top','btn_generate_bottom','btn_save_top','btn_save_bottom',
        'btn_load_top','btn_load_bottom','btn_load_followup_top','btn_load_followup_bottom'
      ].forEach((id) => {
        const node = document.getElementById(id);
        if (!node) return;
        try { node.addEventListener('click', armBulk, true); } catch (e) {}
      });
    } catch (e) {}
  };

  update();
  setupDirtyPing();
  setupFieldMarkers();
  setupLanguageSwitcher();
  setupI18nObserver();
  scheduleI18nApply();
  setTimeout(update, 50);
  setTimeout(update, 250);
  setTimeout(scheduleI18nApply, 150);
  setTimeout(scheduleI18nApply, 500);
  window.addEventListener("resize", () => setTimeout(update, 50));

  // Pre-RHK PDF export (sticky header button)
  window.rhkTriggerPreRhkPdf = () => {
    try {
      // Gradio versions differ: elem_id may be attached to the <button> itself
      // or to a wrapper that contains the <button>. Be robust.
      const root = document.getElementById('btn_prerhk_pdf');
      if (!root) return;
      if ((root.tagName || '').toLowerCase() === 'button') {
        root.click();
        return;
      }
      const btn = root.querySelector('button') || document.querySelector('#btn_prerhk_pdf button');
      if (btn) btn.click();
    } catch (e) {}
  };



})();
"""
JS_ON_LOAD = (
    JS_ON_LOAD
    .replace("__DESKTOP_ONLY__", "true" if DESKTOP_ONLY else "false")
    .replace("__MIN_WIDTH__", str(DESKTOP_MIN_WIDTH_PX))
    .replace("__RHK_I18N_FALLBACK__", _I18N_PAYLOAD_JSON)
    .strip()
)


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

  function findInEventPath(ev, sel){
    try {
      if(ev && typeof ev.composedPath === 'function'){
        var path = ev.composedPath() || [];
        for(var i=0;i<path.length;i++){
          var n = path[i];
          if(!n || n === window || n === document) continue;
          if(n.matches && n.matches(sel)) return n;
          if(n.closest){
            var c = n.closest(sel);
            if(c) return c;
          }
        }
      }
    } catch(e) {}
    try {
      var t = ev && ev.target;
      if(t && t.closest) return t.closest(sel);
    } catch(e) {}
    return null;
  }

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
    // Primary HEAD_HTML path already installed a robust delegated handler.
    // In that case, skip fallback binding to avoid double copy events.
    if(window.__rhkCopyClickHandler){
      window.__rhkCopyDelegationInstalled = true;
      return;
    }
    window.__rhkCopyDelegationInstalled = true;
    document.addEventListener('click', function(ev){
      try {
        var host = findInEventPath(ev, '#btn_copy_doc, #btn_copy_pat, #btn_copy_rhk');
        if(!host) return;
        var isDoc = host.id === 'btn_copy_doc';
        var isPat = host.id === 'btn_copy_pat';
        var isRhk = host.id === 'btn_copy_rhk';
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
    installCopyObserver();
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
