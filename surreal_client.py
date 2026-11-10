"""Create an authenticated connection to the configured SurrealDB instance."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from surrealdb import Surreal


load_dotenv()


def connect() -> Surreal:
    """Connect to SurrealDB using the settings in the project .env file.

    The caller is responsible for closing the returned connection with
    ``db.close()`` when finished.
    """
    required = (
        "SURREALDB_URL",
        "SURREALDB_NAMESPACE",
        "SURREALDB_DATABASE",
        "SURREALDB_TOKEN",
    )
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing SurrealDB configuration: {', '.join(missing)}")

    db = Surreal(os.environ["SURREALDB_URL"])
    try:
        db.use(os.environ["SURREALDB_NAMESPACE"], os.environ["SURREALDB_DATABASE"])
        db.authenticate(os.environ["SURREALDB_TOKEN"])
    except Exception:
        db.close()
        raise
    return db
