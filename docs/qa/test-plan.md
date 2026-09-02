# jobradar — Playwright test plan

> **Scope.** The **Playwright layer** only. The pytest suite (275 tests) is the
> pyramid's base — untouched, counted as-is. This is the requirements-driven plan
> for the e2e/contract layer, in three parts: the coverage **catalog** (what to
> test, mapped from [requirements.md](requirements.md)), the **rebalance** into a
> healthy pyramid, and the **waves** that order the build. Live status:
> [traceability.md](traceability.md); seeding and fixtures: [test-data.md](test-data.md).
>
> **Method.** Planned top-down from requirements ("as it should be"), then
> reclassified by the strict rule **a test's layer = the layer of its assertion**
> to right the pyramid — see *Prioritisation & rebalance* below.

In-scope epics: **6, 7, 8, 9, 10 (OPS-1 only)** as first-class Playwright targets;
**1–4** as complex-e2e substrate. Out (stay pytest): **5 Notifications & Telegram
distribution, 11 Access control, email ingestion (ING-3), the ≤6 no-description cap
(SCO-4), and threshold→notification gating (SCO-5)** — none has a browser surface.

---

## Layer definitions (within Playwright)

| Layer | Driver | What it does | Cost |
|---|---|---|---|
| **UI** | `page` | render + interaction assertions on one page, seeded DB | cheap–medium |
| **API** | `request` | assertion on the **raw HTTP response** — status / headers / `Location` / body (the app serves HTML, plus JSON on `/hiring/cover`) — over the wire, **no browser render** | cheap |
| **E2E** | `page` + `request`/CLI | multi-step: **API/CLI/seed prep → final UI assertion** | expensive |

**The pipeline principle (the crux of the rebalance).** Epics 1–4 (ingestion,
dedup, L0, scoring) are *logic already owned by pytest*. Playwright does **not**
re-verify that logic per-criterion. It covers them only where they **surface to
the user**, bundled into a small set of **flagship E2E** journeys — each one
heavy on API/seed prep, thin on the final visible assertion. That is exactly the
"balance the pyramid" show-case: few, high-value e2e; the deterministic base
stays in pytest.

**ID scheme.** `PW-<EPIC>-<n>`. `Covers` cites the requirement acceptance-criteria
IDs from [requirements.md](requirements.md), so traceability runs both ways.

---

## Epics 1–4 — pipeline substrate (flagship E2E only)

Logic → pytest. These are the *few* journeys where the pipeline is observed
end-to-end through the UI. Every one seeds a fixture source and triggers a run.

| ID | Scenario | Layer | Covers | Prep |
|---|---|---|---|---|
| PW-PIPE-1 | **Fresh scan surfaces a scored match.** DOU RSS fixture = 1 clean match + 1 duplicate + 1 L0-reject → `run` (mock scorer) → feed shows the 1 match with score on the rail; `/runs` funnel reconciles `fetched = dups+filtered+new`; the L0-reject appears under "show L0-dropped" with its reason | E2E | ING-1.1, DED-1.2, L0-2.2, L0-4.1, SCO-1.1, ANL-1.1 | fixture feed + mock scorer |
| PW-PIPE-2 | **Cross-source dedup.** Same vacancy in a DOU fixture and a Djinni fixture → `run` → one card, both source links present | E2E | ING-2.1, DED-2.1 | 2 fixtures |
| PW-PIPE-3 | **Reopened role returns fresh.** Seed a `skipped` vacancy, age `first_seen` > 180d → `run` → the card returns in `new`, not `skipped` | E2E | DED-3.1, DED-3.2 | seed + clock |
| PW-PIPE-4 | **Case/whitespace is the same job.** Two fixture items differing only in case/whitespace of company+title → `run` → one card | E2E | DED-1.3 | fixture |
| PW-PIPE-5 | **Digit-in-title double-show is accepted.** Two items differing only by a number in the title → `run` → two cards (regression guard on the deliberate trade-off) | E2E | DED-1.4 | fixture |
| PW-PIPE-6 | **DOU 25-cap is flagged.** DOU fixture with ≥25 items → `run` → `/runs` shows the "capped" marker + the feed's window in hours | E2E | ING-6.1 | fixture(25+) |
| PW-PIPE-9 | **Scores are never recomputed.** `run` twice over the same fixture (mock scorer returns a different value the 2nd time) → the card keeps its first score | E2E | SCO-3.1 | fixture + mock scorer |
| PW-PIPE-10 | **Title-exclude, not body.** Fixture: one item with an anti-goal in the *title*, one with the same term only in the *body* → `run` → the title one is dropped, the body one survives | E2E | L0-3.1, L0-3.2 | fixture + profile.exclude |

**8 flagship E2E** for the whole pipeline (vs the ~26 granular checks pytest
already owns). Email ingestion (ING-3) and the ≤6 no-description cap (SCO-4) are
deliberately **not** here — no browser surface, logic owned by
[test_collectors.py](../../tests/test_collectors.py). Step 6 may trim 2–3 of the
narrower dedup cases if pytest coverage is deemed sufficient.

---

## Epic 4 — Scoring (UI surface only; logic above/pytest)

| ID | Scenario | Layer | Covers | Prep |
|---|---|---|---|---|
| PW-SCO-1 | Click a card's score → popup opens with band badge, rail + threshold mark, verdict, **Covers** (green), **Gaps** (red) | UI | SCO-6.1 | seed scored row |
| PW-SCO-2 | Stack terms in the popup are highlighted by the same highlighter as the description (they never disagree) | UI | SCO-6.2 | seed |
| PW-SCO-3 | The fit band shown equals the band derived from the score (no `AMBER · 0` contradiction) | UI | SCO-1.2 | seed |
| PW-SCO-4 | No API key configured → the score/cover affordance stays visible but explains a key is needed in Profile | UI | SCO-8.1 | no-key config |

---

## Epic 6 — Feed & triage (primary UI)

| ID | Scenario | Layer | Covers | Prep |
|---|---|---|---|---|
| PW-FEED-1 | Seeded DB → one `job-card` per vacancy in the active tab | UI | FEED-1.1 | seed N |
| PW-FEED-2 | Each card shows score, publication date, source; its own mark sits on the shared 0–10 rail; the threshold mark is drawn once | UI | FEED-1.2 | seed |
| PW-FEED-3 | Description expands in place (`<details>`), sanitized, stack terms highlighted and clickable | UI | FEED-1.3 | seed markup |
| PW-FEED-4 | Change status `new → interested` in the UI → the card moves tab and **persists after reload** | E2E | FEED-2.2 | seed |
| PW-FEED-5 | `request`: `POST /status` (valid status, `maxRedirects:0`) → **assert 303 + `Location`**; then `GET /?status=<new>` → **assert the response body now lists the row under the new status** (persistence over the wire) | API | FEED-2.2 | seed |
| PW-FEED-6 | Status tabs `new / interested / applied / skipped` with live counters | UI | FEED-2.1 | seed mixed |
| PW-FEED-7 | `POST /status` with an unknown status or empty hash → **400**, nothing written | API | FEED-2.3 | — |
| PW-FEED-8 | `archived` has no feed tab — an archived row is absent from every tab incl. "all" and its count | E2E | FEED-2.1 | seed archived |
| PW-FEED-9 | Period filter `week / two-weeks / month` keeps only in-window rows | UI | FEED-3.1 | seed dated + clock |
| PW-FEED-10 | Source filter restricts the feed to one source | UI | FEED-4.1 | seed 2 sources |
| PW-FEED-11 | Min-score dropdown drops rows below it; unscored handled explicitly | UI | FEED-4.2 | seed scores |
| PW-FEED-12 | Full-text search matches title / description / location | UI | FEED-4.3 | seed |
| PW-FEED-13 | Sort offers "score: high → low" (default) and "low → high" | UI | FEED-5.1 | seed scores |
| PW-FEED-14 | Unscored rows sink to the bottom in **both** sort directions | UI | FEED-5.2 | seed mixed |
| PW-FEED-15 | The Applied tab orders by `status_at` (recently applied first) | UI | FEED-6.1 | seed applied |
| PW-FEED-16 | The Applied sort dropdown is recently / newest / oldest — **no** score sort | UI | FEED-6.2 | seed |
| PW-FEED-17 | Clicking a tag cycles include → exclude → off | UI | FEED-7.1 | seed tags |
| PW-FEED-18 | Tag matching is word-boundary: `Java` filters out `JavaScript`-only rows | E2E | FEED-7.2 | seed Java/JS |
| PW-FEED-19 | Tag filtering works from cards, `/tags`, and the header autocomplete | UI | FEED-7.3 | seed |
| PW-FEED-20 | Anti-goal terms are omitted from the `/tags` cloud and the feed picker | UI | FEED-8.1 | seed + profile.exclude |
| PW-FEED-21 | A tag's picker count equals what selecting it shows in the current view | E2E | FEED-8.2 | seed within-view |
| PW-FEED-22 | Clicking a company opens `/company` listing all of its vacancies | UI | FEED-9.1 | seed same company |
| PW-FEED-23 | No `jobs.db` → the empty-state page (200) on the feed and every other page | API | FEED-10.1 | no DB |
| PW-FEED-24 | **Combined: source + min-score + search.** source=DOU **and** min-score=7 **and** search="Playwright" → only rows matching all three remain (AND semantics), counters update | UI | FEED-4.1–4.3 | seed mixed |
| PW-FEED-25 | **Combined: period + status tab + include-tag.** week **and** Applied tab **and** tag `Playwright` → the intersection; relaxing any one widens the result predictably | UI | FEED-3.1, FEED-6.1, FEED-7.1 | seed dated+status+tags |
| PW-FEED-26 | **Combined: include-tag AND exclude-tag at once.** include `Python` + exclude `Django` → rows with Python but not Django (include AND-narrows, exclude post-cuts) | E2E | FEED-7.1, FEED-8.2 | seed Python/Django mix |

---

## Empty & first-run states

Before the first scan the tool must look **intentional**, be **understandable**,
and still **work**. Expands the terse PW-FEED-23 into a real first-run experience.

| ID | Scenario | Layer | Covers | Prep |
|---|---|---|---|---|
| PW-EMPTY-1 | No `jobs.db` → `/` renders the empty-state (200) with a plain "no scans yet" message and a visible **Scan** call-to-action — not a blank or broken page | UI | FEED-10.1 | no DB |
| PW-EMPTY-2 | No `jobs.db` → every page (`/runs /tags /stats /calendar /company /profile`) renders a usable empty-state — nav intact, no 500, no half-rendered widget | API | FEED-10.1 | no DB |
| PW-EMPTY-3 | **First-run journey:** empty-state → press **Scan** → run (seam) → the feed populates with the fixture's matches | E2E | FEED-10.1, OPS-1.1 | no DB → fixture + runner seam |
| PW-EMPTY-4 | DB exists but a filter/tab yields **0 rows** → a clear "nothing here" placeholder inside the normal chrome (distinct from the no-DB state); filters stay operable | UI | FEED-10.1 | seed + over-narrow filter |
| PW-EMPTY-5 | No `profile.json` → `/profile` opens in EDIT with an empty, usable form (nothing to save from → EDIT) | UI | PRO-2.3 | no profile |

---

## Epic 7 — Market analytics (UI)

| ID | Scenario | Layer | Covers | Prep |
|---|---|---|---|---|
| PW-ANL-1 | `/runs` renders the arithmetic funnel; a deliberately unbalanced seed is flagged red | UI | ANL-1.1 | seed run journal |
| PW-ANL-2 | `/runs` shows per-feed fetched/dups/filtered/new, dead feeds at 0, L0 reasons in plain language | UI | ANL-2.1 | seed journal |
| PW-ANL-3 | `/stats` renders coverage, table-stakes, differentiators, and leverage gaps from skill-demand × profile | UI | ANL-3.1 | seed + profile |
| PW-ANL-4 | `/stats` shows each figure's sample size and lists what is deliberately *not* shown | UI | ANL-3.2 | seed |
| PW-ANL-5 | `/tags` renders a cloud with per-term counts; a term links into a filtered feed | UI | ANL-4.1 | seed tags |
| PW-ANL-6 | `/calendar` shows new + applied per day with distinct marks | UI | ANL-5.1 | seed dated statuses |
| PW-ANL-7 | Clicking a calendar day number opens that day's list | E2E | ANL-5.1 | seed |
| PW-ANL-8 | Archiving a vacancy removes it from the feed but it **still counts on the calendar** (its `status_at` is unchanged) | E2E | ANL-5.2, HIRE-3.3 | seed applied → archive |
| PW-ANL-9 | Adding an `extra_skill` that is in demand changes `/stats` coverage/gaps — the profile's `owned` set (`skills + extra_skills`) feeds `stats.analyse` | UI | PRO-4.1, ANL-3.1 | seed + profile `extra_skills` |

---

## Epic 8 — Profile builder (UI + E2E)

| ID | Scenario | Layer | Covers | Prep |
|---|---|---|---|---|
| PW-PRO-1 | Paste CV → `preview` highlights recognised skills inline, grouped by the role's groups | UI | PRO-1.1 | cv fixture |
| PW-PRO-2 | `preview` writes nothing to `profile.json` | E2E | PRO-1.2 | cv fixture |
| PW-PRO-3 | Seniority and years are auto-detected from the CV | UI | PRO-1.3 | cv fixture |
| PW-PRO-4 | `save` → 303 → `/profile?saved=1`, page in the VIEW (saved) state | API | PRO-2.1 | — |
| PW-PRO-5 | `save_scan` → saves and triggers a run → 303 → `/` | E2E | PRO-2.2 | runner seam |
| PW-PRO-6 | Empty profile opens EDIT; `?edit=1` forces EDIT; otherwise VIEW | UI | PRO-2.3 | with/without profile |
| PW-PRO-7 | A skill not present in the CV is dropped on save; stale ones removed | E2E | PRO-3.1 | cv fixture |
| PW-PRO-8 | A synonym maps to canonical; a CV skill unknown to the dictionary still survives | E2E | PRO-3.2 | cv fixture |
| PW-PRO-9 | An extra (non-CV) skill is saved and **not** validated against the CV | E2E | PRO-4.1 | — |
| PW-PRO-10 | An extra skill already confirmed from the CV is deduped away | E2E | PRO-4.1 | cv fixture |
| PW-PRO-11 | A `stack` term adds a deep search feed used on the next run | E2E | PRO-5.1 | runner seam |
| PW-PRO-12 | An `exclude` term drives L0 title-exclusion, tag muting, and stats muting together | E2E | PRO-5.2 | seed + run |
| PW-PRO-13 | `notes` (boundaries) are saved and reach the scorer input | E2E | PRO-5.3 | mock scorer capture |
| PW-PRO-14 | Role selection is constrained to known roles; an unknown value falls back to default | UI | PRO-6.1 | — |
| PW-PRO-15 | `request`: `POST /profile` with LLM key/model/provider → **assert 303**; `GET /profile?edit=1` → **assert the response echoes the saved model/provider and masks the key** (round-trip over the wire) | API | PRO-7.1 | — |
| PW-PRO-16 | A skill toggled off in preview is excluded from the saved profile | E2E | PRO-3.1 | cv fixture |

---

## Epic 9 — Application tracker & cover letters (UI + API)

| ID | Scenario | Layer | Covers | Prep |
|---|---|---|---|---|
| PW-HIRE-1 | An Applied-tab pipeline card moves `waiting_hr → pre_screen → tech_interview → finish` | E2E | HIRE-1.1 | seed applied |
| PW-HIRE-2 | The note shown for the current stage is saved before moving (never lost on switch) | E2E | HIRE-2.1 | seed |
| PW-HIRE-3 | Notes are stored per stage — each stage keeps its own text | E2E | HIRE-2.2 | seed |
| PW-HIRE-4 | "Finish & archive" sets `status=archived`; the card leaves the feed and its "all" count | E2E | HIRE-3.1 | seed applied |
| PW-HIRE-5 | "Restore to Applied" sets `status=applied` | E2E | HIRE-3.2 | seed archived |
| PW-HIRE-6 | `request`: `GET /calendar` → note the applied day; `POST /hiring/update` archive then restore; `GET /calendar` again → **assert the applied day in the response is unchanged** (`status_at` untouched) while `status` did change | API | HIRE-3.3 | seed applied |
| PW-HIRE-7 | ✍ generate (mock LLM) → modal fills with evaluation + letter + traceability | E2E | HIRE-4.1 | career-facts fixture + mock LLM |
| PW-HIRE-8 | The fit band pill equals the band derived from the fit score | UI | HIRE-4.2 | mock LLM |
| PW-HIRE-9 | ✍ on an `interested` feed card opens the same modal; evaluation/traceability render as Markdown | E2E | HIRE-4.3 | mock LLM |
| PW-HIRE-10 | The generated letter is cached in `cover_data`; a second view returns the cache (no regeneration) | E2E | HIRE-5.1 | mock LLM call-count |
| PW-HIRE-11 | `regenerate=1` forces a fresh generation, overwriting the cache | API | HIRE-5.2 | mock LLM |
| PW-HIRE-12 | Missing `career-facts.md` → `{ok:false, error}` popup with HTTP 200, naming the file | API | HIRE-6.1 | no facts |
| PW-HIRE-13 | Missing API key → popup pointing to Profile → LLM access | API | HIRE-6.2 | no key |
| PW-HIRE-14 | A generation failure (mock throws) becomes popup text, never a 500 | API | HIRE-6.3 | mock LLM throws |
| PW-HIRE-15 | `POST /hiring/cover` with no DB → 404 JSON `{ok:false}` | API | (contract) | no DB |
| PW-HIRE-16 | The Applied tab links to the hiring pipeline | UI | HIRE-4.3 | seed applied |

---

## Epic 10 — Operations (OPS-1 only)

| ID | Scenario | Layer | Covers | Prep |
|---|---|---|---|---|
| PW-OPS-1 | Click **Scan** → 303 back to the same page → the header shows "scanning" | E2E | OPS-1.1 | slow runner seam |
| PW-OPS-2 | `POST /run` → 303 (`started`) | API | OPS-1.1 | runner |
| PW-OPS-3 | A second press during an active (slow-mock) run → `busy`, no second process | E2E | OPS-1.2 | slow runner seam |
| PW-OPS-4 | Runner not wired to the server → `POST /run` → 503 | API | OPS-1.4 | no runner |

---

## Cross-cutting UI

| ID | Scenario | Layer | Covers | Prep |
|---|---|---|---|---|
| PW-UI-1 | **Tooltip sweep.** Seed DB + profile (edit mode) so `/stats` and `/profile` render every `?`; collect **all** `span.q[data-tip]`, assert each has non-empty `data-tip` and reveals on focus/hover — one test, API-prep + multi-surface UI sweep; auto-covers new tooltips (a hint added without text → fail) | E2E | — (UX completeness) | seed DB + profile, `?edit=1` |

---

## API / contract — the base the pyramid is missing

Black-box HTTP contract against the **live server** (`request`) — the cheap, wide
base a UI/E2E-heavy suite lacks. This **deliberately reintroduces the basic status
contract** (SEC-3.1 / SEC-3.3 / SEC-6.1) that Epic 11 parked in pytest. The auth
*internals* — token channels, localhost rule, security headers, resource whitelist
(SEC-1/2/4/5) — stay in pytest; only the over-the-wire status/redirect surface
comes here, because that is exactly the missing base. Not a duplicate of
`test_web.py` (in-process): this exercises the running server.

| ID | Scenario | Layer | Covers | Prep |
|---|---|---|---|---|
| PW-API-1 | `/health` → 200, body `<p>ok</p>` (liveness smoke) | API | SEC-3.1 | — |
| PW-API-2 | An unknown path → 404 "Not Found" | API | SEC-3.3 | — |
| PW-API-3 | A known path with the wrong method (`GET /status`, `POST /health`) → 405 | API | SEC-3.3 | — |
| PW-API-4 | The 303 + `Location` redirect contract on `POST /status`, `/run`, `/profile`, `/hiring/update` (observed with `maxRedirects:0`) | API | SEC-6.1 | seed/runner |

**API rows already scattered in the plan** (the contract layer also owns these):
PW-FEED-5/7 (`/status` write + 400), PW-OPS-2/4 (`/run` 303/503), PW-HIRE-11–15
(`/hiring/cover` JSON + 404), PW-PRO-4/15 (`/profile` 303 + save), PW-EMPTY-2
(empty-state sweep).

---

## Catalog totals (before the rebalance)

| Epic / section | UI | API | E2E | Total |
|---|---:|---:|---:|---:|
| 1–4 pipeline substrate | 0 | 0 | 8 | 8 |
| 4 scoring UI | 4 | 0 | 0 | 4 |
| 6 feed & triage | 19 | 3 | 4 | 26 |
| Empty & first-run | 3 | 1 | 1 | 5 |
| 7 analytics | 7 | 0 | 2 | 9 |
| 8 profile | 4 | 2 | 10 | 16 |
| 9 hiring & cover | 3 | 7 | 6 | 16 |
| 10 ops | 0 | 2 | 2 | 4 |
| Cross-cutting UI | 0 | 0 | 1 | 1 |
| API / contract | 0 | 4 | 0 | 4 |
| **Total** | **40** | **19** | **34** | **93** |

Current shape: **UI 43% · API 20% · E2E 37%**.

**This inverted shape is the point — not an accident.** A thin API middle under a
heavy UI+E2E top is exactly the as-is problem on the target project; the catalog
**reproduces it visibly** so the fix is measurable. The base of a real pyramid is
API/contract, and here it is still under-built.

**The fix — a measurable before → after** (detailed in *Prioritisation & rebalance* below):
- Convert run-triggering E2E that don't need a browser into **API prep + a cheap
  read-back** (much of Epic 8 profile, some hiring) — weight moves E2E → API.
- Grow the **API / contract** layer above (status, redirects, error contracts) —
  the missing base.
- Keep the pipeline flagships and genuine UI journeys as the few, high-value E2E.
- Target shape: a **wide API base, a solid UI middle, a thin E2E cap**.

### Where the API steps live inside the UI/E2E tests

*Can we map this before a single test exists?* **Directionally yes; precisely
not yet.** The `Prep` column already declares each test's setup, so the API/CLI/
seed footprint is visible now — but the exact endpoints and call counts per test
firm up only with the **seeding contract** (see [test-data.md](test-data.md)): whether setup is a test-only
HTTP seed endpoint, a CLI `run` over fixtures, or a direct DB insert.

What `Prep` already tells us — API/seed steps that are **preparation, not the
test's layer**:

| Prep kind | Weight | Rows |
|---|---|---|
| **Pipeline-triggering** (`run`/runner seam over a fixture) — heaviest API/CLI setup | high | all 8 `PW-PIPE-*`, `PW-EMPTY-3`, `PW-OPS-1/3`, `PW-PRO-5/11/12` |
| **DB seed** (rows/profile inserted before the page loads) | medium | most UI rows tagged `seed …` |
| **Mock scorer / mock LLM** | medium | `PW-PIPE-1/8/9`, `PW-SCO-*`, `PW-HIRE-7–14` |
| **Frozen clock** | low | `PW-FEED-9`, `PW-PIPE-3` |

Every one of those is scaffolding for a **UI/journey assertion** — which is why
they count as UI or E2E, not API. A row lands in the **API** column *only* where
the assertion is on the raw response (`request`, no browser). **"Uses an API
call" ≠ "is an API test"** — that confusion is exactly the anti-pattern this
catalog is built to expose and then correct.

## Prioritisation & rebalance

The catalog above over-tagged **E2E** because many rows *touch* a save/run. Applying
the strict rule — **a test's layer = the layer of its assertion** — the run-free
"do X, then read the response/data back" rows are **API**, not E2E. Reclassifying
them is the whole "fix the pyramid" move.

**What moves E2E → API** (assertion is on a response/data round-trip, no browser):
- Profile round-trips: `PRO-2` (preview no-write), `PRO-7` (CV validation),
  `PRO-8` (synonym→canonical), `PRO-9/10` (extra skills), `PRO-13` (notes reach
  the scorer, via the stub's captured input).
- Hiring data: `HIRE-2` (per-stage notes), `HIRE-10` (cache hit), `HIRE-11`
  (regenerate) — join the JSON-contract rows already API (`HIRE-6/12/13/14/15`).

**What moves E2E → UI** (rendered-page assertion, no run): `FEED-8` (archived
hidden), `FEED-18` (word boundary), `FEED-26` (combined tags), `ANL-7` (day
drill), `ANL-8` (archive on calendar).

**What stays E2E** (genuine multi-step journey through a `run` or irreducible UI
flow): the 8 pipeline flagships, `EMPTY-3` (first-run), `OPS-1/3` (Scan button),
`PRO-5` (save & scan), `PRO-11/12` (stack/exclude surfacing after a scan),
`FEED-4` (status persists across nav), `FEED-21` (picker vs feed), `HIRE-1/3`
(stage journey / archive flow), `HIRE-4/7/9` (cover-letter modal generation).

| Shape | API | UI | E2E | Total |
|---|---:|---:|---:|---:|
| **Existing suite (as-is)** | 15 (33%) | 30 (67%) | 0 | 45 |
| **This catalog (the reproduced problem)** | 19 (20%) | 40 (43%) | 34 (37%) | 93 |
| **Rebalanced target** | **≈33 (33%)** | **≈46 (45%)** | **≈23 (22%)** | **≈102** |

The move that matters: **E2E cap 36% → 22%, API base 21% → 33%** — same behaviours
covered, weight shifted to the cheap, deterministic layer. That is the artefact to
show: *a UI/e2e-tilted plan, then the disciplined re-classification that rights the
pyramid.*

---

## The harness — the single biggest unlock

Nothing today drives the pipeline (scorer `enabled:false`, no source fixture, no
`run` trigger, no clock freeze). One harness build unlocks ~20 rows at once.

### Scoring harness — deliberately **two tiers**

Most scoring tests do **not** need an LLM. Split by what is under test:

**Tier A — seeded scores (no LLM, no run).** For everything that only *displays or
filters* a score: seed `score / band / verdict / matched / gaps` straight into the
row (`seed.py` already seeds scores 6.5–8.7; extend it with verdict/covers/gaps).
- Unlocks: `SCO-1/2/3` (score popup), `SCO-4` (no-key affordance, via config with
  no key), `FEED-2` (rail + threshold mark), and the already-passing min-score /
  sort rows. **Cheap — do first (Wave 1).**

**Tier B — stub LLM over the wire (behaviour).** For scoring *wiring* and the
*no-rescore* invariant, where a real scoring call must happen deterministically.
The product already speaks OpenAI-compatible (`provider=openai` + `base_url`), so
add a **local stub LLM server** that answers `/chat/completions` with deterministic
JSON keyed off the vacancy (a marker in the description → a fixed
score/verdict/covers/gaps). Config: `scorer.enabled:true, provider:openai,
base_url:<stub>, api_key:test`.
- Unlocks: `PIPE-1` (fresh scan → scored card), `PIPE-9` (no-rescore: stub returns
  a *different* value on the 2nd run, the card keeps the first).
- **The same stub answers cover-letter generation** → unlocks the whole `HIRE`
  cover block with one server.

### The rest of the harness

| Piece | What | Unlocks |
|---|---|---|
| **H1 — stub source server** | serves canned DOU/Djinni RSS at the configured feed URLs (run without a profile so feeds come from `config.sources`); IMAP stays off | all `PIPE-*` ingestion/dedup/L0 |
| **H2 — stub LLM server** | Tier-B above (scoring **and** cover letters) | `PIPE-1/9`, `HIRE-4/7/9/10/11` |
| **H3 — run trigger + wait** | drive `POST /run` (the real button) and poll status/feed until done | `OPS-1/2/3`, every `run`-based E2E |
| **H4 — seed scenarios** | helpers on `seed.py`: scored+verdict rows, `archived`, aged >180d, `runs`-journal rows, `profile.exclude`, hiring stages, `cover_data` | `FEED-8/20/21`, `ANL-1/2/8`, `HIRE-*` |
| **H5 — time (optional)** | server clock can't be frozen from e2e; use **seeded relative dates** (3d/10d/40d ago) for period/TTL instead | `FEED-9`, `PIPE-3` |

H3 doubles as the OPS-1 test itself — triggering a run *is* the Scan-button
scenario. Reuse, don't build twice.

---

## Prioritised waves

Ordered by **value ÷ cost**: cheap deterministic base first, expensive journeys last.

### Wave 0 — Harness (enabler, 0 tests)
Build H1–H5 + the Tier-A/Tier-B scoring seams. Blocks Waves 2–3; unblocks ~30 rows.
**Do this first** — without it a third of the plan is un-writable.

### Wave 1 — Seed-only + contract (~35 tests, no run needed) — highest ROI
The wide API/UI base. No pipeline, all deterministic from a seeded DB.
- **API / contract:** `API-4` (303 redirect), `FEED-5` (303 + persistence),
  `EMPTY-2` (no-DB sweep).
- **Empty / first-run (no DB):** `EMPTY-1`, `FEED-23`.
- **Scoring display (Tier A seed):** `SCO-1/2/3/4`, `FEED-2`.
- **Feed depth (seed):** `FEED-3/6/8/9/13/14/15/16/17/19/24/25/26`.
- **Tag muting (seed `exclude`):** `FEED-20/21`.
- **Analytics (seed journal/profile):** `ANL-1/2/3/4/7/8`.
- **Profile (form + API round-trip):** `PRO-2/3/4/6/7/8/9/10/13/14/15/16`.

### Wave 2 — Pipeline + ops (~14 tests) — needs H1+H2+H3
The few, high-value E2E flagships — the show-case.
- **Pipeline flagships:** `PIPE-1…10` (dedup, TTL, cap, L0, no-rescore surfaced).
- **Ops:** `OPS-1/2/3/4` (Scan button, busy, 503).
- **Run journeys:** `EMPTY-3` (first-run), `PRO-5` (save & scan), `PRO-11`
  (stack→feed), `PRO-12` (exclude→feed).

### Wave 3 — Hiring & cover letters (~16 tests) — needs H4 + H2 stub LLM
A whole shipped feature area currently at **zero** e2e coverage.
- **Tracker:** `HIRE-1/2/3` (stages, per-stage notes, archive/restore), `HIRE-6`
  (`status_at` integrity).
- **Cover letters:** `HIRE-4/7/8/9` (generate, band, feed-card ✍, Markdown),
  `HIRE-10/11` (cache, regenerate), `HIRE-12/13/14/15` (graceful-degrade JSON),
  `HIRE-16` (Applied→hiring link).

### Added to the catalog (were pending)
- **`PW-UI-1`** — tooltip sweep (complex-e2e, API-prep + UI sweep). → Wave 2.
- **`PW-ANL-9`** — `extra_skills` change `/stats` coverage (seed-only). → Wave 1.

---

## Existing suite — keep / upgrade / note

- **Keep as-is:** `company` (3), `calendar` (3), `tags` (3), `filters` (6 —
  extend with the missing period + 3-way combined), `feed` (2), `stats` (3 —
  extend to coverage/gaps), `health` (8, incl. the auth 403/200 smoke).
- **Upgrade (partial → full):** `FEED-2/6/17/19/24`, `EMPTY-4`, `ANL-3`,
  `PRO-4/6/13`.
- **Redundancy with pytest (flag, don't cut):** `health.spec` status codes and
  `pages.spec` 200-smokes overlap `test_web.py` (in-process). Playwright asserts
  the same contract **over the wire** — a defensible second layer; the clearest
  trim candidate only if cost ever bites.
- **No renumbering / no deletion of green tests** — the plan only adds and upgrades.

---

## Definition of done

- ~100 Playwright tests; shape ≈ **API 33% · UI 45% · E2E 22%** (wide base, solid
  middle, thin cap).
- Every catalog row `covered` or consciously deferred with a reason.
- Harness: stub source + stub LLM (scoring **and** cover) + run trigger + seed
  scenarios, all deterministic and offline.
- Traceability intact: each test cites its requirement AC; each requirement AC in
  scope maps to ≥1 test or a named deferral.
