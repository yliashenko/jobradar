# jobradar — Playwright traceability (live status)

> PW-ID → spec file → status. Updated as batches land. ✅ done · 🟡 partial · ❌ not yet.
> Suite state: **87 tests green** (45 baseline + 42 new/migrated), 174 across chromium + mobile.

## Epic 6 — Feed & triage

| PW-ID | Status | Spec |
|---|---|---|
| FEED-1 | ✅ | `feed.spec.ts` (migrated → identity) |
| FEED-2 | ✅ | `scoring.spec.ts` (rail) |
| FEED-3 | ✅ | `feed-more.spec.ts` |
| FEED-4 | ✅ | `status-change.spec.ts` |
| FEED-5 | ✅ | `contract.spec.ts` (303) |
| FEED-6 | 🟡 | `feed.spec.ts` (structure; no dedicated counter test) |
| FEED-7 | ✅ | `health.spec.ts` (400) |
| FEED-8 | ✅ | `archived.spec.ts` |
| FEED-9 | ✅ | `period.spec.ts` |
| FEED-10/11/12 | ✅ | `filters.spec.ts` |
| FEED-13 | ✅ | `feed-more.spec.ts` (×2) |
| FEED-14 | ✅ | `feed-more.spec.ts` (×2) |
| FEED-15/16 | ❌ | Applied-tab sort — needs a 2nd applied row (`at` ready) |
| FEED-17 | ✅ | `feed-more.spec.ts` (include/exclude ×2) |
| FEED-18 | ✅ | `tag-filter.spec.ts` |
| FEED-19 | 🟡 | card + `/tags` done; header autocomplete ❌ |
| FEED-20 | ✅ | `tags.spec.ts` (muting ×2) |
| FEED-21 | ❌ | picker count within-view |
| FEED-22 | ✅ | `company.spec.ts` |
| FEED-23 | ✅ | `empty.spec.ts` |
| FEED-24 | 🟡 | `filters.spec.ts` has source+score; 3-way ❌ |
| FEED-25/26 | ❌ | combined period+status+tag; include AND exclude |

## Epic 4 — Scoring UI
| PW-ID | Status | Spec |
|---|---|---|
| SCO-1/3 | ✅ | `scoring.spec.ts` |
| SCO-2 | ✅ | `scoring.spec.ts` |
| SCO-4 | ✅ | `scoring.spec.ts` (no-key affordance on v8) |

## Epic 7 — Analytics
| PW-ID | Status | Spec |
|---|---|---|
| ANL-1/2 | ❌ | `/runs` funnel + per-feed — needs `runs` table seed |
| ANL-3 | 🟡 | `stats.spec.ts` (sections + coverage); sample-size detail ❌ |
| ANL-4 | ❌ | sample sizes / "not shown" |
| ANL-5 | ✅ | `tags.spec.ts` |
| ANL-6 | ✅ | `calendar.spec.ts` (migrated) |
| ANL-7 | ❌ | calendar day drill-down |
| ANL-8 | ✅ | `calendar.spec.ts` |
| ANL-9 | ✅ | `stats.spec.ts` |

## Epic 8 — Profile
| PW-ID | Status | Spec |
|---|---|---|
| PRO-1 | ✅ | `profile.spec.ts` |
| PRO-2/3/8 | ✅ | `profile.spec.ts` |
| PRO-4 | ✅ | `contract.spec.ts` (303) |
| PRO-9/14/15 | ✅ | `profile.spec.ts` (extra-skill, role persist, LLM config) |
| PRO-6 | 🟡 | edit form + save-persist; `?edit=1`/VIEW detail ❌ |
| PRO-12 | 🟡 | `tags.spec.ts` covers exclude→feed; L0-on-scan ❌ (needs run) |
| PRO-5/7/10/11/13/16 | ❌ | save_scan, CV-validation, extra-dedup, stack→feed, notes→scorer, toggle-off |

## Epics 1–4 — pipeline substrate (flagship complex-e2e)
Run synchronously via the CLI over a fixture source + stub LLM (harness:
`fixtures/{stub-llm,run}.ts`, `runScan`).
| PW-ID | Status | Spec |
|---|---|---|
| PIPE-1 | ✅ | `pipeline.spec.ts` (fresh scan → scored card) |
| PIPE-2 | ✅ | `pipeline.spec.ts` (cross-source dedup) |
| PIPE-4 | ✅ | `pipeline.spec.ts` (case/whitespace dedup) |
| PIPE-5 | ✅ | `pipeline.spec.ts` (digit double-show) |
| PIPE-10 | ✅ | `pipeline.spec.ts` (L0 title-exclude) |
| PIPE-3/6 | ❌ | TTL reopen (needs job-hashed aged seed); DOU 25-cap (fixture isn't a DOU feed) |

## Epic 10 — Ops
| PW-ID | Status | Spec |
|---|---|---|
| OPS-1 | ✅ | `ops.spec.ts` (`POST /run` 303 + Scan-button wiring) |
| OPS-2/3/4 | 🟡/❌ | 303 done; busy/single-flight & no-runner 503 not HTTP-distinguishable → pytest |

## Epic 9 — Application tracker & cover letters
| PW-ID | Status | Spec |
|---|---|---|
| HIRE-1 | ✅ | `hiring.spec.ts` (stage move) |
| HIRE-3 | ✅ | `hiring.spec.ts` (archive removes from feed) |
| HIRE-4/10 | ✅ | `hiring.spec.ts` (cover generate via stub + cache) |
| HIRE-12/13 | ✅ | `hiring.spec.ts` (graceful degrade: no facts / no key) |
| HIRE-2/5/6/7/8/9/11/14/15/16 | ❌ | notes-preserve, restore, per-stage UI, modal render, regenerate, feed-card ✍ |

## API / contract & cross-cutting
| PW-ID | Status | Spec |
|---|---|---|
| API-1/2/3 | ✅ | `health.spec.ts` |
| API-4 | ✅ | 303 on `/status`+`/profile` (`contract.spec.ts`), `/run` (`ops.spec.ts`), `/hiring/*` (`hiring.spec.ts`) |
| PW-UI-1 | ❌ | tooltip sweep |

---

## What's left, by cost

**A — Doable now (no new infra), ~11 rows left:** FEED-15/16, FEED-19 (autocomplete),
FEED-21, FEED-24 (3-way), FEED-25/26, ANL-3/4, ANL-7, PRO-6/10/16, PW-UI-1.
Mostly seed/UI on the existing harness (`at` override already added).

**B — Needs a `runs`-table seed, 2 rows:** ANL-1/2 (`/runs` funnel + per-feed).
Small, but reverse the `runs.feeds` JSON shape and migrate the existing
`runs.spec.ts` empty-state test (it relies on zero run rows).

**C — Wave-2/3 stubs — BUILT.** The harness (`fixtures/stub-llm.ts` OpenAI-compatible
stub, `fixtures/run.ts` config patcher, `runScan` synchronous CLI trigger, config +
`.lock` reset in `server.ts`) landed and unlocked:
- **Pipeline flagships** — PIPE-1/2/4/5/10 (`pipeline.spec.ts`).
- **Scan trigger** — OPS-1 (`ops.spec.ts`).
- **Hiring + cover** — HIRE-1/3/4/10/12/13 (`hiring.spec.ts`), cover via the stub.

Remaining tail (optional): PIPE-3/6, the deeper HIRE UI journeys, the bucket-A
leftovers, and ANL-1/2 (`runs`-table seed).

---

## Wrap-up snapshot

**Layer shape of the 87 tests today: API ~23 (26%) · UI ~57 (66%) · E2E ~7 (8%).**
The requirements-first redesign delivered the wide API base, the solid UI middle,
**and now the E2E cap** — the pipeline flagships (fixture source + stub LLM + a
real scan), the archive journey, and the cover-letter generation. All three layers
present, deterministic, offline, and green on chromium + mobile. Product code was
**never touched** for testing — the seams (`JOBRADAR_HOME`, swappable scorer/source
via `base_url`, `POST /run`, the built-in fixture source) already existed.

The whole show-case arc is now demonstrable in the suite: an as-is UI+smoke set →
a requirements-driven catalog that reproduced the inverted pyramid → the strict
`assertion-layer` reclassification → a harness that surfaces the deep pipeline
end-to-end without a single line of product change.
