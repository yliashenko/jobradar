# jobradar webui — API contract

> There is no OpenAPI/Swagger spec: the product serves HTML (Flask + Jinja), not
> JSON. The single source of truth is the routes in `jobradar/web/routes.py` and
> the authorization logic in `jobradar/web/auth.py`. This is a hand-written
> summary contract extracted from them. Keep it in sync with the code.

## Authorization — two channels

| Channel | How it is passed | Intended for |
| --- | --- | --- |
| query | `?token=<t>` | browser |
| header | `X-Jobradar-Token: <t>` | API client |

Rule (`auth.require_token`):

- `webui.token` **empty** → **only localhost** is accepted (`127.0.0.1`,
  `::1`, `localhost`); no token required. Non-localhost → **403**.
- `webui.token` **set** → a match is required (query or header), otherwise
  **403** "Invalid or missing token.".
- `/health` and `/resources/...` **skip** the check (they are public).

## GET

| Path | Auth | OK | Errors |
| --- | --- | --- | --- |
| `/health` | no | `200`, body `<p>ok</p>` | — |
| `/resources/<name>` | no | `200` image (whitelist) | `404` |
| `/` (feed) | yes | `200` HTML; no DB → `200` empty-state | `403` |
| `/runs` `/tags` `/stats` `/calendar` `/company` | yes | `200` HTML; no DB → empty-state | `403` |
| `/profile` | yes | `200` HTML (no DB needed) | `403` |
| *unknown path* | — | — | **`404`** (default Flask page, "Not Found") |

## POST

| Path | Auth | Body | OK | Errors |
| --- | --- | --- | --- | --- |
| `/status` | yes (token) | `hash`, `status`, `back` | **`303`** + `Location` | `400` "Unknown status or empty identifier."; `404` (no DB) |
| `/run` | yes (token) | `back` | `303` (`started`/`busy`) | `503` (runner unavailable) |
| `/profile` | yes (token in the `token` field) | `action` (`preview`/`save`/`save_scan`), `role`, `cv_text`, … | `303` (`save`→`/profile?saved=1`; `save_scan`→`/`) | — |
| *unknown path* | — | — | — | **`404`** (default Flask page) |

## What changed after the migration to Flask (important for tests)

- **Custom 404 messages are gone.** An unknown path → **the default Flask 404**
  ("Not Found"), not the old ad-hoc "No such page/action" message. Assert on the text "Not Found".
- **`405` now exists.** A known path + wrong method → **405 "Method Not Allowed"**
  (e.g. `POST /health`, `GET /status`). The old server had no such response.
- **Messages are in English:** `403` → "Invalid or missing token.",
  `400` → "Unknown status or empty identifier.".
- **403 is wrapped in a Flask template** (`<title>403 Forbidden</title>`) — the
  message text remains a substring, so `toContain(...)` survives, `toBe(...)` does not.
- **Security headers** on every response: `Referrer-Policy: no-referrer`;
  on HTML — `Cache-Control: no-store`.

## Stable selectors (`data-testid`)

| Node | Locator |
| --- | --- |
| feed container | `[data-testid="feed"]` |
| job card | `[data-testid="job-card"]` + `data-hash="<hash>"` |
| status button | `[data-testid="status-btn"]` + `data-status="<status>"`; the active one has the `.on` class |
| tag chip | `[data-testid="tag"]` + `data-tag="<term>"`; links to `/?status=all&tech=<term>` |
| calendar day | `[data-testid="calendar-day"]` + `data-day="<YYYY-MM-DD>"` (distinct `.cal-new` / `.cal-applied`) |

## Status vocabulary (`status` values for `POST /status`)

`new`, `interested`, `applied`, `skipped` — the UI labels match the keys
(English, lowercase). `archived` is a terminal value with no feed tab of its own
(it lives on the Applied tab, behind its "Show archived" toggle:
`/?status=applied&archived=1`); `rejected` is a legacy value migrated to
`skipped`.

## Notes for tests

- **Ordering in Flask:** a route is matched by method → `405` on the wrong method
  of a known path; `require_token` runs **before** input validation, so `/status`
  without a token returns `403`, not `400`.
- **`303` is part of the contract**, not an implementation detail: to observe the
  redirect itself, a test needs `maxRedirects: 0`.
- **`POST /status` with a valid status WRITES to the database** — it is
  destructive. In the suite it is isolated via a per-worker DB + auto-reset (`fixtures/server.ts`).
- **`extraHTTPHeaders` is inherited** even in `request.newContext` — for a truly
  anonymous request (the 403 test) set `extraHTTPHeaders: {}` explicitly.
