# Candidate profile (example)

Copy this file to `profile.md` and rewrite it for yourself, **or** fill the profile
through the web UI (which writes `profile.json`). The scorer prefers `profile.json`;
`profile.md` is the fallback. Both are git-ignored — this `.example` is the only
profile committed to the repo.

This text is fed verbatim to the LLM scorer as the single source of truth about the
candidate. The one section that earns its keep is **"Boundaries that must not blur"**:
without it the model rates every vacancy that merely mentions your strongest keyword
an 8/10. Keep it honest and specific — see CLAUDE.md §3.

---

## Positioning
QA Automation Engineer / SDET. Remote or hybrid. Expectation: from $X/mo.
English B2, <native language> C2.

## Experience (summary)
- Example Corp, 2018–present:
  - Manual QA and test design: 2018–2020
  - QA Automation (TypeScript, API frameworks): 2020–present
- Before Example Corp: QA roles at Two Other Companies (2015–2018)

## What the candidate can actually defend on a technical screen
- API automation in TypeScript: Mocha/Chai, in-house frameworks, CI, Allure
- Manual QA and test design at a lead level
- CI/CD: pipelines, Git; Docker at a user level

## Boundaries that must not blur (keep the scorer honest)
- Python is NOT claimed as a working language. A vacancy requiring
  "strong Python, 3+ years hands-on" is a GAP, not a PARTIAL.
- pytest — currently learning, no commercial experience. GAP.
- Java, Kotlin, Go, Ruby, PHP — no experience at all. GAP.
- Performance testing (JMeter, Gatling, k6) — no experience. GAP.
- Mobile automation (Appium, XCUITest, Espresso) — no experience. GAP.
- Security testing / pentest — no experience. GAP.

## What raises interest in a vacancy
- SDET / QA Automation roles with real engineering depth, not pure manual
- TypeScript as the primary automation language
- Product teams and tooling work, not only running test suites

## What lowers interest
- Middle-level and below
- Pure manual QA without automation
- Mandatory relocation or full-time office
