"""Auto-clear assurance tests (ADR-0019).

Two pure functions: `auto_clear_leakage` derives the false-negative leakage from the LOCKED
held-out aggregates (no eval re-run, no tokens — respects the ADR-0012 lock), and
`select_qa_sample` picks the risk-weighted QA sample among auto-cleared alerts.
"""

from __future__ import annotations

from assurance import auto_clear_leakage, is_borderline_dismiss, select_qa_sample


# --- auto_clear_leakage -------------------------------------------------------------

def test_leakage_derived_from_locked_aggregates():
    # The real locked metrics.json values (n=250): 106 auto-cleared, 60.38% benign -> 64 benign,
    # so 42 auto-cleared were true reports; 150 true reports (tp 108 + fn 42) -> 28% leakage.
    metrics = {
        "autoClearedShare": 0.424,
        "autoClearPrecision": 0.6038,
        "confusionMatrix": {"tp": 108, "fp": 36, "fn": 42, "tn": 64},
    }
    out = auto_clear_leakage(metrics)
    assert out["autoClearedReports"] == 42
    assert out["totalReports"] == 150
    assert out["autoClearLeakageRate"] == 0.28


def test_leakage_is_zero_when_no_reports_in_slice():
    metrics = {
        "autoClearedShare": 0.5,
        "autoClearPrecision": 1.0,
        "confusionMatrix": {"tp": 0, "fp": 0, "fn": 0, "tn": 10},
    }
    out = auto_clear_leakage(metrics)
    assert out["autoClearedReports"] == 0
    assert out["autoClearLeakageRate"] == 0.0


# --- select_qa_sample ---------------------------------------------------------------

def _alert(aid: str, routing: str, confidence: float, risk: int = 50) -> dict:
    return {"alertId": aid, "routing": routing, "riskScore": risk,
            "triage": {"confidence": confidence}}


def test_qa_sample_takes_the_lowest_confidence_auto_cleared_first():
    alerts = [
        _alert("A", "autoCleared", 0.86),
        _alert("B", "autoCleared", 0.99),
        _alert("C", "autoCleared", 0.90),
        _alert("D", "autoCleared", 1.0),
    ]
    # rate 0.5 of 4 -> 2, the two closest to the threshold
    assert select_qa_sample(alerts, 0.5) == {"A", "C"}


def test_qa_sample_ignores_non_auto_cleared_alerts():
    alerts = [
        _alert("A", "needsReview", 0.5),
        _alert("B", "autoCleared", 0.9),
    ]
    assert select_qa_sample(alerts, 0.5) == {"B"}


def test_qa_sample_always_takes_at_least_one_when_any_are_cleared():
    alerts = [_alert(a, "autoCleared", 0.95) for a in ("A", "B", "C")]
    # 0.2 * 3 = 0.6 -> ceil 1
    assert len(select_qa_sample(alerts, 0.2)) == 1


def test_qa_sample_tie_breaks_on_risk_then_id_deterministically():
    alerts = [
        _alert("A", "autoCleared", 0.90, risk=40),
        _alert("B", "autoCleared", 0.90, risk=80),  # same confidence, higher risk -> picked first
    ]
    assert select_qa_sample(alerts, 0.5) == {"B"}


def test_qa_sample_empty_when_nothing_auto_cleared():
    assert select_qa_sample([_alert("A", "needsReview", 0.5)], 0.5) == set()


# --- is_borderline_dismiss (review 0.6, margin 0.1 -> band 0.70) ---------------------

def _triage(rec: str, conf: float, verifier: str = "agreed", debate=None) -> dict:
    return {"recommendation": rec, "confidence": conf,
            "verifier": {"status": verifier}, "debate": debate}


def test_escalate_is_never_borderline():
    assert is_borderline_dismiss(_triage("escalate", 0.61), 0.6, 0.1) is False


def test_low_confidence_dismiss_is_borderline():
    assert is_borderline_dismiss(_triage("dismiss", 0.65), 0.6, 0.1) is True


def test_band_edge_is_inclusive():
    assert is_borderline_dismiss(_triage("dismiss", 0.70), 0.6, 0.1) is True


def test_confident_clean_dismiss_is_not_borderline():
    assert is_borderline_dismiss(_triage("dismiss", 1.0), 0.6, 0.1) is False


def test_flagged_dismiss_is_borderline_even_when_confident():
    assert is_borderline_dismiss(_triage("dismiss", 0.95, verifier="flagged"), 0.6, 0.1) is True


def test_debated_dismiss_is_borderline_even_when_confident():
    assert is_borderline_dismiss(_triage("dismiss", 0.95, debate={"reverdict": {}}), 0.6, 0.1) is True
