"""
Simple in-memory stores for MVP.

TODO:
- Replace with database-backed repositories (e.g., Postgres + SQLAlchemy).
- Add persistence, migrations, and proper indexing.
- Enforce tenancy via authenticated user.
"""

from typing import Dict, Optional

from src.api.models import Asset, Transcript, Quote, ExportJob, User

# In-memory "databases"
USERS: Dict[str, User] = {}
ASSETS: Dict[str, Asset] = {}
TRANSCRIPTS: Dict[str, Transcript] = {}
QUOTES: Dict[str, Quote] = {}
EXPORT_JOBS: Dict[str, ExportJob] = {}

# Internal ID counters per resource kind
_id_counters: Dict[str, int] = {}


def _next_id(prefix: str, counter_dict: Dict[str, int]) -> str:
    """
    Increment and return a sequential ID with the given prefix.
    Example: asset_1, asset_2, ...
    """
    current = counter_dict.get(prefix, 0) + 1
    counter_dict[prefix] = current
    return f"{prefix}_{current}"


# PUBLIC_INTERFACE
def generate_id(kind: str) -> str:
    """Generate a predictable ID for the given resource kind."""
    return _next_id(kind, _id_counters)


# PUBLIC_INTERFACE
def get_user(user_id: str) -> Optional[User]:
    """Fetch a user from the in-memory store."""
    return USERS.get(user_id)
