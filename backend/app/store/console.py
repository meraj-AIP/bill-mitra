"""Aggregates for the Department console. Only counts and masked numbers leave this module.

Every query takes the same window and DISCOM filter as named parameters. Questions carry no DISCOM, so a DISCOM
filter leaves them out rather than guessing.
"""

import math
import sqlite3
import statistics
from typing import Any

from app.config import get_settings
from app.store.complaints import OPEN_STATUSES
from app.store.db import tx

STATUSES = ("Open", "In progress", "Resolved", "Rejected")
TIMING_SAMPLE = 1000
_EV = "ts >= datetime('now', :since) AND (:discom IS NULL OR discom = :discom)"
_CP = "created_at >= datetime('now', :since) AND (:discom IS NULL OR discom = :discom)"


def _p90(values: list[int]) -> int | None:
    return sorted(values)[math.ceil(0.9 * len(values)) - 1] if values else None


def _reads(conn: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    counts = dict(conn.execute(
        f"SELECT CASE WHEN audit_status = 'checked' AND intent = 'reread' THEN 'rescued' ELSE audit_status END k, "
        f"COUNT(*) FROM events WHERE type = 'read' AND {_EV} GROUP BY k", args).fetchall())
    timings = [r[0] for r in conn.execute(
        f"SELECT ms FROM events WHERE type = 'read' AND ms IS NOT NULL AND {_EV} ORDER BY id DESC LIMIT :n",
        {**args, "n": TIMING_SAMPLE})]
    return {
        "total": sum(counts.values()), "trusted_first_time": counts.get("checked", 0),
        "reread_rescued": counts.get("rescued", 0), "retake": counts.get("retake", 0),
        "not_a_bill": counts.get("not_a_bill", 0), "failed": counts.get("reading_failed", 0),
        "median_ms": round(statistics.median(timings)) if timings else None, "p90_ms": _p90(timings),
    }


def _complaints(conn: sqlite3.Connection, args: dict[str, Any]) -> dict[str, Any]:
    by_status = dict(conn.execute(f"SELECT status, COUNT(*) FROM complaints WHERE {_CP} GROUP BY status",
                                  args).fetchall())
    # A backlog is current state, so overdue ignores the window and counts every old open complaint.
    overdue = conn.execute(
        "SELECT COUNT(*) FROM complaints WHERE status IN (?, ?) AND created_at < datetime('now', ?) "
        "AND (? IS NULL OR discom = ?)",
        (*OPEN_STATUSES, f"-{get_settings().complaint_reply_days} days", args["discom"], args["discom"])).fetchone()[0]
    return {"complaints_by_status": {s: by_status.get(s, 0) for s in STATUSES}, "complaints_overdue": overdue}


_FAILED_OPEN = ("SELECT COUNT(*) FROM complaints c WHERE c.status IN ('Open', 'In progress') "
                "AND (:discom IS NULL OR c.discom = :discom) AND (SELECT m.delivery FROM complaint_messages m "
                "WHERE m.ticket = c.ticket AND m.author_kind != 'consumer' ORDER BY m.id DESC LIMIT 1) = 'failed'")


def _week(conn: sqlite3.Connection, discom: str | None) -> dict[str, Any]:
    """The last 7 days against the 7 before, whatever window the page is showing."""
    def window(since: str, until: str) -> dict[str, int]:
        args = {"since": since, "until": until, "discom": discom}
        span = "BETWEEN datetime('now', :since) AND datetime('now', :until) AND (:discom IS NULL OR discom = :discom)"
        bills, mismatches = conn.execute(f"SELECT COUNT(*), COALESCE(SUM(audit_status = 'mismatch'), 0) FROM events "
                                         f"WHERE type = 'bill_read' AND ts {span}", args).fetchone()
        opened = conn.execute(f"SELECT COUNT(*) FROM complaints WHERE created_at {span}", args).fetchone()[0]
        closed = conn.execute(f"SELECT COUNT(*) FROM complaints WHERE status IN ('Resolved', 'Rejected') "
                              f"AND updated_at {span}", args).fetchone()[0]
        return {"bills": bills, "mismatches": mismatches, "opened": opened, "closed": closed}

    failed = conn.execute(_FAILED_OPEN, {"discom": discom}).fetchone()[0]
    return {"this_week": window("-7 days", "+0 days"), "last_week": window("-14 days", "-7 days"),
            "failed_deliveries": failed}


def health() -> dict[str, Any]:
    """Today's signs that something needs fixing, for the admin. Counts only."""
    args = {"since": "-1 days", "discom": None}
    with tx() as conn:
        explained = dict(conn.execute(f"SELECT intent, COUNT(*) FROM events WHERE type = 'explain' AND {_EV} "
                                      "GROUP BY intent", args).fetchall())
        reads = _reads(conn, args)
        failed_7d = conn.execute("SELECT COUNT(*) FROM complaint_messages WHERE delivery = 'failed' "
                                 "AND created_at >= datetime('now', '-7 days')").fetchone()[0]
        failed_open = conn.execute(_FAILED_OPEN, {"discom": None}).fetchone()[0]
        overdue = _complaints(conn, {**args, "since": "-3650 days"})["complaints_overdue"]
    return {"explanations": {k: explained.get(k, 0) for k in ("llm_pass", "llm_fallback", "template")},
            "reads": reads, "failed_deliveries_7d": failed_7d, "failed_deliveries_open": failed_open,
            "complaints_overdue": overdue, "reply_days": get_settings().complaint_reply_days}


def summary(days: int = 30, discom: str | None = None) -> dict[str, Any]:
    args = {"since": f"-{days} days", "discom": discom, "day": f"-{days - 1} days"}
    with tx() as conn:
        def scalar(sql: str) -> Any:
            return conn.execute(sql, args).fetchone()[0]

        bills = scalar(f"SELECT COUNT(*) FROM events WHERE type = 'bill_read' AND {_EV}")
        audit = conn.execute(f"SELECT audit_status, COUNT(*) FROM events WHERE type = 'bill_read' AND {_EV} "
                             "GROUP BY audit_status", args).fetchall()
        overcharge = scalar(f"SELECT COALESCE(SUM(amount), 0) FROM complaints WHERE {_CP}")
        complaints = scalar(f"SELECT COUNT(*) FROM complaints WHERE {_CP}")
        questions = scalar(f"SELECT COUNT(*) FROM events WHERE type = 'question' AND {_EV}")
        alerts = scalar(f"SELECT COUNT(*) FROM events WHERE type = 'alert' AND {_EV}")
        languages = conn.execute(f"SELECT language, COUNT(*) c FROM events WHERE type IN ('bill_read', 'question') "
                                 f"AND {_EV} GROUP BY language ORDER BY c DESC", args).fetchall()
        intents = conn.execute(f"SELECT intent, COUNT(*) c FROM events WHERE type = 'question' AND intent IS NOT NULL"
                               f" AND {_EV} GROUP BY intent ORDER BY c DESC LIMIT 8", args).fetchall()
        daily = conn.execute(
            # Days are India days, so an evening upload is not counted on the next UTC day.
            "SELECT date(ts, '+5 hours', '+30 minutes') d, SUM(type = 'bill_read'), SUM(type = 'question') FROM events "
            "WHERE ts >= date('now', :day) AND (:discom IS NULL OR discom = :discom) GROUP BY d ORDER BY d",
            args).fetchall()
        sections = conn.execute(
            f"SELECT section, COUNT(*), SUM(audit_status = 'mismatch'), ROUND(AVG(units)) FROM events "
            f"WHERE type = 'bill_read' AND section IS NOT NULL AND {_EV} GROUP BY section ORDER BY 2 DESC",
            args).fetchall()
        explained = dict(conn.execute(f"SELECT intent, COUNT(*) FROM events WHERE type = 'explain' AND {_EV} "
                                      "GROUP BY intent", args).fetchall())
        reads = _reads(conn, args)
        complaint_stats = _complaints(conn, args)
        week = _week(conn, discom)
    return {
        "days": days, "discom": discom,
        "bills_read": bills, "complaints": complaints, "overcharge_flagged": round(overcharge, 2),
        "questions": questions, "alerts": alerts,
        "audit": {row[0] or "unknown": row[1] for row in audit},
        "languages": [{"language": r[0] or "te", "count": r[1]} for r in languages],
        "intents": [{"intent": r[0], "count": r[1]} for r in intents],
        "daily": [{"date": r[0], "bills": r[1], "questions": r[2]} for r in daily],
        "sections": [{"section": r[0], "bills": r[1], "mismatches": r[2], "avg_units": r[3]} for r in sections],
        "reads": reads,
        "explanations": {k: explained.get(k, 0) for k in ("llm_pass", "llm_fallback", "template")},
        **complaint_stats,
        "week": week,
        "reply_days": get_settings().complaint_reply_days,
    }
