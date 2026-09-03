# CLAUDE.md — jobradar

Read at the start of each session. It says **why the project exists**, **where things
live**, **what must not break silently**, and **how we work**. Update the "State" section
when something real moves; leave the invariants alone unless a decision changes (then write
an ADR).

State: 2026-08-20. Flask + Jinja2 migration done (ADR-0012); code, UI, and scorer rubric are
now all English (ADR-0013) — see "State" at the bottom.

---

## 1. Purpose

Yevhen (QA Automation / SDET, Kyiv) doesn't want to miss relevant
vacancies without visiting three sites daily.

The tool does exactly:

```
sources → dedup → cheap L0 filter → LLM scoring against the profile → Telegram → web triage
```

**What it is NOT:** not a mass-apply system, not a job-search CRM, not a replacement for
Djinni alerts. Its one real value: **scoring against a real profile with honest boundaries**,
which filters out what looks like a fit by title but isn't by substance.

**Scope discipline.** This is a small personal tool, and also a portfolio artifact — read by
people evaluating engineering conventions. Both call for the same restraint: prefer finishing
and polishing what already exists over adding another feature. **If a change isn't earning its
keep, say so plainly instead of building it.**

## 2. Architecture

Layered, one direction: `web → domain/core`. The web layer never leaks into the core; the
core never imports the web.

```
jobradar/
  __main__.py     # python -m jobradar <cmd>  (serve → Flask app; run/check/… → cli)
  app.py          # create_app() factory: config, runner, auth, db teardown, Jinja env
  web/            # Flask layer
    routes.py     #   Blueprint — thin handlers: gather data → render_template
    views.py      #   data-shaping (feed query/filter, calendar/company/stats/runs)
    forms.py      #   POST parsing (profile save/preview, run trigger, status change)
    filters.py    #   Jinja filters (band_class, fmt_iso, humanize_*, feed_label, pie SVG…)
    urls.py       #   Jinja globals (feed_link, tech_url, company_link, calendar_link…)
    auth.py       #   token check
  templates/      # Jinja2 — base.html + one per page + partials/_*.html
  static/
    css/app.css   #   compiled from scss/ partials (make css)
    scss/         #   source partials (_tokens, _shell, _card, _calendar, …)
  core/           # db, dedup, text, pipeline, scoring, sources — pure logic
  domain/         # domain models/helpers
  paths.py clock.py roles.py skills.py candidate.py stats.py runner.py config.py cli.py
```

Source of truth for structure and past decisions: `docs/adr/` and the README. Product track
(frozen by ADR-0003): `docs/PRODUCT.md`. Terms: `docs/glossary.md`.

## 3. Conventions

- **`.py` holds Python, `.html` holds templates, CSS holds styles.** No HTML strings in
  Python, no logic in templates beyond presentation.
- **Comments and UI in English, sparse.** The code documents itself; comment only the
  non-obvious *why*. Code, comments, and UI strings are all English (ADR-0013). What stays
  Ukrainian is **functional data bound to the UA job market** — DOU/Djinni feed keywords and
  L0 regexes (`roles.py`), dedup noise words (`dedup.py`), skill matchers and their internal
  group keys (`skills.py`; the UI shows them via `GROUP_LABELS` / the `group_label` filter),
  seniority-strip words (`views.py`). Translating those breaks matching, so don't. ADRs stay
  Ukrainian (the log's).
- **Web tests go through the Flask test client** (`client.get("/")`, assert on the response),
  not by calling render internals. Domain logic is unit-tested directly. All on pytest.
- **Every commit passes `make check`** (ruff + mypy + css-check + pytest); CI runs the same.
- **Conventional Commits, English subject.** `feat:` / `fix:` / `refactor:` / `test:` /
  `docs:` / `style:` / `chore:`. One logical change per commit; docs separate from code.
- **main stays green.** Short-lived `feat/<slug>` branches for multi-commit work; deploy = tag.
  No force-push to main, no rebase of published history; undo is a revert commit.
- Never commit `config.json`, `jobs.db`, or logs (`.gitignore`).

## 4. Invariants — do not "fix" these silently

These are deliberate trade-offs, not bugs. Changing one needs a reason and usually an ADR.

- **Scores are never recomputed.** A scored vacancy keeps its score forever (LLMs drift).
  If you change the rubric in `SCORER_SYSTEM` or facts in the profile, **bump
  `RUBRIC_VERSION`** — otherwise the DB mixes scores from different criteria.
- **The profile is the single source of truth about the candidate** for the scorer, including
  its "boundaries that must not blur" block (Python isn't a work language; pytest without
  commercial use; Playwright as ownership, not hands-on). Without it the LLM gives every
  Python vacancy an 8/10. Don't soften it "to get more matches."
- **Dedup key = `sha256(normalized_company | normalized_title)`, TTL 180 days.** Deliberate
  skew toward showing duplicates over missing a vacancy; a role reopened after ~6 months
  should return with status reset. Known duplicate cases (internal number changes, seniority
  renames) are accepted on purpose — don't strip digits from titles to "fix" it.
- **Boards are not scraped.** DOU and Djinni are read from their official RSS only; there
  is no email/IMAP integration. Don't propose Selenium/Playwright scraping of boards, or
  re-adding an email source.
- **Silent failure is the top risk.** A broken feed parser looks exactly like an empty
  market. The heartbeat (no new records for N hours → Telegram) guards it — don't remove it.
- **DOU feed caps at 25 records.** A feed that hit the cap is flagged on `/runs` — keep the
  marker; it's the only way the radar can silently drop rows.
- **LLM scoring is two-tier:** L0 (regex + salary-band, free, deterministic) gates L1 (LLM).
  L0 changes don't apply retroactively; a posting with no description → the scorer is told
  not to exceed 6.
- **Testability seams (keep working):** `JOBRADAR_HOME` env-override for all paths; injected
  `clock`; swappable scorer/source; stable `data-testid` on key UI nodes (the Playwright e2e
  in `jobradar-e2e/` depends on them).

## 5. Commands

```sh
make check      # everything CI wants: ruff + mypy + css-check + pytest
make test       # pytest only
make css        # recompile scss/ → static/css/app.css
make serve      # web UI on localhost (Flask)

python -m jobradar serve   # web UI
python -m jobradar run     # a scan (add --dry-run to skip sending)
python -m jobradar check   # verify DOU / scorer / Telegram
python -m jobradar stats   # collection funnel — the main tuning tool
python -m jobradar top     # best from the DB
```

## 6. State

**The web layer is on Flask + Jinja2** (ADR-0012). The stdlib-only constraint that shaped
the old design (NAS survival) is dropped — NAS deployment is off the table; the project is
a portfolio artifact optimized for readability and convention. The migration is done: the
hand-rolled `http.server` and the in-house `el()` HTML builder (`render/`) are gone, every
route renders a Jinja template from a `web/views.py` context, and the render-coupled tests
run through the Flask test client. Core/domain logic and the testability seams are unchanged.

**Code, UI, and the scorer rubric are now all English** (ADR-0013), reversing "UI stays
Ukrainian" from ADR-0012. Comments across `core/`, the root modules, and SCSS were translated;
UI strings, the `SCORER_SYSTEM` rubric and the scorer-input labels are English, and
`RUBRIC_VERSION` was bumped to **v2** (past scores keep their v1 tag — not recomputed).
Functional data tied to the Ukrainian job market stays Ukrainian (see the language convention
in §3); skill-group keys are shown in the UI via `skills.GROUP_LABELS` / the `group_label`
Jinja filter. `make check` is green (ruff + mypy + css-check + pytest, 204 tests).

Next after the migration: the personal backlog is Phase 0–1 of `docs/PRODUCT.md` (first real scan,
a week without the LLM to tune L0, then scoring at threshold 6).
