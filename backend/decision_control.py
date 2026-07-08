"""Deterministic decision control plane.

One interface owns VerdictAML's non-LLM safety policy: routing, suppression eligibility,
QA sample flags, borderline flags, blocked reasons, and auto-clear rationale. Callers should
ask this module for a control decision instead of re-implementing the gates locally.
"""

from __future__ import annotations

from dataclasses import dataclass

from agents.memory import envelope_benign_consistent
from assurance import is_borderline_dismiss, select_qa_sample


ROUTING_AUTO_CLEARED = "autoCleared"
ROUTING_NEEDS_REVIEW = "needsReview"


@dataclass(frozen=True)
class ControlDecision:
    routing: str
    eligible: bool
    qa_sampled: bool
    borderline_dismiss: bool
    blocked_reason: str | None
    reasons: list[str]
    suppression_applied: bool
    suppression_envelope_consistent: bool


class DecisionControlPlane:
    """Deep module for deterministic AML decision policy.

    The interface is intentionally small: pass an alert dict plus optional QA sample ids,
    receive the full control decision. The implementation hides the policy ordering:
    escalate/file gates stay human-owned, verifier/debate/screening gates override model
    confidence, and learned suppressions can only clear a benign-consistent borderline dismiss.
    """

    def __init__(
        self,
        *,
        auto_clear_threshold: float,
        review_threshold: float,
        qa_sample_rate: float,
        borderline_margin: float,
    ) -> None:
        self.auto_clear_threshold = auto_clear_threshold
        self.review_threshold = review_threshold
        self.qa_sample_rate = qa_sample_rate
        self.borderline_margin = borderline_margin

    def qa_sample_ids(self, alerts: list[dict]) -> set[str]:
        return select_qa_sample(alerts, self.qa_sample_rate)

    def route_decision(
        self,
        *,
        recommendation: str,
        confidence: float,
        verifier_status: str,
        debated: bool = False,
        screening_blocked: bool = False,
        suppressed: bool = False,
    ) -> str:
        triage = {
            "recommendation": recommendation,
            "confidence": confidence,
            "verifier": {"status": verifier_status},
            "debate": {} if debated else None,
            "screening": {"blocked": screening_blocked},
        }
        return self._route(triage, suppression_applied=suppressed)

    def route_triage(self, triage: dict) -> str:
        return self._route(
            triage,
            suppression_applied=False,
        )

    def evaluate_alert(self, alert: dict, *, qa_sample_ids: set[str] | None = None) -> ControlDecision:
        triage = alert["triage"]
        suppression_applied, envelope_consistent = self._suppression_state(alert)
        routing = self._route(triage, suppression_applied=suppression_applied)
        blocked_reason = None if routing == ROUTING_AUTO_CLEARED else self.blocked_reason_code(alert)
        return ControlDecision(
            routing=routing,
            eligible=routing == ROUTING_AUTO_CLEARED,
            qa_sampled=alert["alertId"] in (qa_sample_ids or set()),
            borderline_dismiss=is_borderline_dismiss(
                triage,
                self.review_threshold,
                self.borderline_margin,
            ),
            blocked_reason=blocked_reason,
            reasons=self.auto_clear_reasons(alert, routing=routing),
            suppression_applied=suppression_applied,
            suppression_envelope_consistent=envelope_consistent,
        )

    def evaluate_queue_item(
        self,
        alert_meta: dict,
        *,
        full_alert: dict | None = None,
        qa_sample_ids: set[str] | None = None,
    ) -> ControlDecision:
        """Evaluate a queue-list item.

        Queue rows omit transactions, so the learned-suppression envelope gate can only be
        evaluated when the caller provides a hydrated full alert. For non-borderline rows this
        returns the stored routing and still computes the rest of the control fields.
        """
        if self.requires_ledger_for_suppression(alert_meta) and full_alert is not None:
            return self.evaluate_alert(full_alert, qa_sample_ids=qa_sample_ids)

        triage = alert_meta["triage"]
        routing = alert_meta.get("routing") or self.route_triage(triage)
        blocked_reason = None if routing == ROUTING_AUTO_CLEARED else self.blocked_reason_code(alert_meta)
        return ControlDecision(
            routing=routing,
            eligible=routing == ROUTING_AUTO_CLEARED,
            qa_sampled=alert_meta["alertId"] in (qa_sample_ids or set()),
            borderline_dismiss=is_borderline_dismiss(
                triage,
                self.review_threshold,
                self.borderline_margin,
            ),
            blocked_reason=blocked_reason,
            reasons=self.auto_clear_reasons(alert_meta, routing=routing),
            suppression_applied=False,
            suppression_envelope_consistent=False,
        )

    def requires_ledger_for_suppression(self, alert_meta: dict) -> bool:
        triage = alert_meta["triage"]
        screening = triage.get("screening") or {}
        return (
            triage["recommendation"] == "dismiss"
            and triage["verifier"]["status"] == "agreed"
            and not triage.get("debate")
            and not screening.get("blocked")
            and self.review_threshold <= triage["confidence"] < self.auto_clear_threshold
        )

    def blocked_reason_code(self, alert: dict) -> str:
        triage = alert["triage"]
        screening = triage.get("screening") or {}
        suppression = triage.get("suppression") or {}
        if triage["recommendation"] == "escalate":
            return "escalation"
        if screening.get("blocked"):
            return "screeningHit"
        if triage.get("debate") is not None:
            return "adversarialDebate"
        if triage["verifier"]["status"] == "flagged":
            return "verifierFlagged"
        if suppression.get("status") == "revoked":
            return "revokedSuppression"
        if triage["recommendation"] == "dismiss":
            return "lowConfidenceDismiss"
        return "other"

    def auto_clear_reasons(self, alert: dict, *, routing: str | None = None) -> list[str]:
        triage = alert["triage"]
        screening = triage.get("screening") or {}
        suppression = triage.get("suppression") or {}
        routing = routing or self.evaluate_alert(alert).routing
        reasons: list[str] = []
        if triage["recommendation"] == "dismiss":
            reasons.append("AI recommendation is dismiss.")
        else:
            reasons.append("Blocked: AI recommendation is escalate; auto-clear never escalates.")
        if triage["verifier"]["status"] == "agreed":
            reasons.append("Verifier agreed with the recommendation.")
        else:
            reasons.append("Blocked: verifier flagged the recommendation.")
        if triage.get("debate"):
            reasons.append("Blocked: contested call entered adversarial debate.")
        if screening.get("blocked"):
            reasons.append("Blocked: sanctions/PEP screening matched a counterparty.")
        if triage["confidence"] >= self.auto_clear_threshold:
            reasons.append("Confidence meets the auto-clear threshold.")
        elif suppression.get("status") == "suppressed" and triage["confidence"] >= self.review_threshold:
            suppression_applied, envelope_consistent = self._suppression_state(alert)
            if suppression_applied:
                reasons.append("Learned suppression matched and confidence is above the human review threshold.")
            elif envelope_consistent:
                reasons.append("Blocked: learned suppression was present but not active.")
            else:
                reasons.append("Blocked: learned suppression matched, but the ledger envelope changed or is unavailable.")
        else:
            reasons.append("Blocked: confidence is below the auto-clear threshold.")
        if routing == ROUTING_AUTO_CLEARED:
            reasons.append("Final control-plane routing is autoCleared.")
        return reasons

    def _route(self, triage: dict, *, suppression_applied: bool) -> str:
        screening = triage.get("screening") or {}
        if triage.get("debate") is not None:
            return ROUTING_NEEDS_REVIEW
        if screening.get("blocked"):
            return ROUTING_NEEDS_REVIEW
        if triage["recommendation"] == "dismiss" and triage["verifier"]["status"] == "agreed":
            if triage["confidence"] >= self.auto_clear_threshold:
                return ROUTING_AUTO_CLEARED
            if suppression_applied and triage["confidence"] >= self.review_threshold:
                return ROUTING_AUTO_CLEARED
        return ROUTING_NEEDS_REVIEW

    def _suppression_state(self, alert: dict) -> tuple[bool, bool]:
        suppression = (alert["triage"].get("suppression") or {})
        envelope_consistent = envelope_benign_consistent(alert.get("transactions") or [])
        return (
            suppression.get("status") == "suppressed" and envelope_consistent,
            envelope_consistent,
        )
