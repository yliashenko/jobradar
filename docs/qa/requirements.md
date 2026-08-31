# jobradar — Requirements (reconstructed PRD)

> **What this is.** A requirements specification for jobradar, written *as if it
> preceded the product* — epics → user stories → acceptance criteria. It is
> reverse-engineered from the shipped behaviour, the ADRs, and the merged PR
> history of the project's earlier iteration (PRs #1–#16). Each story carries a
> `Trace:` line back to the PR(s) that realised it, so the reconstruction stays
> honest rather than pretending to be a genuine up-front spec.
>
> **Why it exists.** The current test suite was written *bottom-up* — looking at
> the code that already existed. This document flips the axis: it states what the
> product is *supposed to do*, so tests can be planned against **requirements**,
> not against the implementation that happens to be there. It is the input to
> `test-plan.md` (the coverage & build plan) and `test-data.md` (the seeding plan).
>
> **How to read the IDs.** Every acceptance criterion is numbered
> (`ING-1.2` = epic Ingestion, story 1, criterion 2). Those IDs are the atoms the
> test catalog maps onto — one criterion may become one unit test, or one step in
> an e2e scenario, or nothing yet (a coverage gap). Traceability runs
> requirement → test, both ways.

Status: draft v1 (2026-08-31). Scope: the product **as built** (personal Stage-A
tool). The frozen SaaS vision in [../PRODUCT.md](../PRODUCT.md) is explicitly
**out of scope** — these requirements describe what exists, not Phase 2+.

---

## The product in one line

```
sources → dedup → cheap L0 filter → LLM scoring against the profile → Telegram → web triage
```

jobradar replaces the daily habit of checking three job boards. Its single point
of value is **honest scoring against a real profile with explicit boundaries** —
filtering out what looks right by title but isn't by substance. It is **not** a
mass-apply system and **not** a CRM.

## Epic map

| # | Epic | What it guarantees | Trace (PRs) |
|---|------|--------------------|-------------|
| 1 | **Ingestion** | Vacancies arrive from real UA sources without scraping | #1, #15 |
| 2 | **Deduplication & lifecycle** | Each vacancy is seen once; reopened ones return | #1 |
| 3 | **L0 pre-filter** | Cheap deterministic gate before any paid LLM call | #1 |
| 4 | **LLM scoring** | An honest 0–10 verdict against the profile | #1, #9, #14, #15 |
| 5 | **Notifications & liveness** | Worthwhile matches reach Telegram; silence is caught | #1 |
| 6 | **Feed & triage** | The collected set can be read and triaged in a browser | #1, #9, #13, #15, #16 |
| 7 | **Market analytics** | Honest, auditable numbers about the run and the market | #1 |
| 8 | **Profile builder** | The candidate profile is data, editable in the UI | #1, #14, #16 |
| 9 | **Application tracker & cover letters** | Applied vacancies move through stages; AI drafts a letter | #13, #14, #15 |
| 10 | **Operations & control** | The scan can be triggered and observed safely | #1 |
| 11 | **Access control & web contract** | The history is private; the HTTP surface is well-defined | #1, #5 |

**Invariant tags.** Criteria marked `[INV]` encode a deliberate trade-off from
CLAUDE.md §4 — a test on them is a *regression guard on a decision*, and the
decision must not be "fixed" silently.

---

## Epic 1 — Ingestion

*Collect vacancies from real UA sources. Boards are never scraped: DOU is
official RSS, Djinni is official RSS, LinkedIn/Djinni email alerts arrive over
IMAP (BYOA).* `[INV]`

### ING-1 — Collect from DOU RSS as broad role slices
> As a candidate, I want the radar to pull DOU vacancies by **role/experience/
> format** slices (not tech keywords), so that DOU's 25-item-per-feed cap covers
> the market rather than one narrow query. **Trace:** #1

- **ING-1.1** A DOU RSS fixture with N items yields N vacancies with
  `title, company, url, published_at, description` populated.
- **ING-1.2** Feeds are role-derived (`category=QA`, `exp=…`, `remote`), not
  keyword queries. `[INV]` (broad-slice design beats the 25-cap)
- **ING-1.3** A malformed / empty feed yields 0 vacancies and does not abort the run.

### ING-2 — Collect from Djinni RSS (both QA categories)
> As a candidate, I want Djinni polled over its **official RSS** for both `QA`
> and `Automation QA` primary keywords, so that automation roles not cross-posted
> to DOU are not silently missed. **Trace:** #1, #15

- **ING-2.1** A Djinni RSS fixture parses `company / title / link / description`.
- **ING-2.2** Both `QA` and `Automation QA` categories are polled (regression on
  the #15 miss where only `QA` was fetched).
- **ING-2.3** Djinni carries no company in the title → dedup falls back to the
  stable job URL. `[INV]` (accepted DOU+Djinni double-show)

### ING-3 — Collect from email alerts (Djinni / LinkedIn) over IMAP
> As a candidate, I want to forward my own board alerts to one IMAP folder and
> have vacancies extracted from them, so that LinkedIn (never scrapable) still
> reaches the radar. **Trace:** #1
>
> **Playwright scope: OUT.** Pytest base
> ([test_collectors.py](../../tests/test_collectors.py)). Email/IMAP has no
> browser surface; a fixture-sourced vacancy landing in the feed is already
> covered source-agnostically by PW-PIPE-1.

- **ING-3.1** A sanitized Djinni `.eml` yields the expected set of vacancies.
- **ING-3.2** A sanitized LinkedIn `.eml` yields vacancies **without a
  description**.
- **ING-3.3** A layout the regex no longer matches yields 0 vacancies (and is
  caught by the heartbeat, not by a crash). `[INV]` (silent-failure surface)

### ING-4 — Normalise feed content
> As the pipeline, I want feed HTML sanitised and dates parsed to a canonical
> form, so downstream steps see clean text and comparable timestamps. **Trace:** #1

- **ING-4.1** `sanitize_html` strips markup/scripts, leaving readable text.
- **ING-4.2** `parse_feed_date` populates `published_at` for each supported feed
  date format; an unparseable date degrades to a defined fallback, not a crash.

### ING-5 — Every run is auditable
> As an operator, I want each run journalled per feed, so I can later reconstruct
> what was fetched, deduped, filtered, and added. **Trace:** #1

- **ING-5.1** A run records per-feed fetched counts (including dead feeds at 0).
- **ING-5.2** The journal is what `/runs` renders (see ANL-1/ANL-2).

### ING-6 — Surface the DOU 25-item cap
> As an operator, I want a feed that hit DOU's 25-item ceiling flagged, because a
> capped feed is the only way the radar can *silently* drop rows. **Trace:** #1

- **ING-6.1** A DOU feed with ≥25 items is flagged as "capped" on `/runs`, with
  the feed's time-window in hours. `[INV]` (must not be hidden)

---

## Epic 2 — Deduplication & lifecycle

*A vacancy already seen costs no L0, no scoring, no tokens. Dedup is permanent
(TTL-bounded), biased to over-show rather than ever miss.* `[INV]`

### DED-1 — Deduplicate by normalised company|title
> As a candidate, I don't want the same vacancy twice, so identical
> company+title collapses to one record. **Trace:** #1

- **DED-1.1** Key = `sha256(normalized_company | normalized_title)`. `[INV]`
- **DED-1.2** Two runs over the same fixture → the second adds 0 new.
- **DED-1.3** Company+title differing only in case/whitespace → the same hash.
- **DED-1.4** Digits in the title are **not** stripped (a renamed/renumbered
  role may double-show; accepted). `[INV]`

### DED-2 — Merge the same vacancy across sources
> As a candidate, I want a vacancy that appears on both DOU and Djinni shown once
> where it can be identified. **Trace:** #1

- **DED-2.1** The same company+title from DOU and Djinni merges into one record,
  recording both source links.

### DED-3 — Re-surface reopened vacancies after the TTL
> As a candidate, I want a role reopened after ~6 months to come back fresh,
> because both it and I have changed. **Trace:** #1

- **DED-3.1** `dedup_ttl_days = 180`. A vacancy last seen >180d ago goes through
  the full path again and is notified. `[INV]`
- **DED-3.2** Its status resets to `new` even if previously `skipped`. `[INV]`
- **DED-3.3** The log records a "Reopened vacancy (last seen …)" line.

---

## Epic 3 — L0 pre-filter

*A free, deterministic gate (regex + salary band) that runs before the paid LLM.
L0 changes never apply retroactively.* `[INV]`

### L0-1 — Salary-band gate
> As a candidate, I want vacancies below my floor dropped cheaply. **Trace:** #1

- **L0-1.1** A vacancy with a parseable salary ≥ `min_salary_usd` passes L0.
- **L0-1.2** A vacancy below the floor is rejected with a salary reason.
- **L0-1.3** A vacancy with **no** salary is not dropped on salary grounds
  (absence ≠ below floor).

### L0-2 — Role-keyword gate
> As a candidate, I want only on-role text to pass. **Trace:** #1

- **L0-2.1** Text matching `require_any_text` (QA/SDET/Automation…) passes L0.
- **L0-2.2** Text matching none of the required terms is rejected with a
  keyword reason.

### L0-3 — Title-only exclusion
> As a candidate, I want off-target roles cut by **title**, but never by body,
> so a duty mentioned in a good role's description doesn't disqualify it.
> **Trace:** #1

- **L0-3.1** Role-level exclusion (e.g. Junior) cuts by title.
- **L0-3.2** Profile anti-goals ("not for me") cut by title, word-boundary
  (`Manual Testing Engineer` title cut; "manual testing" in an automation body
  survives). `[INV]`

### L0-4 — Attribute every rejection
> As an operator tuning L0, I want to see exactly which rule dropped each row.
> **Trace:** #1

- **L0-4.1** Each L0-rejected row carries a plain-language `l0_reason`.
- **L0-4.2** `/runs` and `jobradar stats` group rejections by reason.

### L0-5 — L0 is not retroactive
> As an operator, I want L0 changes to affect only new rows, so history stays
> comparable. **Trace:** #1

- **L0-5.1** Re-running after loosening/tightening L0 does not re-classify
  already-stored rows. `[INV]`

---

## Epic 4 — LLM scoring

*The honest mirror: a 0–10 verdict of the vacancy against the profile, calibrated
to say GAP not PARTIAL. Scores are never recomputed.* `[INV]`

### SCO-1 — Score L0-passers against the profile
> As a candidate, I want each L0-passing vacancy scored 0–10 with a verdict and
> covers/gaps, so I can triage by substance. **Trace:** #1, #9

- **SCO-1.1** A passed vacancy gets `score`, `band`, `verdict`, `covers[]`,
  `gaps[]`.
- **SCO-1.2** The band is derived from the score (no contradictory
  `band vs score`). **Trace:** #15
- **SCO-1.3** The scorer receives the profile's CV + confirmed skills +
  seniority **and** the boundaries block (candidate.scorer_text).

### SCO-2 — Honest boundaries drive the verdict
> As a candidate, I want my "boundaries that must not blur" treated as GAP, so
> the score doesn't flatter me. **Trace:** #1

- **SCO-2.1** With the boundaries block present, a vacancy that trips a boundary
  scores materially lower than the same vacancy scored without it. `[INV]`
- **SCO-2.2** The flat skill list feeds the *filter*; the boundaries text feeds
  the *scorer* — the two roles never merge. `[INV]`

### SCO-3 — Never recompute a score
> As an operator, I want a scored vacancy to keep its score forever (LLMs drift).
> **Trace:** #1

- **SCO-3.1** Re-running over an already-scored vacancy leaves score/verdict
  untouched. `[INV]`
- **SCO-3.2** A score carries the `RUBRIC_VERSION` it was made under; changing
  the rubric bumps the version and does not touch old rows. `[INV]`

### SCO-4 — Cap description-less sources
> As a candidate, I don't want a blind score inflated. **Trace:** #1
>
> **Playwright scope: OUT.** The ≤6 cap is a scorer-prompt behaviour — no
> deterministic assertion with a mock scorer, no UI surface. Pytest owns it.

- **SCO-4.1** A LinkedIn vacancy (no description) is scored no higher than 6. `[INV]`

### SCO-5 — Threshold gates notification
> As a candidate, I only want Telegram for real matches. **Trace:** #1
>
> **Playwright scope: OUT.** Notification gating is Telegram distribution
> (pytest base). The feed shows every stored row regardless of threshold, so
> there is nothing threshold-specific to assert in the UI.

- **SCO-5.1** Score ≥ `notify_min_score` → a notification is formed.
- **SCO-5.2** Score < threshold → no notification (row still stored).

### SCO-6 — Score-details popup
> As a candidate, I want to click a card's score and see the full breakdown.
> **Trace:** #9

- **SCO-6.1** Clicking the score opens a modal with band badge, rail+threshold
  mark, verdict, Covers (green), Gaps (red).
- **SCO-6.2** Stack terms in the popup use the same highlighter as the
  description — the two never disagree on what a skill is.

### SCO-7 — Pluggable LLM provider
> As a new owner of a handed-off copy, I want the tool to run on **my** account
> and provider. **Trace:** #14

- **SCO-7.1** Provider defaults to Anthropic; `provider=openai` (+ `base_url`)
  routes to any OpenAI-compatible endpoint (gateway / local Ollama).
- **SCO-7.2** Key + provider precedence is **Profile → config → env**
  (`llm_settings`).

### SCO-8 — Degrade gracefully without a key
> As a first-week user, I want the pipeline usable before I pay for scoring.
> **Trace:** #1, #14

- **SCO-8.1** With `scorer.enabled=false` or no key, the pipeline passes
  everything that cleared L0 (no score), and the UI explains a key is needed.

---

## Epic 5 — Notifications & liveness

*Telegram is the "something worth a look arrived" signal. Silent failure is the
top risk — the heartbeat guards it.* `[INV]`

> **Playwright scope: OUT.** This whole epic stays in the pytest base
> ([test_notify.py](../../tests/test_notify.py)). Telegram distribution has no
> browser surface, so it is not re-planned as e2e/API.

### NOT-1 — Notify worthwhile matches
> As a candidate, I want a Telegram message per new vacancy at/above threshold.
> **Trace:** #1

- **NOT-1.1** A new, L0-passing, ≥threshold vacancy produces one Telegram send
  with title/company/score/link.
- **NOT-1.2** An already-notified vacancy is not re-sent.

### NOT-2 — 24-hour heartbeat
> As an operator, I want to be told when the market goes silent, because a broken
> parser looks exactly like an empty market. **Trace:** #1

- **NOT-2.1** No new record within `heartbeat_alert_hours` (24) → one Telegram
  "silence for 24h" message. `[INV]` (do not remove)
- **NOT-2.2** The heartbeat does not re-fire every run while still silent
  (`last_heartbeat_alert` throttle).

### NOT-3 — dry-run sends nothing
> As an operator, I want a full run that sends nothing, for tuning. **Trace:** #1

- **NOT-3.1** `run --dry-run` performs the full pipeline but issues zero Telegram
  sends (prints instead).

---

## Epic 6 — Feed & triage

*The web UI is where triage happens; it reads the same `jobs.db` as the CLI.*

### FEED-1 — Read the collected set on a shared scale
> As a candidate, I want the feed as cards on one 0–10 rail with a threshold
> mark, so the list reads as a distribution. **Trace:** #1, #9, #13

- **FEED-1.1** A seeded DB renders one card per vacancy in the active tab.
- **FEED-1.2** Each card shows score, publication date, source, and its own mark
  on the shared rail; the threshold mark is drawn once.
- **FEED-1.3** The description expands in place (`<details>`), sanitised, with
  stack terms highlighted and clickable.

### FEED-2 — Triage a vacancy
> As a candidate, I want to set a status in one click and have it stick.
> **Trace:** #1, #15

- **FEED-2.1** Status tabs are `new / interested / applied / skipped` with live
  counters. (`archived` has no feed tab — it lives on `/hiring`.)
- **FEED-2.2** `POST /status` writes `status` + `status_at`; the change survives
  a reload (UI+DB end-to-end).
- **FEED-2.3** An unknown status or empty hash → 400, nothing written.

### FEED-3 — Filter by recency
> As a candidate, I want week / two-weeks / month windows. **Trace:** #1, #16

- **FEED-3.1** Each period keeps only vacancies within it; the 14-day option sits
  between week and month.

### FEED-4 — Filter by source, score, and text
> As a candidate, I want to narrow the feed. **Trace:** #1, #14

- **FEED-4.1** Source filter restricts to one source.
- **FEED-4.2** Min-score (1–10) drops rows below it; unscored handled explicitly.
- **FEED-4.3** Full-text search matches title/description/location.

### FEED-5 — Sort the feed by fit
> As a candidate, I want best-fit first. **Trace:** #13

- **FEED-5.1** Sort offers "score: high → low" (default) and "low → high".
- **FEED-5.2** Unscored rows sink to the bottom in **both** directions.

### FEED-6 — Applied tab is a to-do list
> As a candidate, I want my applications ordered by *when I applied*, not by fit.
> **Trace:** #16

- **FEED-6.1** The Applied tab orders by `status_at` (recently applied first).
- **FEED-6.2** Its sort dropdown is recently-applied / newest / oldest — **no**
  score sort.

### FEED-7 — Three-state tag filtering
> As a candidate, I want to include, then exclude, then clear a tag (Apple-Notes
> style), by word boundary. **Trace:** #1

- **FEED-7.1** Clicking a tag cycles include → exclude → off.
- **FEED-7.2** Matching is word-boundary: `Java` ≠ `JavaScript`. `[INV]`
- **FEED-7.3** Tag filtering is available on cards, `/tags`, and the header
  autocomplete (role-scoped).

### FEED-8 — Anti-goals are muted from tag surfaces
> As a candidate, I don't want "not for me" skills offered or counted.
> **Trace:** #16

- **FEED-8.1** Excluded terms are omitted from the `/tags` cloud and the feed tag
  picker entirely.
- **FEED-8.2** The picker counts **within the current view** (status/source/
  search/company/days, title-muted rows cut) so a tag's count equals what
  selecting it shows. `[INV]` (fixes the "picker 34 / feed 21" mismatch)

### FEED-9 — Company page
> As a candidate, I want every vacancy from one company on one page. **Trace:** #1

- **FEED-9.1** Clicking a company opens `/company` listing all its vacancies.

### FEED-10 — Empty state before the first scan
> As a first-run user, I want a sensible page with no DB yet. **Trace:** #1

- **FEED-10.1** With no `jobs.db`, every page returns the empty-state (200), not
  an error. `[INV]` (empty market ≠ broken)

---

## Epic 7 — Market analytics

*Honest, auditable numbers — every figure shows its sample size and never
extrapolates from thin data.* `[INV]`

### ANL-1 — The run funnel reconciles
> As an operator, I want `fetched = duplicates + filtered + new` to add up.
> **Trace:** #1

- **ANL-1.1** `/runs` shows the arithmetic funnel; a mismatch is flagged red. `[INV]`

### ANL-2 — Per-feed breakdown
> As an operator tuning the radar, I want each feed's contribution and the cap.
> **Trace:** #1

- **ANL-2.1** `/runs` lists per-feed fetched/dups/filtered/new, dead feeds at 0,
  the DOU cap marker (ING-6), and L0 reasons in plain language.

### ANL-3 — Market-positioning stats
> As a candidate, I want to see where my profile stands against skill demand.
> **Trace:** #1

- **ANL-3.1** `/stats` shows coverage, table-stakes, differentiators, and
  leverage gaps (skill demand × profile).
- **ANL-3.2** Each figure shows its sample size; salary/scoring/trends are
  explicitly listed as *not shown*, so it never fakes precision. `[INV]`

### ANL-4 — Tag cloud
> As a candidate, I want the market's skill frequencies. **Trace:** #1

- **ANL-4.1** `/tags` renders a cloud with per-term counts; a term links into a
  filtered feed (excluded terms omitted, FEED-8).

### ANL-5 — Activity calendar
> As a candidate, I want a day grid of activity and to drill into a day.
> **Trace:** #1, #13

- **ANL-5.1** `/calendar` shows new + applied per day (distinct marks); a day
  number links to that day's list.
- **ANL-5.2** Archived vacancies still count on the calendar — archiving never
  moves `status_at`, so the record stays on the day it was applied. `[INV]`

---

## Epic 8 — Profile builder

*The candidate profile is data (`profile.json`), editable in the UI, and the
single source of truth the scorer sees.* `[INV]`

### PRO-1 — Preview skills from a pasted CV
> As a candidate, I want to paste my CV and see the skills it found, grouped by
> role and highlighted inline. **Trace:** #1

- **PRO-1.1** `action=preview` highlights recognised skills in the CV text and
  groups them by the role's groups (role groups first, extras appended).
- **PRO-1.2** Preview writes nothing to disk.
- **PRO-1.3** Seniority and years are auto-detected from the CV (earliest
  seniority mention wins, not highest rank).

### PRO-2 — Save the profile (and optionally scan)
> As a candidate, I want to save, or save-and-scan. **Trace:** #1

- **PRO-2.1** `action=save` writes `profile.json` atomically → 303 →
  `/profile?saved=1`, page in the saved (VIEW) state.
- **PRO-2.2** `action=save_scan` saves and triggers a scan → 303 → `/`.
- **PRO-2.3** An empty profile opens in EDIT; `?edit=1` forces EDIT; otherwise
  VIEW.

### PRO-3 — Skills are validated against the CV
> As a candidate, I want the confirmed-skill list to track the CV, not drift.
> **Trace:** #1

- **PRO-3.1** On save, a skill survives only if present in the CV text
  (`validate_skills`); stale ones are dropped. `[INV]`
- **PRO-3.2** A synonym maps to its canonical form (`skills.canonical`); a CV
  skill unknown to the dictionary still survives (word-boundary).

### PRO-4 — Extra (non-CV) skills
> As a candidate, I want to add assumed-standard skills (Scrum, HTTP) that a CV
> rarely spells out. **Trace:** #16 (deferred), current repo

- **PRO-4.1** `extra_skills` are canonicalised, deduped against confirmed skills,
  and **not** validated against the CV.

### PRO-5 — Stack, anti-goals, and boundaries
> As a candidate, I want to steer depth, exclusions, and honesty. **Trace:** #1

- **PRO-5.1** `stack` terms add deep DOU search feeds (beating the 25-cap on what
  matters); not validated against the CV.
- **PRO-5.2** `exclude` ("not for me") canonicalised; drives L0 title exclusion
  (L0-3.2), tag muting (FEED-8), and stats muting.
- **PRO-5.3** `notes` (boundaries) is free text fed to the scorer (SCO-2).

### PRO-6 — Role and seniority
> As a candidate, I want to pick my role and confirm the detected level.
> **Trace:** #1

- **PRO-6.1** Role ∈ the known roles (QA / QA Automation / Frontend / Backend);
  an unknown role falls back to the default. Each role carries its own feeds, L0,
  and skill groups.

### PRO-7 — Own-account LLM config
> As an owner, I want my API key and provider stored per-account, never in git.
> **Trace:** #14

- **PRO-7.1** `api_key / llm_model / llm_provider / llm_base_url` are saved in
  `profile.json` (gitignored), take precedence over config (SCO-7.2), and power
  both scoring and cover letters.

---

## Epic 9 — Application tracker & cover letters

*Applied vacancies move through a small hiring pipeline; an AI drafts a cover
letter from the candidate's own facts.*

### HIRE-1 — Move a vacancy through hiring stages
> As an applicant, I want to track a vacancy across stages. **Trace:** #13

- **HIRE-1.1** `/hiring` cards move through `waiting_hr → pre_screen →
  tech_interview → finish` via `POST /hiring/update`.

### HIRE-2 — Notes are never dropped
> As an applicant, I want per-stage notes preserved when I switch stages.
> **Trace:** #13

- **HIRE-2.1** The note shown for the current stage is saved before moving, so
  switching stages never loses an edit.
- **HIRE-2.2** Notes are stored per stage (JSON map on the row).

### HIRE-3 — Archive and restore
> As an applicant, I want to finish and archive, and restore if needed.
> **Trace:** #13

- **HIRE-3.1** "Finish & archive" sets `status=archived`, stage `finish`; the
  card leaves the feed (incl. the "all" tab and its count).
- **HIRE-3.2** "Restore to Applied" sets `status=applied`.
- **HIRE-3.3** Neither archive nor restore touches `status_at` (calendar
  integrity, ANL-5.2). `[INV]`

### HIRE-4 — Generate a cover letter from own facts
> As an applicant, I want a fit evaluation + letter + traceability drafted from
> **my** career facts, in one click. **Trace:** #14, #15

- **HIRE-4.1** The ✍ button generates evaluation + letter + traceability from
  `career-facts.md` in the data dir.
- **HIRE-4.2** The fit band is derived from the fit score (no `AMBER · 0`
  contradiction). **Trace:** #15
- **HIRE-4.3** The ✍ button is available on `interested` feed cards too, opening
  the same modal; evaluation/traceability render as Markdown. **Trace:** #15

### HIRE-5 — Cache the letter
> As an applicant, I don't want to pay to regenerate on every view. **Trace:** #14

- **HIRE-5.1** The result is stored in `jobs.cover_data` and returned from cache
  on subsequent views (never recomputed on view). `[INV]`
- **HIRE-5.2** `regenerate=1` forces a fresh generation, overwriting the cache.

### HIRE-6 — Degrade gracefully
> As an applicant with the feature not set up, I want a clear message, not a
> crash. **Trace:** #14, #15

- **HIRE-6.1** Missing `career-facts.md` → a `{ok:false, error}` popup (HTTP 200),
  naming the missing file.
- **HIRE-6.2** Missing API key → a popup pointing to Profile → LLM access.
- **HIRE-6.3** Any generation failure (network/timeout/bad JSON) becomes popup
  text, never a 500. `[INV]`

---

## Epic 10 — Operations & control

*The scan can be triggered from the UI and observed, without corrupting state or
spawning duplicates.*

### OPS-1 — Trigger a scan from the UI
> As a user, I want a Scan button that never spawns a second run. **Trace:** #1

- **OPS-1.1** `POST /run` triggers a run and 303s back to the same page.
- **OPS-1.2** A press during an active run returns `busy` (single-flight), not a
  second process. `[INV]`
- **OPS-1.3** With no runner wired, `POST /run` → 503.

### OPS-2 — Single-flight lock, shared with cron
> As an operator, I want the button and cron to share one lock, and a hung run to
> auto-clear. **Trace:** #1

- **OPS-2.1** The lock is one directory shared with `run.sh`.
- **OPS-2.2** A lock older than one hour is treated as stale and removed. `[INV]`

### OPS-3 — CLI surface
> As an operator, I want `run / check / top / stats` from the terminal.
> **Trace:** #1

- **OPS-3.1** `check` reports DOU / IMAP / scorer / Telegram connectivity and
  writes nothing to the DB.
- **OPS-3.2** `top` lists best-scored vacancies; `stats` prints the funnel
  (total / passed L0 / notified) + by-source + top L0 reasons.

---

## Epic 11 — Access control & web contract

*The database is a private job-search history. The HTTP surface is well-defined
and validated in a fixed order.*

### SEC-1 — Two token channels
> As a phone user, I want to pass a token by query or header. **Trace:** #1, #5

- **SEC-1.1** `?token=` (browser) and `X-Jobradar-Token:` (API) are both accepted.

### SEC-2 — Localhost vs token
> As a home user, I want localhost open, everything else gated. **Trace:** #1

- **SEC-2.1** `webui.token` empty → only `127.0.0.1 / ::1 / localhost` accepted;
  non-local → 403.
- **SEC-2.2** `webui.token` set → a match is required (query or header) or 403
  "Invalid or missing token.".

### SEC-3 — Public endpoints and validation order
> As an integrator, I want health/resources public and a predictable order.
> **Trace:** #1, #5

- **SEC-3.1** `/health` → 200 `<p>ok</p>`; `/resources/<name>` public.
- **SEC-3.2** `require_token` runs **before** input validation → `/status`
  without a token → 403, not 400.
- **SEC-3.3** Wrong method on a known path → 405; unknown path → 404 "Not Found".

### SEC-4 — Resource whitelist / traversal guard
> As an operator, I don't want `/resources` to read arbitrary files. **Trace:** #1

- **SEC-4.1** Only whitelisted basenames (`dou_logo.png`, `djinni_logo.png`) are
  served; anything else → 404, and a traversal path cannot escape the resources
  dir (`os.path.basename`). `[INV]`

### SEC-5 — Security headers
> As a user, I want safe defaults on every response. **Trace:** #5

- **SEC-5.1** Every response carries `Referrer-Policy: no-referrer`; HTML also
  carries `Cache-Control: no-store`.

### SEC-6 — Redirect contract
> As an integrator, I want the 303 redirects to be part of the contract.
> **Trace:** #5

- **SEC-6.1** `POST /status`, `/run`, `/profile`, `/hiring/update` respond 303
  with a `Location` (observable only with `maxRedirects: 0`).
