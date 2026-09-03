# jobradar e2e — Known problems (TAF gaps)

> An honest, self-critical inventory of what the Playwright test-automation
> framework does **not** yet do well. Written as an external reviewer would rank
> it: by impact on trust in the suite, not by ease of fixing. The suite is a
> clean, requirements-driven, deterministic happy-path framework — these are the
> gaps between that and a production-grade TAF.

Status: 2026-09-01. Suite: 87 tests (174 across chromium + mobile), green.

---

## 1. No quality gates on the framework's own TypeScript (high)

`jobradar-e2e` has **no ESLint, no Prettier, and no `tsc --noEmit`**; CI
(`.github/workflows/e2e.yml`) runs only `npx playwright test`. The Python side
has `ruff` + `mypy`; the test code that drives it has nothing. A broken type, an
unused import, or an `any` ships unnoticed.

- **Impact:** the framework claims a "professional dev layer" but exempts itself
  from the gate it applies to the product.
- **Fix:** add ESLint (`eslint-plugin-playwright`), Prettier, and a
  `tsc --noEmit` step to CI, ahead of the test run.

## 2. Time is not controlled → latent flakiness (high)

The e2e server's clock can't be frozen, so date-sensitive tests use real `now`
plus relative dates (`days_ago`). `calendar` (current-month markers) and
`filters` (period `days=7/14`) will drift at day/month boundaries — e.g. a
3-days-ago row crossing the 1st of the month moves into the current month. CI's
`retries: 2` would **mask** this rather than surface it.

- **Impact:** the single largest reliability risk; a green run can lie near
  boundaries.
- **Fix:** inject a fixed "now" into the server (env/date override), or tag and
  quarantine the date-sensitive tests and drop retry-masking on them.

## 3. URLs / query strings are not centralized (medium-high)

Selectors are DRY (`utils/selectors.ts`), but URLs are raw strings across the
specs: `page.goto('/?status=all')` (×7), `'/?status=all&tech=API&sort=score_asc'`,
`'/?days=7'`, `'/profile?edit=1'` (×3). `utils/routes.ts` is barely used. A route
or query-key change (`tech` → anything) breaks many specs at once — an asymmetry
with the now-centralized selectors.

- **Fix:** a small query/route builder (e.g. `feedUrl({ status, tech, sort })`)
  beside `Routes` and `sel`.

## 4. Coverage is happy-path functional only (medium)

No **negative/validation** depth beyond a couple of cases (400, no-facts), and
**zero accessibility, visual-regression, or performance** layers. ~40% of the
requirements catalog is still partial/absent (see `traceability.md`:
FEED-15/16/21/24–26, ANL-1–4/7, PRO-5/7/10/11/13/16, HIRE-2/5–9/11/14–16,
PIPE-3/6, OPS busy/503). A few assertions are smoke-level ("heading visible")
and don't verify data correctness.

## 5. Brittle exact-count assertions on the shared fixture (medium)

`tags` asserts exactly `18` unique tags; several filter tests assert `1/2/3`.
These are coupled to the one 12-row `catalog` fixture; changing the seed
cascades. The manifest mitigates the *mystery-guest* smell but not the coupling —
the same brittleness class already migrated to identity/scoped in `feed`/`calendar`
still lives here.

## 6. Effectively Chromium-only (medium)

The two projects are `Desktop Chrome` and `Pixel 5` — **both Chromium**. No
Firefox, no WebKit/Safari. And "mobile" is only a viewport: there is **no
mobile-specific assertion** (responsive layout, hamburger menu, touch), so the
×2 run adds little confidence.

## 7. Traceability is a hand-maintained document (medium-low)

`traceability.md` maps requirements → specs by hand and drifts from reality (it
lagged the folder/merge refactor). There is no enforced requirement↔test link.

- **Fix:** tag tests (`@req:FEED-9`) and add a script that diffs the catalog
  against the tags in CI.

## 8. Mock fidelity (low-medium)

The stub-LLM tests assert the stub's canned output ("stub cover letter"): they
verify wiring, not real model behavior. The stub's request routing
(`body.includes('cover')`) is a fragile heuristic. The real scoring/cover LLM
contract is not exercised deterministically anywhere — a conscious trade-off, but
a blind spot. The "covered by pytest" claim for the out-of-scope areas
(notifications, auth internals, scorer prompt) is **asserted, not verified**
from the e2e side.

## 9. Smaller items (low)

- API tests assert raw HTML substrings (`data-hash="v1"`) rather than via `sel` —
  brittle to markup.
- CI runs the whole suite; the `@smoke`/`@regression` scripts exist but no fast
  smoke gate or sharding is wired.
- The async `POST /run` path (OPS) leaves a short-lived background run after the
  test; harmless (lock is reset), but untidy.
- `E2E_PYTHON` must be an absolute path — a relative one fails with `ENOENT`;
  a run-book footgun.

---

## Priority

Fix **1** and **2** first — they are about trusting the framework as an
instrument; without them a green run is not fully credible. Then **3** (cheap,
high maintainability payoff). **4/6** are conscious scope decisions (negative /
a11y / cross-browser) that deserve an explicit "in or out for this portfolio"
call rather than silent omission.
