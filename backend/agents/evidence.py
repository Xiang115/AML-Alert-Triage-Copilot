"""Evidence rendering: turn a domain object into the prompt-ready text the
Triage Agent reasons over. The seam between the two data worlds (ADR-0005) lives
here — demo/hero alerts (clean transactions) vs eval alerts (aggregated features).

`triage()` takes pre-rendered evidence (a str), so this module is the one place
the on-screen evidence format — including the `runningBalance` mule tell — is
decided, and the one place to test it.
"""

from __future__ import annotations

from schemas import AlertInput


def render_alert_evidence(alert: AlertInput) -> str:
    """Evidence block for a demo/hero alert (clean transactions)."""
    acct = alert.account
    lines = [
        f"Account: {acct.holder_name} ({acct.account_type}, opened {acct.opened_at})",
        f"Trigger: {alert.trigger}",
        "Transactions (id | time | dir | amount | counterparty | runningBalance):",
    ]
    for t in alert.transactions or []:
        lines.append(
            f"  {t.transaction_id} | {t.timestamp} | {t.direction} | "
            f"{t.amount} {t.currency} | {t.counterparty_name} | {t.running_balance}"
        )
    return "\n".join(lines)


def render_features_evidence(features: dict) -> str:
    """Evidence block for an eval alert (aggregated features, no transactions)."""
    return "Aggregated alert features:\n" + "\n".join(f"  {k}: {v}" for k, v in features.items())
