"""Per-request SQLite connection, stored on Flask's `g` and closed on teardown.

The schema and migrations belong to the core; the web layer only opens a
connection. `get_db()` returns None when the database file doesn't exist yet
(before the first scan) so routes can show the empty-state page.
"""

import os

from flask import g

from jobradar import paths
from jobradar.core.db import db_connect


def get_db():
    if "db" not in g:
        g.db = db_connect() if os.path.exists(paths.db_path()) else None
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()
