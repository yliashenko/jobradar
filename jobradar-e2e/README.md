# jobradar-e2e

End-to-end and contract tests for the **jobradar** web UI, built with
Playwright + TypeScript.

jobradar is a personal job-radar tool (collects vacancies → dedup → cheap
filter → LLM scoring → web triage). This suite exercises its web UI; the product
is a Flask app, served with `python -m jobradar serve`.

---

## What this suite is (and is not)

It is a **deliberately e2e-weighted** Playwright suite across two layers:

| Layer | Tool | What it covers |
| --- | --- | --- |
| **UI e2e** | `page` | browser flows: CV/profile, feed triage, tag filter, calendar, stats |
| **API / contract** | `request` | HTTP contract: status codes, auth, redirects, input validation |

It is **not** a re-implementation of an API mega-suite. The API layer here is a
thin, honest contract check; the depth is in the UI e2e flows.

Scope is **positive cases first**; negative/security/perf are later iterations.

---

## The delta that shaped it

Coming from a classic API-TAF, Playwright removes whole layers by folding them
into the runner. This table is the design rationale — what each classic layer
becomes, and why:

| Classic API-TAF | Playwright | What changes |
| --- | --- | --- |
| root `beforeAll` + login, state in a global | worker-scoped fixture | state lives on the worker — the cure for a Singleton |
| `AuthorizationService` (Singleton) | fixture returns token/context | injection instead of global state |
| controller facades | `pages/` (POM) + `api/` facade | UI and API split explicitly |
| `url-builders/`, `RequestOptionsBuilder` | `baseURL` + options object | builders/factory move into the runner |
| `chai` + `containSubset` | web-first `expect()` | assertions auto-wait — a class of flake disappears |
| `ignore`-lists in `.mocharc-*` | `@smoke` tags + `--grep` | filter by meaning, not by path |
| isolation via unique names | worker-scoped data | real isolation, not name suffixes |

---

## Layout

```
specs/      test specs (contract + e2e)
pages/      Page Objects — UI layer
api/        facade over APIRequestContext (the API layer)
fixtures/   worker-scoped server + seeded data
utils/      helpers (e.g. the @step decorator)
```

---

## Getting started

The worker fixture boots the product as a subprocess, so both Node and Python
(with the product's Flask runtime) must be available.

```sh
# from the repo root — the product's Python runtime (Flask)
python3 -m pip install -r ../requirements.txt

# in jobradar-e2e/
npm ci
npx playwright install --with-deps

npm test                 # whole suite, both projects
npm run test:smoke       # only @smoke
npm run test:chromium    # one browser
npm run report           # open the last HTML report
```

The server is started **automatically**: a worker-scoped fixture boots an
isolated `python -m jobradar serve` per worker and waits for `/health`. No manual
server step, no secrets.

---

## Key decisions (each is defensible)

- **`baseURL` from `process.env.JOBRADAR_URL`** with a localhost fallback — one
  suite runs locally and against a deployed instance; the difference is one env
  var, not a code change.
- **`trace: 'on-first-retry'`** — traces are expensive; collect them exactly
  when a test failed and is retrying, i.e. in CI.
- **Granular timeouts** (`timeout` / `expect.timeout` / `actionTimeout`) instead
  of one global value — three different limits for three different things.
- **Tags over ignore-lists** — `@smoke` / `@regression` + `--grep` filter by
  meaning; nothing is silenced by editing path lists.
- **`@step()` decorator** ([utils/step.ts](utils/step.ts)) — wraps POM methods in
  `test.step` for a readable trace; a direct analog of `@AllureStep()`.
- **CI has a single source of truth** — `retries`/`workers` live in the config,
  branched on `process.env.CI`; the workflow only triggers the run.

---

## Environments

- **Functional suite → a self-hosted instance** the fixture boots itself: own
  port, own database, full isolation; runs locally and in CI without access to
  any infrastructure.
- **Deployed target → separate, read-only smokes** (`@smoke-readonly`, planned):
  `baseURL` from env, destructive tests fenced off by tag so they physically
  cannot run against a live environment.

---

## Status

The full suite is green across `chromium` and `mobile`. See
[../docs/qa/traceability.md](../docs/qa/traceability.md) for the live test count
and per-requirement coverage.

| Piece | State |
| --- | --- |
| scaffold, `playwright.config.ts`, CI workflow | ✅ done |
| worker-scoped isolation fixture (`JOBRADAR_HOME`) | ✅ done |
| seed + per-test reset | ✅ done |
| `api/` facade, `pages/` POM, UI e2e flows | ✅ done |
| contract tests (`/health`, routing, auth, validation) | ✅ done |
| `@step()` decorator | ✅ done |
| test plan, API contract docs | ✅ done |
| deployed `@smoke-readonly` project | ⏳ planned |
| CI sharding + merge-reports | ⏳ planned |

---

## Docs

- [ARCHITECTURE.md](ARCHITECTURE.md) - how the framework is layered, and the
  worker-isolation lifecycle.
- [API-CONTRACT.md](API-CONTRACT.md) - the web UI HTTP contract, derived from the
  handler (there is no OpenAPI to generate from).
- [JobRadar Internals Artefact](https://claude.ai/code/artifact/5c814055-bc62-41e7-9dcd-b92de56717b0) - more information see detailed artifact

---

## Determinism

The functional suite never touches live infrastructure: LLM scoring is mocked,
sources come from recorded fixtures, and the database is seeded per run. This
keeps every run reproducible and free of network and cost.
