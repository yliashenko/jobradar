"""Dedup key = sha256(normalized company | normalized title).

Deliberate skew (CLAUDE.md §5): better to show extra than to miss one.
Digits are NOT stripped from the title before hashing — at ZONE3000 #1205 and
#1301 may be different roles, and stripping digits would cause a miss (§4).
"""

import hashlib
import re

# Noise words that shouldn't affect merging: level «engineer», format
# «remote/віддалено», country, vacancy gender markers. Removed before hashing.
_NOISE = (
    "engineer",
    "specialist",
    "remote",
    "віддалено",
    "ukraine",
    "україна",
    "m f",
    "d",
)


def normalize_key(value):
    value = (value or "").lower()
    value = re.sub(r"[^a-z0-9а-яіїєґ]+", " ", value, flags=re.UNICODE)
    words = [w for w in value.split() if w not in _NOISE]
    return " ".join(words).strip()


def job_hash(company, title):
    payload = normalize_key(company) + "|" + normalize_key(title)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
