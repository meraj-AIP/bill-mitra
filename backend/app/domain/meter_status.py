"""The meter status code ("Sts") printed beside each reading on a TGSPDCL / TGNPDCL spot bill.

The meter reader's handheld records the meter's condition at the visit. Only 01 means the units are an actual
reading; the others mean the units were estimated, averaged or carried. TGSPDCL does not publish the code list, so
the meanings below come from APSPDCL consumer forum orders (the same spot billing system before the state split)
and must be confirmed by the DISCOM billing team before they are treated as final.
"""

from typing import Literal

StatusKind = Literal["normal", "stuck", "meter_changed", "door_locked", "not_in_use", "other"]

NORMAL = "01"
KIND: dict[str, StatusKind] = {"01": "normal", "02": "stuck", "04": "meter_changed", "05": "door_locked",
                               "09": "not_in_use"}
# Codes whose meaning no source confirms yet; every other listed code is from a forum order.
UNCONFIRMED = frozenset({"01", "09"})
STAFF_LABEL: dict[StatusKind, str] = {
    "normal": "Normal, read from the meter", "stuck": "Meter stuck, not recording",
    "meter_changed": "Meter changed in this period", "door_locked": "Door locked, units estimated",
    "not_in_use": "Premises not in use", "other": "Status code not known yet",
}


def kind(code: str | None) -> StatusKind | None:
    if code is None:
        return None
    return KIND.get(code, "other")


def estimated(code: str | None) -> bool:
    """True when the printed status says the units were not read from the meter this time."""
    return code is not None and code != NORMAL
