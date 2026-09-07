"""Shared presentation data: status/band labels, tag hints, source logos, header
icons, and the single inline popup script. Page-specific data lives with its view.
"""

# Triage statuses: DB key → human label. Order drives the tabs and buttons.
# 'archived' has a label (for lookups) but no feed tab of its own — it lives on
# the Applied tab, behind its "Show archived" toggle.
STATUS_LABELS = {
    "new": "new",
    "interested": "interested",
    "applied": "applied",
    "skipped": "skipped",
    "archived": "archived",
}
STATUS_ORDER = ("new", "interested", "applied", "skipped")

# Hiring pipeline for an applied vacancy: DB key → human label. Order drives the
# stage buttons on the Applied tab. Per-stage notes are kept as JSON keyed by
# these same DB keys (jobs.hiring_notes).
HIRING_LABELS = {
    "waiting_hr": "Waiting for HR response",
    "pre_screen": "Pre-screen",
    "tech_interview": "Tech interview",
    "finish": "Finish",
}
HIRING_ORDER = ("waiting_hr", "pre_screen", "tech_interview", "finish")

# Auto-scan cadence labels (Settings → Auto-scan). Keyed by candidate.SCHEDULE_REPEATS
# (which owns the canonical order); the view builds the dropdown from that order.
SCHEDULE_REPEAT_LABELS = {
    "every_6h": "Every 6 hours",
    "every_12h": "Every 12 hours",
    "daily": "Every day",
    "weekday": "Every weekday",
    "weekly": "Every week",
    "biweekly": "Every two weeks",
    "monthly": "Every month",
}
# Auto-scan weekday picker (weekly/two-weekly). 0=Monday … 6=Sunday, matching
# datetime.weekday(); order drives the dropdown. Named apart from the calendar's own
# short WEEKDAYS in views.py — different purpose, different labels.
SCHEDULE_WEEKDAYS = (
    (0, "Monday"),
    (1, "Tuesday"),
    (2, "Wednesday"),
    (3, "Thursday"),
    (4, "Friday"),
    (5, "Saturday"),
    (6, "Sunday"),
)
SCHEDULE_WEEKDAY_LABELS = dict(SCHEDULE_WEEKDAYS)

# Scorer bands: machine key → card label.
BAND_LABELS = {
    "strong": "strong match",
    "worth_trying": "worth trying",
    "stretch": "stretch",
    "skip": "skip",
}

# Tag-chip hint in its three states (neutral / in filter / excluded).
TAG_HINTS = {
    "": "show only vacancies with this tag",
    "on": "click to hide vacancies with this tag",
    "off": "click to remove the filter",
}

# Source logos on cards (files in resources/, whitelisted in routes._RESOURCES).
SOURCE_LOGOS = {"dou": "dou_logo.png", "djinni": "djinni_logo.png"}

# Header icons (inline SVG, styled via currentColor in app.css).
RADAR_ICON = (
    '<svg class="ico" viewBox="0 0 16 16" aria-hidden="true">'
    '<circle cx="8" cy="8" r="6.2"/><path d="M8 8L12.4 4.4"/>'
    '<circle cx="8" cy="8" r="1.3"/></svg>'
)
ACCOUNT_ICON = (
    '<svg viewBox="0 0 22 22" class="acc-ico" aria-hidden="true">'
    '<circle cx="11" cy="8" r="3.4"/>'
    '<path d="M4 18.5c0-3.9 3.1-6 7-6s7 2.1 7 6"/></svg>'
)

# The one client-side script: instant search inside the tag/company popups, and
# stopping a company-link click from toggling the card's <details>. Vanilla,
# delegated — checkboxes and Apply are native; JS only hides non-matching rows.
POPUP_JS = (
    "(function(){document.addEventListener('input',function(e){"
    "var b=e.target;if(!b.classList||!b.classList.contains('picksearch'))return;"
    "var p=b.closest('.pick-panel');if(!p)return;"
    "var q=b.value.trim().toLowerCase();"
    "p.querySelectorAll('.pick-sect').forEach(function(s){var any=false;"
    "s.querySelectorAll('.pickrow').forEach(function(r){"
    "var n=(r.getAttribute('data-name')||'');"
    "var hit=!q||n.indexOf(q)!==-1;r.style.display=hit?'':'none';if(hit)any=true;});"
    "s.style.display=any?'':'none';});});"
    "document.addEventListener('click',function(e){"
    "if(e.target.closest&&e.target.closest('a.co'))e.stopPropagation();});"
    "})();"
)

# Cover-letter generation on the hiring cards: the ✍ button POSTs to /hiring/cover,
# shows a spinner while Sonnet writes, then fills the modal (letter, evaluation,
# traceability, fit band) and flips the button to Regenerate. Copy uses the
# clipboard API. Vanilla, delegated — the modal open/close stays CSS :target.
COVER_JS = (
    "(function(){"
    "var BAND={'GREEN':'green','GREEN EDGE':'edge','AMBER':'amber','RED':'red','SKIP':'skip'};"
    "function fill(m,d){"
    "var L=m.querySelector('.cl-letter');if(L)L.textContent=d.letter||'';"
    "var E=m.querySelector('.cl-eval');if(E)E.innerHTML=d.evaluation_html||'';"
    "var T=m.querySelector('.cl-trace');if(T)T.innerHTML=d.traceability_html||'';"
    "var B=m.querySelector('.cl-band');if(B){var b=d.band||'';"
    "B.textContent=b+(d.fit_score!=null?(' \\u00b7 '+d.fit_score):'');"
    "B.className='cl-band cl-'+(BAND[(b).toUpperCase()]||'');}"
    "var r=m.querySelector('.cl-result');if(r)r.removeAttribute('hidden');"
    "var g=m.querySelector('.cl-generate');if(g){g.textContent='Regenerate';"
    "g.setAttribute('data-regenerate','1');}}"
    "document.addEventListener('click',function(e){"
    "var g=e.target.closest&&e.target.closest('.cl-generate');"
    "if(g){e.preventDefault();var m=g.closest('.modal');if(!m)return;"
    "var s=m.querySelector('.cl-status');"
    "if(s){s.textContent='Generating\\u2026 this takes a moment.';s.className='cl-status busy';}"
    "g.disabled=true;"
    "var body=new URLSearchParams();body.set('hash',g.getAttribute('data-hash')||'');"
    "if(g.getAttribute('data-regenerate')==='1')body.set('regenerate','1');"
    "var tok=m.getAttribute('data-token')||'';if(tok)body.set('token',tok);"
    "fetch('/hiring/cover',{method:'POST',headers:{'Content-Type':"
    "'application/x-www-form-urlencoded'},body:body.toString()})"
    ".then(function(r){return r.json();}).then(function(d){g.disabled=false;"
    "if(!d.ok){if(s){s.textContent=d.error||'Generation failed.';s.className='cl-status err';}return;}"
    "if(s){s.textContent='';s.className='cl-status';}fill(m,d);})"
    ".catch(function(){g.disabled=false;"
    "if(s){s.textContent='Network error.';s.className='cl-status err';}});return;}"
    "var c=e.target.closest&&e.target.closest('.cl-copy');"
    "if(c){e.preventDefault();var mm=c.closest('.modal');"
    "var L=mm&&mm.querySelector('.cl-letter');"
    "if(L&&navigator.clipboard){navigator.clipboard.writeText(L.textContent||'')"
    ".then(function(){c.textContent='Copied';"
    "setTimeout(function(){c.textContent='Copy';},1500);});}}"
    "});})();"
)

# Hiring notes: the Save button is disabled until the textarea differs from the
# value it was rendered with (defaultValue), so an untouched card can't be saved.
# Progressive enhancement — with JS off the button stays usable.
HIRING_JS = (
    "(function(){"
    "function sync(t){var f=t.closest('form');if(!f)return;"
    "var b=f.querySelector('.hsave');if(b)b.disabled=(t.value===t.defaultValue);}"
    "document.addEventListener('input',function(e){var t=e.target;"
    "if(t&&t.classList&&t.classList.contains('hnote'))sync(t);});"
    "function init(){var n=document.querySelectorAll('.hnote');"
    "for(var i=0;i<n.length;i++)sync(n[i]);}"
    "if(document.readyState!=='loading')init();"
    "else document.addEventListener('DOMContentLoaded',init);"
    "})();"
)
