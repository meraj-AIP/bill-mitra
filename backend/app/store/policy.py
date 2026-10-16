"""Per DISCOM review policy. Rows are seeded with the owner's defaults at startup (app/store/db.py)."""

from app.domain.review import Policy
from app.store.db import DISCOM_UNITS, tx

_COLUMNS = ("ae_limit", "custom_needs_approval", "spike_ratio", "spike_min_increase", "min_history_months",
            "decision_sla_days")


def get(discom: str | None) -> Policy:
    """The DISCOM's policy; a bill with an unknown DISCOM is judged by the defaults."""
    if discom not in DISCOM_UNITS:
        return Policy(discom="TGSPDCL")
    with tx() as conn:
        row = conn.execute("SELECT * FROM review_policy WHERE discom = ?", (discom,)).fetchone()
    return Policy(**{k: row[k] for k in ("discom", *_COLUMNS)}) if row else Policy(discom=discom)  # type: ignore[arg-type]


def all_policies() -> list[Policy]:
    return [get(d) for d in DISCOM_UNITS]


def save(policy: Policy) -> Policy:
    values = policy.model_dump()
    with tx() as conn:
        conn.execute(f"UPDATE review_policy SET {', '.join(f'{c} = ?' for c in _COLUMNS)}, "
                     "updated_at = CURRENT_TIMESTAMP WHERE discom = ?",
                     (*(values[c] for c in _COLUMNS), policy.discom))
    return get(policy.discom)
