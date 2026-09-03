# jobradar — Test data & seeding (step 7)

> **What this is.** The seeding and fixture design that makes the
> [test plan](test-plan.md) runnable: the seed contract, the composable
> scenarios each wave needs, the two stub servers (source + LLM), the run
> trigger, and the determinism/isolation rules. Grounded in the real schema
> (`core/db.py`) and the existing harness (`fixtures/`).

Status: draft v1 (2026-09-01).

---

## 1. Principles (what already holds, and what we add)

- **DB-level seeding** — jobradar has no vacancy write API, so seeds `INSERT`
  through the product's own schema (`db_connect`). Schema drift fails loudly at
  setup. *(already true, `fixtures/seed.py`)*
- **Per-worker isolation** — each worker gets a temp `JOBRADAR_HOME`, seeds once,
  snapshots `jobs.db.template`, and file-restores it before every test. *(keep)*
- **No clock freeze** — the server clock can't be frozen from e2e. Time-dependent
  data uses **seeded relative dates** (`now − Nd`). *(keep, formalise)*
- **Composable scenarios (new)** — move from one fixed 7-row seed to a **seed
  builder + named scenarios**, so a test seeds exactly the rows it needs
  (archived, aged, hiring, run-journal…).
- **Offline & deterministic (new)** — no network. Two local **stub servers**
  (source RSS + LLM) make `run`-based tests reproducible.

---

## 2. The seed contract — `jobs` columns

From `core/db.py`. A `seed_vacancy(**overrides)` helper supplies defaults; a test
overrides only what it asserts on.

| Column | Default | Set it for… |
|---|---|---|
| `hash` (PK) | required, unique | every row |
| `source` | `dou` | source filter, cross-source merge (`dou`/`djinni`) |
| `url` | `https://example.test/<hash>` | source link |
| `title` | required | search, word-boundary, exclude-by-title |
| `company` | `''` | company page, dedup key |
| `location` / `salary` | `''` | full-text search, card facts |
| `description` | `''` | tags (`card_terms`), search, expand |
| `description_html` | `<p>{description}</p>` | sanitized display |
| `extra` | `''` | Djinni structured fields (JSON) |
| `sources` | `''` | **cross-source merge** — JSON `{source: url}` (both links) |
| `published_at` | `NOW` | card date |
| `first_seen` | `NOW` | **period filter, TTL** — set `now − Nd` |
| `l0_pass` | `1` | L0-dropped rows → `0` + `l0_reason` |
| `l0_reason` | `''` | "show L0-dropped", `/runs` reasons |
| `score` | `None` | rail, min-score, sort; **unscored** → keep `None` |
| `band` | `''` | band pill (derived from score) |
| `verdict` | `''` | **score popup** verdict |
| `matched` | `''` | **score popup Covers** (green) — JSON list |
| `gaps` | `''` | **score popup Gaps** (red) — JSON list |
| `rubric` | `''` | rubric version tag |
| `scored_at` | `None` | scored marker |
| `notified_at` | `None` | (Telegram — out of Playwright scope) |
| `status` | `new` | tabs, triage — `new/interested/applied/skipped/archived` |
| `status_at` | `None` (NOW if not new) | **Applied-tab sort, calendar** |
| `run_id` | `None` | link to a `runs` row |
| `hiring_status` | `''` | **hiring stages** — `waiting_hr/pre_screen/tech_interview/finish` |
| `hiring_notes` | `''` | per-stage notes — JSON `{stage: text}` |
| `cover_data` | `''` | **cached cover letter** — JSON `{letter, evaluation, traceability, fit_score, band, model, generated_at}` |

**Adjacent tables:**
- `runs` (`fetched, dup_skipped, l0_dropped, added, revived, notified, feeds`,
  `started_at`, `finished_at`, `triggered_by`) — the `/runs` funnel & per-feed
  breakdown. `feeds` is JSON; **confirm its exact shape against `views.runs_context`
  when implementing** (the per-feed rows + the cap marker read from it).
- `run_dups` (`run_id, hash, source, url, title, company`) — the dedup-pairs list
  on `/runs`.
- `meta` (`last_new_job_at`, `last_collect_ok`, …) — freshness display only.

---

## 3. Seed sets (consolidated: 12 → 3 + overlays)

Consolidated to **3 DB seed sets + profile overlays**. Rows carry stable names
(`v1`, `v_arch`, …) so tests assert **by identity or scoped count, never a global
total** — that discipline is what lets one fixture serve many tests without
turning brittle (and keeps `catalog` from becoming an opaque *mystery guest*).

### `catalog` — the one rich read-fixture
Absorbs the former base / base+ / scored-detail / archived / aged / runs-journal.
Documented manifest:

| Row | source | status | score | for |
|---|---|---|---|---|
| `v1` Acme "Senior QA Automation" | dou | new | 8.7 | +`verdict`/`matched[]`/`gaps[]` → score popup |
| `v2` Acme "SDET (Java)" | dou | new | 7.2 | 2nd Acme → company page |
| `v3` Globex "QA Automation (JavaScript)" | djinni | new | 6.5 | JS-not-Java word boundary |
| `v4` Initech "Test Automation Lead" | dou | new | 8.0 | 12 terms → "+N" collapse |
| `v5` Umbrella "Automation QA" | djinni | new | 7.0 | mixed source |
| `v6` Hooli "QA Engineer" | dou | interested | 7.5 | status tab |
| `v7` Stark "Senior AQA" | dou | applied | 8.2 | `status_at` → Applied tab, calendar |
| `v8` "…(no score)" | dou | new | — | unscored sink (sort) |
| `v9/v10/v11` dated | dou | new | var | `first_seen −3d/−10d/−40d` → period filter |
| `v_arch` | dou | archived | 8.0 | hidden from feed; still on calendar (ANL-8) |
| `v_aged` | dou | skipped | 6.0 | `first_seen −200d` → TTL pre-state (test adds a run) |

Plus `runs` rows — `r1` balanced, `r2` unbalanced (red-flag), `r3` with a
**capped** feed (25) — and `run_dups` → `/runs` funnel / per-feed / cap (ANL-1/2).
Some rows also carry an exclude-target tag and an in-demand extra-skill term for
the profile overlays to act on.

### `hiring` — kept separate (deliberate)
Focused fixture: `applied` rows across stages (`waiting_hr`; `tech_interview`
with per-stage `hiring_notes`; `finish` with cached `cover_data`) + one applied
with **no** cover (generate/degrade). Separate because these tests set specific
per-stage state and mutate stages — a focused fixture keeps those assertions
clean and keeps 4+ applied rows from perturbing `catalog`'s calendar / Applied-tab.
Feeds: HIRE-1/2/3/5/10/16.

### `empty` — no DB
The pre-first-scan state. EMPTY-1/2, FEED-23.

### Profile overlays (over `catalog`/`hiring`, **not** DB seeds)
Same DB, different `profile.json`: `default`, `with-exclude` (terms matching
catalog rows → FEED-20/21, PRO-12), `with-extra-skill` (in-demand term → ANL-9),
`none` (delete → EMPTY-5, PRO-6).

### Not seed sets
- **empty-filtered** (EMPTY-4) = `catalog` + an over-narrow filter query — no new seed.
- **RSS source fixtures** = the run-path inputs (§4 H1), separate by nature.

**Isolation:** worker snapshot = `catalog`. A test needing `hiring`/`empty`
re-seeds after `resetState` (restore template → `seed.py <set>`). Overlays
write/delete `profile.json` per test. Assertions stay identity/scoped, so a row
later added to `catalog` doesn't cascade into unrelated tests.

---

## 4. Harness servers (Wave 0)

### H1 — stub source server (fixture RSS)
A tiny local HTTP server serving canned DOU/Djinni RSS at fixed paths. Config
points the feeds at it and the run reads fixtures, never the network.

- **Wiring:** run **without a `profile.json`** so `candidate.effective_feeds`
  falls back to `config.sources.dou.feeds` / `.djinni.feeds` (with a profile,
  feeds come from the role). Set those to `http://127.0.0.1:<stub>/dou/<case>.xml`.
- **RSS fixtures:** `clean-match`, `with-duplicate`, `l0-reject` (below salary /
  off-keyword), `cross-source` (same job in a DOU + a Djinni file),
  `cap-25` (25 items), `digit-title`, `case-whitespace`, `title-exclude`.
- **Unlocks:** all `PIPE-*` ingestion/dedup/L0.

### H2 — stub LLM server (scoring **and** cover letters)
The product speaks OpenAI-compatible (`provider=openai` + `base_url`, PR #14), so
the stub implements `POST /chat/completions` and returns deterministic JSON.

- **Wiring:** `scorer.enabled:true` in config; the **account is set in the profile**
  (`llm_provider:openai`, `llm_base_url:http://127.0.0.1:<stub>`, `api_key:test`) —
  the single source `llm_settings` reads. Scoring and cover letters share it, so
  both route to the stub; set `cover_letter.model` in config (scorer keeps its own).
- **Response modes** (keyed off a marker in the request payload / vacancy text):
  - *score*: `{score, band, verdict, covers[], gaps[]}` — deterministic per marker.
  - *cover*: `{letter, evaluation, traceability, fit_score}` — band derived from score.
  - *drift*: returns a **different** score on the 2nd call → PIPE-9 (no-rescore).
  - *throw*: 500 / malformed body → HIRE-14 (graceful degrade).
  - *call counter*: an introspection route the test reads to assert **call count**
    → no-rescore / cover cache (HIRE-10, PIPE-9).
- **Unlocks:** PIPE-1/9 (scoring wiring, no-rescore) and the whole HIRE cover
  block (4/7/9/10/11/12/13/14).

### H3 — run trigger + wait
Drive the **real** button: `POST /run` (303, `started`/`busy`), then poll until
done — a new `finished_at` row in `runs`, or `Runner.status().running == false`,
or the feed reaching the expected count — with a timeout. Helper
`triggerRunAndWait(api)`. **This is also the OPS-1 test** — build once, reuse.

### H4 — seed scenarios
Implement §3 as parametrised `seed.py <scenario>` + a Node `seed(home, scenario)`
helper. Covers archived / aged / runs-journal / exclude-profile / hiring.

### H5 — time (no code, a convention)
Relative dates only (`now − Nd`). Period boundaries seeded with margin
(`−3d/−10d/−40d`, not exactly `−7d`) to avoid midnight flakiness.

---

## 5. Determinism & isolation risks (validate during Wave 0)

- **Writing while the server is up.** Scenario seeds run in a separate process
  (`runPython`) against a `jobs.db` the live server also holds. Ensure a
  `busy_timeout`/WAL so a quick `INSERT` between requests doesn't hit "database is
  locked". Run-based tests avoid this (the server itself writes). **Verify early.**
- **Feeds-from-config vs profile.** Run-based tests must run **without a profile**
  (or with a controlled `stack`) so feeds resolve to the stub. Document per test.
- **`runs.feeds` JSON shape.** The `/runs` per-feed + cap rendering reads it —
  reverse it from `views.runs_context` before seeding `catalog`'s `runs` rows.
- **Stub ports.** One stub pair per worker (like the server: `port + workerIndex`)
  or a shared stub with per-request determinism. Prefer per-worker for isolation.
- **Two projects.** Everything runs under chromium + mobile; keep seeds
  project-agnostic (they already are — DB, not viewport).

---

## 6. Scenario → wave map

| Wave | Seed set(s) | Profile overlay | New harness |
|---|---|---|---|
| **0 harness** | — | — | H1 stub source, H2 stub LLM, H3 run trigger, H4 seed builder |
| **1 seed-only + contract** | `catalog`, `empty` | default / with-exclude / with-extra-skill / none | none beyond H4 |
| **2 pipeline + ops** | `catalog` (`v_aged`) + RSS fixtures | none / controlled | H1, H2 (score), H3 |
| **3 hiring & cover** | `hiring` | default | H2 (cover) |

Wave 1 needs **no stub servers** — `catalog` + `empty` + profile overlays only.
That is why it is the cheapest, highest-ROI wave: the whole API/UI base runs on
seeded state alone.

---

## 7. Fixture inventory to create

```
jobradar-e2e/fixtures/
  seed.py                      # parametrised: seed.py <set>   (catalog | hiring | empty)
  profiles/                    # profile.json overlays: default | with-exclude | with-extra-skill
  feeds/
    dou-clean-match.xml  dou-with-duplicate.xml  dou-l0-reject.xml
    dou-cap-25.xml  dou-digit-title.xml  dou-case-whitespace.xml
    dou-title-exclude.xml  djinni-cross-source.xml
  cv/
    qa-automation.txt          # known stack for PRO detect/validate tests
  llm/
    score-responses.json       # canned scoring by marker
    cover-response.json        # canned cover letter
  stubs/
    source-server.(ts|py)      # H1
    llm-server.(ts|py)         # H2
```

---

## 8. Open decisions

1. **Stub language** — Node (lives with the Playwright project, one toolchain) vs
   Python (reuses product parsers). Lean **Node** for the LLM stub (pure HTTP
   JSON); the source stub is just static XML — a file server suffices.
2. **Scenario seeding** — re-seed a chosen scenario per test (clean, slightly
   slower) vs a few extra per-worker snapshots (faster, more template files).
   Recommend **re-seed per test** for clarity; revisit if runtime bites.
3. **Run wait signal** — poll `runs.finished_at` vs `Runner.status()` vs feed
   count. Recommend `runs.finished_at` (authoritative, single source — matches
   `runner.last_run_stats`).
4. **Whether to add a test-only seed endpoint** to the product — **no**; keep test
   seeding out of prod code, via `runPython`.

---

## 9. Definition of done (step 7)

- `seed_vacancy` builder + the §3 scenarios implemented and used by name.
- H1/H2/H3 stubs+trigger in place, offline and deterministic, one pair per worker.
- Every Wave-1 test runnable on seeds alone; Waves 2–3 runnable via the stubs.
- No product code changed for testing (seams already exist: `JOBRADAR_HOME`,
  swappable scorer/source via config `base_url`, `POST /run`).
