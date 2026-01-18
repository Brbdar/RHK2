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
        # Client-side PDF text extraction (Echo PDFs) – keeps PHI on the client.
        # Offline-first strategy: try local vendor files via Gradio /file= route, then CDN fallback.
        r"""
<script>
(function(){
  const PDFJS_URLS = [
    '/file=assets/vendor/pdf/pdf.min.js',
    'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.10.38/pdf.min.js',
    'https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.min.js',
    'https://unpkg.com/pdfjs-dist@4.10.38/build/pdf.min.js'
  ];
  const WORKER_URLS = [
    '/file=assets/vendor/pdf/pdf.worker.min.js',
    'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.10.38/pdf.worker.min.js',
    'https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.worker.min.js',
    'https://unpkg.com/pdfjs-dist@4.10.38/build/pdf.worker.min.js'
  ];

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
        # Client-side OCR for screenshot imports (keeps PHI on the client)
        # Uses tesseract.js (WebAssembly) loaded from CDN.
        '<script src="https://unpkg.com/tesseract.js@5.0.5/dist/tesseract.min.js"></script>',
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
    // Gradio can hot-replace DOM nodes; keep the handler robust across rerenders.
    try{
      if(window.__rhkCopyClickHandler){
        document.removeEventListener('click', window.__rhkCopyClickHandler, true);
      }
    }catch(e){}
    window.__rhkCopyClickHandler = function(ev){
      try {
        var t0 = ev && ev.target;
        if(!t0 || !t0.closest) return;
        var host = t0.closest('#btn_copy_doc, #btn_copy_pat, #btn_copy_rhk');
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
    'Klinik & Labor': 'Anamnese, Vorerkrankungen, Labor und Basisdaten',
    'Bildgebung & Echo/CMR': 'CT, V/Q, Echo und CMR Befunde strukturiert erfassen',
    'Lungenfunktion': 'Spirometrie, Bodyplethysmographie, Diffusion',
    'RHK': 'Invasive Hämodynamik in Ruhe und unter Belastung',
    'Weitere Befunde': '6MWD, NYHA, Scores und ergänzende klinische Parameter',
    'Procedere & Module': 'Empfehlungen, Module, Follow up und Dokumentation'
  };

  function _tabLabel(btn){
    try {
      var t = (btn.textContent || '').trim();
      return t;
    } catch(e) { return ''; }
  }

  function _panelHasAnyValue(panel){
    try {
      if(!panel) return false;
      var els = panel.querySelectorAll('input, textarea, select');
      for(var i=0;i<els.length;i++){
        var el = els[i];
        if(!el) continue;
        // Ignore file pickers and hidden payloads
        if(el.type === 'file') continue;
        if(el.closest && el.closest('.rhk-hidden-payload')) continue;
        var v = (typeof el.value === 'string') ? el.value.trim() : '';
        if(v && v !== '0' && v !== '0.0') return true;
      }
    } catch(e) {}
    return false;
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

  function updateTabUx(){
    try {
      var nav = document.querySelector('.gradio-container .tab-nav, .gradio-container .tabs > .tab-nav');
      if(!nav) return;
      // Keep a stable spacer for tab content below sticky tab-nav (prevents overlap)
      try {
        var h = nav.offsetHeight || 60;
        document.documentElement.style.setProperty('--rhk-tabnav-h', h + 'px');
      } catch(e) {}
      var buttons = nav.querySelectorAll('button');
      if(!buttons || !buttons.length) return;

      // Subtitle
      var sub = byId('rhk_tab_subtitle');
      var activeLabel = '';
      for(var i=0;i<buttons.length;i++){
        if(buttons[i].getAttribute('aria-selected') === 'true'){
          activeLabel = _tabLabel(buttons[i]);
          break;
        }
      }
      if(sub){
        var txt = __rhkTabSubtitleMap[activeLabel] || __rhkTabSubtitleMap[_tabLabel(buttons[0])] || '';
        sub.textContent = txt;
      }

      // Dots
      for(var j=0;j<buttons.length;j++){
        var btn = buttons[j];
        var dot = _ensureDot(btn);
        if(!dot) continue;
        var panelId = btn.getAttribute('aria-controls');
        var panel = panelId ? document.getElementById(panelId) : null;
        var filled = _panelHasAnyValue(panel);
        dot.classList.toggle('is-filled', !!filled);
        dot.classList.toggle('is-active', btn.getAttribute('aria-selected') === 'true');
      }
    } catch(e) {}
  }

  function installTabUxObserver(){
    if(window.__rhkTabUxObserverInstalled) return;
    window.__rhkTabUxObserverInstalled = true;
    try {
      var obs = new MutationObserver(function(){
        // debounce
        if(window.__rhkTabUxT) clearTimeout(window.__rhkTabUxT);
        window.__rhkTabUxT = setTimeout(updateTabUx, 60);
      });
      obs.observe(document.documentElement || document.body, {childList:true, subtree:true, attributes:true});
    } catch(e) {}
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
    installCopyObserver();
    installTabUxObserver();
    updateTabUx();
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
      setStatus(statusId, 'OCR Engine lädt noch... bitte erneut versuchen.');
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
      setStatus(statusId, 'OCR Engine lädt noch... bitte erneut versuchen.');
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
  border-radius: 10px !important;
}
#btn_prerhk_pdf button{
  padding: 6px 10px !important;
  font-size: 12px !important;
  font-weight: 600 !important;
  border: 1px solid rgba(148, 163, 184, 0.9) !important;
  background: #ffffff !important;
  color: #0f172a !important;
  box-shadow: none !important;
}
#btn_prerhk_pdf button:hover{
  filter: brightness(0.98);
}

/* Inline Pre-RHK PDF download row (next to copy buttons) */
#rhk_prerhk_inline_row{
  align-items: center !important;
  gap: 10px !important;
  margin-top: 4px !important;
}
#file_prerhk_pdf{
  max-width: 260px !important;
}
#prerhk_status{
  font-size: 12px !important;
  color: #475569 !important;
}

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

/* Copy + download buttons: match the same style (avoid heavy dark blocks) */
#btn_copy_doc button, #btn_download_doc button, #btn_copy_pat button, #btn_copy_rhk button {
  background: #ffffff !important;
  color: #0f172a !important;
  border: 1px solid rgba(148, 163, 184, 0.9) !important;
  box-shadow: none !important;
}
#btn_copy_doc button:hover, #btn_download_doc button:hover, #btn_copy_pat button:hover, #btn_copy_rhk button:hover {
  filter: brightness(0.98);
}

/* Make the copy/download button row more compact */
#rhk_copy_row button {
  padding: 4px 10px !important;
  font-size: 12px !important;
  line-height: 1.1 !important;
  min-height: 32px !important;
}



/* Tab content as card: improves scanability on Klinik/Labor, Imaging, Lufu/CPET etc. */
#rhk_input_tabs .tabitem {
  background: #ffffff !important;
  border: 1px solid rgba(0,0,0,0.10) !important;
  border-radius: 16px !important;
  padding: 14px 14px 10px 14px !important;
  box-shadow: 0 2px 10px rgba(0,0,0,0.04) !important;
  margin-bottom: 14px !important;
}

/* Make section headings within tabs feel like card headers */
#rhk_input_tabs .tabitem h3,
#rhk_input_tabs .tabitem h4 {
  margin-top: 0px !important;
  margin-bottom: 8px !important;
}

/* Reduce vertical noise between form rows */
#rhk_input_tabs .tabitem .gr-row {
  gap: 10px !important;
  margin-bottom: 10px !important;
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
  color-scheme: light !important;
  --card-bg: rgba(255,255,255,0.96);
  --border: rgba(0,0,0,0.08);

  /* Gradio CSS vars (override dark defaults) */
  /* Canvas: very light lavender (keeps your existing palette, but less "grau" dominant) */
  --body-background-fill: #faf9ff !important;
  --background-fill-primary: #ffffff !important;
  --background-fill-secondary: #faf9ff !important;
  --block-background-fill: rgba(255,255,255,0.96) !important;
  --block-border-color: rgba(0,0,0,0.08) !important;
  --input-background-fill: #ffffff !important;
  --input-border-color: rgba(0,0,0,0.18) !important;
  --body-text-color: #111111 !important;
  --input-text-color: #111111 !important;
}

html, body { color-scheme: light !important; background: #faf9ff !important; }

.gradio-container { max-width: 1700px !important; margin: 0 auto !important; padding-left: 8px; padding-right: 8px; }

/* ------------------------------------------------------------------
   Modern light card-based dashboard
   ------------------------------------------------------------------ */

/* Reusable card wrapper for grouping related parameters */
.rhk-card{
  background: rgba(255,255,255,0.98) !important;
  border: 1px solid rgba(15, 23, 42, 0.08) !important;
  border-radius: 20px !important;
  padding: 14px 14px 10px 14px !important;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04) !important;
  margin: 8px 0 !important;
}

/* ------------------------------------------------------------------
   Section cards (Apple-like header bar + subtle progress)
   ------------------------------------------------------------------ */

.rhk-section-card{ padding: 0 !important; overflow: hidden; border-radius: 22px !important; }

.rhk-sec-head{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
  background: rgba(168, 85, 247, 0.035); /* softer lavender tint */
}

.rhk-sec-title{
  font-size: 13px;
  font-weight: 850;
  color: #0f172a;
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
  width: 92px;
  height: 6px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.08);
  overflow: hidden;
}

.rhk-sec-bar > div{
  height: 100%;
  width: 0%;
  border-radius: 999px;
  background: rgba(168, 85, 247, 0.74);
}

.rhk-sec-body{
  padding: 14px 14px 10px 14px !important;
  background: #ffffff !important;
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
  border-radius: 22px !important;
}

/* Slightly tighter variant */
.rhk-card.rhk-card-tight{
  padding: 12px 12px 8px 12px !important;
}

/* Make headings inside cards look like card headers (no huge markdown spacing) */
.rhk-card h1, .rhk-card h2, .rhk-card h3{
  margin: 2px 0 10px 0 !important;
  padding: 0 !important;
  font-size: 15px !important;
  font-weight: 800 !important;
  color: #0f172a !important;
}
.rhk-card h4{
  margin: 2px 0 8px 0 !important;
  padding: 0 !important;
  font-size: 13px !important;
  font-weight: 700 !important;
  color: #0f172a !important;
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
  border-radius: 12px;
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
  color: #0f172a;
}
.rhk-trend-table tr:last-child td{ border-bottom: none; }

/* Inputs: subtle border and consistent radius */
.rhk-card input, .rhk-card textarea, .rhk-card select{
  border-radius: 12px !important;
  border: 1px solid rgba(15, 23, 42, 0.14) !important;
}

/* Accordions should also look like cards */
.gradio-container details{
  border-radius: 16px !important;
  border: 1px solid rgba(15, 23, 42, 0.08) !important;
  background: rgba(255,255,255,0.98) !important;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04) !important;
}
.gradio-container details > summary{
  padding: 10px 12px !important;
  font-weight: 800 !important;
  color: #0f172a !important;
}

/* Tabs: keep crisp, dashboard-like */
[role="tablist"] > button{
  border-radius: 999px !important;
  border: 1px solid rgba(15, 23, 42, 0.10) !important;
  background: rgba(255,255,255,0.9) !important;
}
[role="tablist"] > button[aria-selected="true"]{
  border-color: rgba(37, 99, 235, 0.35) !important;
  box-shadow: 0 2px 10px rgba(37, 99, 235, 0.10) !important;
}

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
/* Tabs: immer sichtbar, aber ohne Höhen-Drift → horizontal scroll (robust, verhindert Overlap) */
[role="tablist"]{
  flex-wrap: nowrap !important;
  overflow-x: auto !important;
  overflow-y: hidden !important;
  white-space: nowrap !important;
  gap: 6px !important;
  scrollbar-width: none;
}
[role="tablist"]::-webkit-scrollbar{ display:none; }
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

/* Tab-Content: Platzhalter unter sticky Tab-Leiste (verhindert, dass Überschriften/Progress-Bar "unter" die Tabs rutschen) */
.gradio-container .tabs{
  --rhk-tabnav-h: 60px;
}
.gradio-container .tabs > .tabitem{
  padding-top: 6px !important;
  scroll-margin-top: calc(74px + var(--rhk-tabnav-h, 60px) + 12px);
}

/* ------------------------------------------------------------------
   v27.2 Tabs: sticky + segmented control + subtitle + completion dots
   ------------------------------------------------------------------ */

/* Make the MAIN tab bar visually dominant and keep it visible while scrolling */
.gradio-container .tabs > .tab-nav,
.gradio-container .tab-nav{
  position: sticky !important;
  top: 74px !important; /* below topbar */
  z-index: 9500 !important;
  background: rgba(246, 247, 251, 0.92) !important;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  padding: 10px 6px 14px 6px !important;
  margin: 0 0 6px 0 !important;
  border-bottom: none !important;
  display: flex !important;
  flex-wrap: nowrap !important;
  overflow-x: auto !important;
  overflow-y: hidden !important;
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
  border: 1px solid rgba(15, 23, 42, 0.14) !important;
  background: rgba(255,255,255,0.88) !important;
  border-radius: 999px !important;
  padding: 8px 12px !important;
  font-weight: 650 !important;
  color: rgba(15,23,42,0.78) !important;
  box-shadow: 0 1px 0 rgba(15,23,42,0.02) !important;
}
[role="tablist"] > button[role="tab"][aria-selected="true"]{
  background: #ffffff !important;
  border-color: rgba(37, 99, 235, 0.35) !important;
  color: #0f172a !important;
  font-weight: 800 !important;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08) !important;
}

/* Small completion dot appended to each tab */
.rhk-tab-dot{
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 99px;
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

.badge-low { background: rgba(34,197,94,0.14); border-color: rgba(34,197,94,0.30); }
.badge-intermediate { background: rgba(234,179,8,0.16); border-color: rgba(234,179,8,0.32); }
.badge-intermediate-high { background: rgba(249,115,22,0.16); border-color: rgba(249,115,22,0.32); }
.badge-high { background: rgba(239,68,68,0.16); border-color: rgba(239,68,68,0.32); }
.badge-na { background: rgba(0,0,0,0.05); border-color: rgba(0,0,0,0.10); }
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
   v27.2: Main tabs must stay visible and feel like a segmented control
   ------------------------------------------------------------------ */
.gradio-container .tabs > .tab-nav,
.gradio-container .tab-nav{
  position: sticky !important;
  top: 86px !important; /* below the glass topbar */
  z-index: 9500 !important;
  background: rgba(246,247,251,0.92) !important;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  padding: 8px 6px !important;
  margin: 0 0 6px 0 !important;
  border-bottom: 1px solid rgba(15,23,42,0.08) !important;
}

.gradio-container .tab-nav button{
  flex: 0 0 auto !important;
  border-radius: 999px !important;
  padding: 8px 12px !important;
  font-size: 13px !important;
  font-weight: 700 !important;
  border: 1px solid rgba(15,23,42,0.10) !important;
  background: rgba(255,255,255,0.75) !important;
  color: #0f172a !important;
  box-shadow: 0 1px 6px rgba(15,23,42,0.05) !important;
  margin: 4px 6px 4px 0 !important;
}
.gradio-container .tab-nav button:hover{
  filter: brightness(0.985);
}
.gradio-container .tab-nav button[aria-selected="true"]{
  background: #ffffff !important;
  border: 1px solid rgba(15,23,42,0.18) !important;
  box-shadow: 0 2px 12px rgba(15,23,42,0.10) !important;
  font-weight: 800 !important;
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
  border-radius: 99px;
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
  border-radius: 10px;
  font-size: 12px;
  font-weight: 500;
  background: rgba(15,23,42,0.96);
  color: rgba(255,255,255,0.95);
  border: 1px solid rgba(255,255,255,0.12);
  box-shadow: 0 10px 26px rgba(0,0,0,0.22);
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


/* ------------------------------------------------------------------
   Spiro-Logic Wizard (CPET live education)
   ------------------------------------------------------------------ */
.spiro-edu{
  border: 1px solid rgba(0,0,0,0.06);
  background: rgba(255,255,255,0.96);
  border-radius: 18px;
  padding: 12px 12px;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
}
.spiro-edu--overall{ background: rgba(168, 85, 247, 0.035); }
.spiro-edu__title{
  font-size: 13px;
  font-weight: 850;
  color: #0f172a;
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
  background: #ffffff !important;
}
.rhk-cpet-card .rhk-sec-body{
  background: #ffffff !important;
}
.rhk-cpet-card .rhk-sec-head{
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
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
/* DOCX Import Ampel (UI only; payload provides green/yellow/red) */
.docx-box.good{border-color:rgba(34,197,94,.38);background:rgba(34,197,94,.06)}
.docx-box.yellow{border-color:rgba(234,179,8,.45);background:rgba(234,179,8,.06)}
.docx-box.bad{border-color:rgba(239,68,68,.40);background:rgba(239,68,68,.06)}
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

/* ------------------------------------------------------------------
   Startseite: Tool-Disclaimer (Footer)
   ------------------------------------------------------------------ */
#rhk_tool_disclaimer_wrapper{margin-top:14px;padding:0 14px 12px 14px}
#rhk_tool_disclaimer{border-top:1px solid rgba(0,0,0,.08);padding-top:10px}
.rhk-disclaimer-inner{max-width:1200px;margin:0 auto}
.rhk-disclaimer-title{font-weight:900;font-size:12px;color:rgba(15,23,42,.75);margin:0 0 4px 0}
.rhk-disclaimer-text{font-size:11px;line-height:1.35;color:rgba(15,23,42,.62)}

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
