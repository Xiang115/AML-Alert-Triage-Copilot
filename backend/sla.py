"""STR filing-SLA clock — the BNM next-working-day deadline.

Malaysia's AML/CFT regime requires a reporting institution to submit a Suspicious
Transaction Report **within the next working day, from the date the compliance officer
establishes the suspicion** (BNM AML/CFT Policy Document; corroborated by the BNM-derived
Standard Guidelines and MIA, 2023). Two consequences shape this module:

- The clock runs from when *suspicion is established* — NOT the transaction date. In the app
  that is the analyst's escalate decision (a real GMT+8 timestamp), never the synthetic
  SAML-D `createdAt`. `filing_sla` therefore takes `established_at` (the decision time) and,
  before it exists, shows a *prospective* deadline computed from now.
- "Working day" excludes weekends and Malaysian public holidays. `next_working_day` takes the
  holiday set as an argument, so the rule is pure and unit-testable; the real calendar
  (`data/my_holidays.json`) is loaded once and injected at serve time.

This is a pure module: no I/O, no LLM. Computed serve-time in main.py, never persisted.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from timeutil import LOCAL_TZ, to_local

CITATION = (
    "BNM AML/CFT Policy Document — an STR must be submitted the next working day from when "
    "the compliance officer establishes the suspicion."
)


def next_working_day(start: date, holidays: set[date]) -> date:
    """The first calendar day strictly after `start` that is neither a weekend
    (Sat/Sun) nor a Malaysian public holiday in `holidays`."""
    d = start + timedelta(days=1)
    while d.weekday() >= 5 or d in holidays:
        d += timedelta(days=1)
    return d


def _end_of_day_local(d: date) -> datetime:
    """The filing deadline instant: end of the due working day, in GMT+8."""
    return datetime.combine(d, time(23, 59, 59), tzinfo=LOCAL_TZ)


def filing_sla(
    *,
    recommendation: str,
    final_disposition: str | None,
    established_at: datetime | None,
    now: datetime,
    holidays: set[date],
) -> dict:
    """The STR filing-SLA state for a served alert (camelCase, serialised as-is).

    - Dismissed (or a pending dismiss recommendation): no filing obligation.
    - Escalated decision: a live clock from the decision time to end of the next working day;
      `overdue` once that instant has passed, else `active`.
    - Pending escalate recommendation (not yet decided): a `prospective` deadline from now,
      i.e. "if you escalate today, the STR is due by <next working day>".
    """
    base = {"applicable": False, "state": "notApplicable",
            "establishedAt": None, "dueBy": None, "citation": CITATION}

    if final_disposition == "dismiss":
        return base

    if final_disposition == "escalate" and established_at is not None:
        established = to_local(established_at)
        due = next_working_day(established.date(), holidays)
        state = "overdue" if to_local(now) > _end_of_day_local(due) else "active"
        return {**base, "applicable": True, "state": state,
                "establishedAt": established.isoformat(), "dueBy": due.isoformat()}

    if final_disposition is None and recommendation == "escalate":
        due = next_working_day(to_local(now).date(), holidays)
        return {**base, "applicable": True, "state": "prospective", "dueBy": due.isoformat()}

    return base
