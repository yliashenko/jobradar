#!/usr/bin/env python3
"""
jobradar stats — positioning against the market.

The one strong combination of the available data: market demand (skill
frequency across collected vacancies) × the candidate's profile. DOU has almost
no salaries and the scorer is off for now — so the page deliberately does NOT
fake a salary percentile or a score distribution. It computes exactly what the
data supports: coverage, the pass-bar minimum, differentiators and gaps by
leverage.

Thresholds are display heuristics, not truth. On a small sample (dozens of
vacancies, one source) they're a signal, not a verdict; the UI must state the
sample size.
"""

from jobradar import skills

TOP_N = 15  # "most in demand" = this many top by frequency
STAKES_MIN = 0.55  # >= this demand → pass-bar minimum (expected of everyone)
DIFF_MIN = 0.15  # differentiator: in demand, but not in every vacancy
GAP_LIMIT = 12  # how many gaps to show (highest-leverage)


def analyse(texts, profile_skills, exclude=None):
    """texts — "title + description" of each vacancy; profile_skills — the candidate's skills.

    exclude — "not for me" skills: they're removed from the market entirely
    before counting. Then coverage, differentiators and gaps are computed only
    against what's relevant to the goal — "manual testing" is no longer a
    phantom gap.

    Returns a structure for display, or None if there's nothing to compute.
    """
    total = len(texts)
    if not total:
        return None

    tally = skills.tally(texts)  # {skill: in how many vacancies}
    if exclude:
        muted = {skills.canonical(e).lower() for e in exclude}
        tally = {t: c for t, c in tally.items() if t.lower() not in muted}
    have = {skills.canonical(s).lower() for s in profile_skills}
    ranked = sorted(tally.items(), key=lambda kv: (-kv[1], kv[0].lower()))

    def frac(count):
        return count / total

    top = ranked[:TOP_N]
    covered = [t for t, _ in top if t.lower() in have]

    # Pass-bar minimum: both what you have and what you don't (don't = urgent).
    stakes = [(t, c, t.lower() in have) for t, c in ranked if frac(c) >= STAKES_MIN]
    # Differentiators: your skills in the mid-band of demand (in demand, not ubiquitous).
    differentiators = [
        (t, c)
        for t, c in ranked
        if DIFF_MIN <= frac(c) < STAKES_MIN and t.lower() in have
    ]
    # Gaps by leverage: what's missing, by descending frequency = a roadmap.
    gaps = [(t, c) for t, c in ranked if t.lower() not in have][:GAP_LIMIT]

    return {
        "total": total,
        "unique_terms": len(tally),
        "top_n": len(top),
        "covered": len(covered),
        "stakes": stakes,
        "differentiators": differentiators,
        "gaps": gaps,
        "profile_skill_count": len(have),
    }
