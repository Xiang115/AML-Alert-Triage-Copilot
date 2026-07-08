"""Finals readiness checks for the live demo.

Run from backend/ before rehearsal/finals:
    python -m readiness
    python -m readiness --base-url https://your-render-api.onrender.com

The local checks catch stale frontend fixtures and missing metric artifacts. The optional
endpoint checks catch the exact finals risk Christopher found: live /metrics or /governance
not reachable even though the README/deck says they are.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import urlopen


REPO = Path(__file__).resolve().parents[1]
BACKEND_DATA = REPO / "backend" / "data"
FRONTEND_FIXTURES = REPO / "frontend" / "src" / "fixtures"

FIXTURE_PAIRS = [
    ("results.json", "alerts.json"),
    ("metrics.json", "metrics.json"),
    ("typologies/typologies.json", "typologies.json"),
    ("evaluation.json", "evaluation.json"),
]

METRICS_KEYS = {
    "totalAlerts",
    "accuracyVsLabels",
    "baselineAccuracy",
    "recall",
    "precision",
    "specificity",
    "confusionMatrix",
    "autoClearedShare",
    "autoClearPrecision",
    "validatedAt",
    "model",
}

GOVERNANCE_KEYS = {"model", "thresholds", "validation", "override", "securityPosture"}
ACCESS_CONTROL_KEYS = {"mode", "demoFallbackActor", "rules", "fourEyesControls", "nonClaims"}
GOVERNANCE_CHANGE_KEYS = {"mode", "pending", "approved", "blockedReason", "changes"}
QA_OUTCOME_KEYS = {"reviewed", "confirmedClears", "missedSuspicion", "missRate", "outcomes"}
BRIEFING_KEYS = {
    "processed",
    "autoCleared",
    "needsReview",
    "escalations",
    "flagged",
    "blockedReasons",
    "nextActions",
    "summary",
}
DEFENSE_CASE_KEYS = {"alertId", "decisionContext", "evidence", "controls", "audit"}
CASE_HANDOFF_KEYS = {
    "alertId",
    "generatedAt",
    "sourceSystem",
    "targetSystems",
    "caseStatusUpdate",
    "caseNote",
    "decision",
    "attachments",
    "auditEvents",
    "writeBack",
    "nonClaims",
}
DECISION_TRACE_KEYS = {
    "alertId",
    "generatedAt",
    "currentRecommendation",
    "currentConfidence",
    "routing",
    "formula",
    "steps",
    "nonClaims",
}
COPILOT_LEDGER_KEYS = {
    "runId",
    "alertId",
    "mode",
    "provider",
    "model",
    "status",
    "startedAt",
    "promptVersion",
    "inputSnapshot",
    "retrieval",
    "llmCalls",
    "deterministicEvents",
    "finalOutput",
    "redactions",
    "nonClaims",
}
INTEGRATION_CONTRACT_KEYS = {
    "mode",
    "inboundSystems",
    "workflow",
    "minimumRequiredFields",
    "optionalEnrichments",
    "outboundArtifacts",
    "productionGates",
    "nonGoals",
}
VALIDATION_DOSSIER_KEYS = {
    "validatedAt",
    "model",
    "dataset",
    "n",
    "accuracyVsLabels",
    "baselineAccuracy",
    "baselineExplanation",
    "recall",
    "precision",
    "specificity",
    "confusionMatrix",
    "autoClearLeakageRate",
    "thresholds",
    "productionState",
    "releaseGates",
    "prohibitedActions",
}
FINALS_BUNDLE_KEYS = {
    "generatedAt",
    "claims",
    "readiness",
    "metrics",
    "governance",
    "accessControl",
    "governanceChangeControl",
    "qaOutcomeSummary",
    "operationalImpact",
    "validationDossier",
    "productionTrustPlan",
    "technicalArchitecture",
    "integrationContract",
    "pilotAdoptionPlan",
    "innovationDifferentiation",
    "demoScript",
    "qnaDefense",
    "heroDefenseCase",
    "heroCaseHandoff",
    "heroDecisionTrace",
    "heroCopilotLedger",
}
TECHNICAL_ARCHITECTURE_KEYS = {
    "mode",
    "thesis",
    "components",
    "flows",
    "dataHandling",
    "aiExecution",
    "reliabilityControls",
    "demoPath",
    "caveat",
}
OPERATIONAL_IMPACT_KEYS = {
    "mode",
    "processedAlerts",
    "autoClearedAlerts",
    "humanReviewAlerts",
    "qaSampleAlerts",
    "escalationsHeldForSignoff",
    "verifierFlagged",
    "baselineReviewMinutes",
    "assistedReviewMinutes",
    "minutesReturned",
    "analystHoursReturned",
    "queueReductionRate",
    "reviewFocusMultiplier",
    "assumptions",
    "controlChecks",
    "demoNarrative",
    "caveat",
}
PRODUCTION_TRUST_PLAN_KEYS = {
    "mode",
    "position",
    "targetSystems",
    "minimumDataAccess",
    "governanceControls",
    "validationGates",
    "items",
    "judgeResponse",
    "nonClaims",
}
PILOT_ADOPTION_PLAN_KEYS = {
    "mode",
    "targetSegments",
    "buyerStakeholders",
    "pilotEconomics",
    "sensitivityCases",
    "commercialModel",
    "competitivePositioning",
    "pilotTimeline",
    "phases",
    "successCriteria",
    "validationEvidence",
    "procurementRisks",
    "nonClaims",
}
INNOVATION_DIFFERENTIATION_KEYS = {"mode", "thesis", "capabilities", "nonClaims"}
QNA_DEFENSE_KEYS = {"mode", "primaryPosition", "answers", "closingLine"}
DEMO_SCRIPT_KEYS = {"mode", "openingLine", "totalMinutes", "steps", "fallbackMoves", "closingLine", "nonClaims"}


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def missing_keys(data: dict[str, Any], keys: set[str]) -> set[str]:
    return {k for k in keys if k not in data}


def auto_clear_leakage(metrics: dict[str, Any]) -> dict[str, Any] | None:
    if not {"autoClearedShare", "autoClearPrecision", "confusionMatrix"} <= metrics.keys():
        return None
    cm = metrics["confusionMatrix"]
    n = cm["tp"] + cm["fp"] + cm["fn"] + cm["tn"]
    auto_cleared = round(metrics["autoClearedShare"] * n)
    benign = round(metrics["autoClearPrecision"] * auto_cleared)
    leaked = max(0, auto_cleared - benign)
    total_reports = cm["tp"] + cm["fn"]
    return {
        "autoClearedReports": leaked,
        "totalReports": total_reports,
        "autoClearLeakageRate": round(leaked / total_reports, 4) if total_reports else 0.0,
    }


def validate_metrics_payload(metrics: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = missing_keys(metrics, METRICS_KEYS)
    if missing:
        errors.append(f"missing metrics keys: {sorted(missing)}")

    cm = metrics.get("confusionMatrix")
    if not isinstance(cm, dict) or missing_keys(cm, {"tp", "fp", "fn", "tn"}):
        errors.append("confusionMatrix must include tp/fp/fn/tn")
    elif metrics.get("totalAlerts") != cm["tp"] + cm["fp"] + cm["fn"] + cm["tn"]:
        errors.append("totalAlerts does not equal confusion matrix total")

    leak = auto_clear_leakage(metrics)
    if leak is None:
        errors.append("auto-clear leakage cannot be derived")
    elif leak["totalReports"] <= 0:
        errors.append("auto-clear leakage denominator is zero")

    return errors


def validate_governance_payload(governance: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = missing_keys(governance, GOVERNANCE_KEYS)
    if missing:
        errors.append(f"missing governance keys: {sorted(missing)}")
    validation = governance.get("validation") or {}
    for key in ("validatedAt", "model", "n", "recall", "autoClearLeakageRate"):
        if validation.get(key) is None:
            errors.append(f"governance.validation.{key} is missing")
    thresholds = governance.get("thresholds") or {}
    for key in ("review", "autoClear", "qaSample", "borderlineMargin"):
        if thresholds.get(key) is None:
            errors.append(f"governance.thresholds.{key} is missing")
    return errors


def validate_access_control_payload(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = missing_keys(packet, ACCESS_CONTROL_KEYS)
    if missing:
        errors.append(f"missing access-control keys: {sorted(missing)}")
    if packet.get("mode") != "actorRoleHeaders":
        errors.append("access-control.mode must be actorRoleHeaders")
    fallback = packet.get("demoFallbackActor") or {}
    if fallback.get("actorRole") != "admin" or fallback.get("source") != "demoFallback":
        errors.append("access-control demo fallback must be explicit admin demoFallback")
    rules = packet.get("rules") or []
    endpoints = {rule.get("endpoint"): rule for rule in rules}
    required = {
        "/alerts/{alert_id}/decision": {"analyst", "compliance", "admin"},
        "/alerts/{alert_id}/str/submit": {"compliance", "admin"},
        "/alerts/{alert_id}/qa-outcome": {"qa", "compliance", "admin"},
        "/governance/change-requests": {"modelRisk", "compliance", "security", "amlOps", "admin"},
        "/reset": {"admin"},
    }
    for endpoint, roles in required.items():
        rule = endpoints.get(endpoint)
        if not rule:
            errors.append(f"access-control missing rule for {endpoint}")
            continue
        if not roles <= set(rule.get("allowedRoles") or []):
            errors.append(f"access-control {endpoint} missing required roles")
        if not rule.get("control"):
            errors.append(f"access-control {endpoint} missing control narrative")
    four_eyes = " ".join(packet.get("fourEyesControls") or []).lower()
    if "str submission" not in four_eyes or "governance changes" not in four_eyes:
        errors.append("access-control four-eyes controls must mention STR submission and governance changes")
    non_claims = " ".join(packet.get("nonClaims") or []).lower()
    if "not production sso" not in non_claims or "oidc" not in non_claims:
        errors.append("access-control non-claims must distinguish actor headers from production SSO/OIDC")
    return errors


def validate_governance_change_payload(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = missing_keys(packet, GOVERNANCE_CHANGE_KEYS)
    if missing:
        errors.append(f"missing governance-change keys: {sorted(missing)}")
    if packet.get("mode") != "modelRiskChangeControl":
        errors.append("governance-change.mode must be modelRiskChangeControl")
    changes = packet.get("changes") or []
    if not changes:
        errors.append("governance-change.changes must not be empty")
    for change in changes:
        for key in ("changeId", "type", "status", "evidence", "requiredApprovals", "rollbackPlan", "nonClaims"):
            if not change.get(key):
                errors.append(f"governance-change item missing {key}")
                break
    text = " ".join(
        f"{change.get('rationale', '')} {' '.join(change.get('nonClaims') or [])}"
        for change in changes
    ).lower()
    if "does not mutate" not in text and "cannot move silently" not in text:
        errors.append("governance-change must state that proposals do not silently mutate runtime controls")
    return errors


def validate_qa_outcomes_payload(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = missing_keys(packet, QA_OUTCOME_KEYS)
    if missing:
        errors.append(f"missing qa-outcomes keys: {sorted(missing)}")
    reviewed = packet.get("reviewed", 0)
    confirmed = packet.get("confirmedClears", 0)
    missed = packet.get("missedSuspicion", 0)
    if reviewed != confirmed + missed:
        errors.append("qa-outcomes reviewed must equal confirmedClears + missedSuspicion")
    for outcome in packet.get("outcomes") or []:
        if outcome.get("outcome") not in {"confirmedClear", "missedSuspicion"}:
            errors.append("qa-outcomes outcome is invalid")
        if not outcome.get("evidenceEndpoints"):
            errors.append("qa-outcomes outcome must cite evidence endpoints")
    return errors


def validate_defense_case_payload(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = missing_keys(packet, DEFENSE_CASE_KEYS)
    if missing:
        errors.append(f"missing defense-case keys: {sorted(missing)}")
    evidence = packet.get("evidence") or {}
    for key in ("matchedTypology", "indicatorCoverage", "citedTransactionIds", "strAnchoring"):
        if key not in evidence:
            errors.append(f"defense-case.evidence.{key} is missing")
    controls = packet.get("controls") or {}
    for key in ("autoClearPolicy", "verifier", "strFiling"):
        if key not in controls:
            errors.append(f"defense-case.controls.{key} is missing")
    filing = controls.get("strFiling") or {}
    for key in ("requiresEscalateSignoff", "blocksUnanchoredGrounds", "xsdValidatedOnExport"):
        if filing.get(key) is not True:
            errors.append(f"defense-case.controls.strFiling.{key} must be true")
    auto_clear = controls.get("autoClearPolicy") or {}
    if not auto_clear.get("reasons"):
        errors.append("defense-case.controls.autoClearPolicy.reasons is empty")
    return errors


def validate_case_handoff_payload(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = missing_keys(packet, CASE_HANDOFF_KEYS)
    if missing:
        errors.append(f"missing case-handoff keys: {sorted(missing)}")
    if packet.get("caseStatusUpdate") not in {"needsReview", "autoCleared", "escalated", "dismissed", "filed"}:
        errors.append("case-handoff.caseStatusUpdate is invalid")
    decision = packet.get("decision") or {}
    for key in ("aiRecommendation", "confidence", "verifierStatus"):
        if decision.get(key) is None:
            errors.append(f"case-handoff.decision.{key} is missing")
    attachments = packet.get("attachments") or []
    endpoints = {a.get("endpoint") for a in attachments}
    if f"/alerts/{packet.get('alertId')}/defense-case" not in endpoints:
        errors.append("case-handoff must attach the per-alert defense case")
    if "/audit" not in endpoints:
        errors.append("case-handoff must attach the audit trail")
    write_back = packet.get("writeBack") or {}
    if write_back.get("requiresHumanDecision") is not True:
        errors.append("case-handoff.writeBack.requiresHumanDecision must be true")
    if write_back.get("mode") not in {"shadowOnly", "humanApprovedWriteback"}:
        errors.append("case-handoff.writeBack.mode is invalid")
    if not write_back.get("productionGate"):
        errors.append("case-handoff.writeBack.productionGate is missing")
    non_claims = packet.get("nonClaims") or []
    if not any("does not mutate" in claim for claim in non_claims):
        errors.append("case-handoff non-claims must state that demo write-back is read-only")
    return errors


def validate_decision_trace_payload(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = missing_keys(packet, DECISION_TRACE_KEYS)
    if missing:
        errors.append(f"missing decision-trace keys: {sorted(missing)}")
    if packet.get("currentRecommendation") not in {"escalate", "dismiss"}:
        errors.append("decision-trace.currentRecommendation is invalid")
    if packet.get("routing") not in {"autoCleared", "needsReview"}:
        errors.append("decision-trace.routing is invalid")
    steps = packet.get("steps") or []
    if len(steps) < 4:
        errors.append("decision-trace.steps must include evidence and gate steps")
    step_kinds = {step.get("step") for step in steps}
    for expected in ("confidenceComputation", "verifierGate", "routePolicy", "strFilingGate"):
        if expected not in step_kinds:
            errors.append(f"decision-trace must include {expected}")
    for step in steps:
        if not all(key in step for key in ("label", "inputs", "result", "evidenceIds", "deterministic")):
            errors.append("decision-trace steps must include label, inputs, result, evidenceIds, and deterministic")
            break
    non_claims = " ".join(packet.get("nonClaims") or []).lower()
    if "not deepseek chain-of-thought" not in non_claims or "does not rerun" not in non_claims:
        errors.append("decision-trace non-claims must reject chain-of-thought and LLM rerun claims")
    return errors


def validate_copilot_ledger_payload(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = missing_keys(packet, COPILOT_LEDGER_KEYS)
    if missing:
        errors.append(f"missing copilot-ledger keys: {sorted(missing)}")
    if packet.get("mode") not in {"precomputed", "live"}:
        errors.append("copilot-ledger.mode is invalid")
    if packet.get("status") not in {"completed", "fallback", "failed", "reconstructed"}:
        errors.append("copilot-ledger.status is invalid")
    calls = packet.get("llmCalls") or []
    if not calls:
        errors.append("copilot-ledger.llmCalls must not be empty")
    for call in calls:
        for key in ("stage", "templateId", "model", "responseModel", "attempt", "messages", "rawResponseHash", "schemaValid"):
            if key not in call:
                errors.append(f"copilot-ledger.llmCalls[] missing {key}")
                break
        for message in call.get("messages") or []:
            for key in ("role", "content", "contentHash", "redactionLevel"):
                if key not in message:
                    errors.append(f"copilot-ledger message missing {key}")
                    break
    if not packet.get("deterministicEvents"):
        errors.append("copilot-ledger.deterministicEvents must not be empty")
    non_claims = " ".join(packet.get("nonClaims") or []).lower()
    if "not deepseek chain-of-thought" not in non_claims or "prompt/response envelope" not in non_claims:
        errors.append("copilot-ledger non-claims must separate prompt envelope from chain-of-thought")
    return errors


def validate_integration_contract_payload(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = missing_keys(contract, INTEGRATION_CONTRACT_KEYS)
    if missing:
        errors.append(f"missing integration-contract keys: {sorted(missing)}")
    if contract.get("mode") != "shadowFirst":
        errors.append("integration-contract.mode must be shadowFirst")
    required = contract.get("minimumRequiredFields") or []
    required_names = {f.get("name") for f in required if f.get("required") is True}
    for key in ("alertId", "riskScore", "running balance"):
        if key not in required_names:
            errors.append(f"integration-contract missing required field {key}")
    artifacts = contract.get("outboundArtifacts") or []
    if not any("defense-case" in a for a in artifacts):
        errors.append("integration-contract must expose defense-case output")
    gates = contract.get("productionGates") or []
    if not any("historical replay" in g for g in gates):
        errors.append("integration-contract must require historical replay")
    return errors


def validate_validation_dossier_payload(dossier: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = missing_keys(dossier, VALIDATION_DOSSIER_KEYS)
    if missing:
        errors.append(f"missing validation-dossier keys: {sorted(missing)}")
    if dossier.get("productionState") != "shadowOnly":
        errors.append("validation-dossier.productionState must be shadowOnly")
    if "catches zero reportable cases" not in (dossier.get("baselineExplanation") or ""):
        errors.append("validation-dossier baseline explanation must state zero reportable cases")
    thresholds = dossier.get("thresholds") or {}
    for key in ("review", "autoClear", "qaSample", "borderlineMargin"):
        if thresholds.get(key) is None:
            errors.append(f"validation-dossier.thresholds.{key} is missing")
    gates = dossier.get("releaseGates") or []
    if not any("Historical replay" in g for g in gates):
        errors.append("validation-dossier must require historical replay")
    prohibited = dossier.get("prohibitedActions") or []
    if not any("auto-filing" in a for a in prohibited):
        errors.append("validation-dossier must prohibit auto-filing")
    return errors


def validate_finals_evidence_bundle_payload(bundle: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = missing_keys(bundle, FINALS_BUNDLE_KEYS)
    if missing:
        errors.append(f"missing finals-evidence-bundle keys: {sorted(missing)}")

    errors.extend(f"bundle.metrics: {e}" for e in validate_metrics_payload(bundle.get("metrics") or {}))
    errors.extend(f"bundle.governance: {e}" for e in validate_governance_payload(bundle.get("governance") or {}))
    errors.extend(
        f"bundle.accessControl: {e}"
        for e in validate_access_control_payload(bundle.get("accessControl") or {})
    )
    errors.extend(
        f"bundle.governanceChangeControl: {e}"
        for e in validate_governance_change_payload(bundle.get("governanceChangeControl") or {})
    )
    errors.extend(
        f"bundle.qaOutcomeSummary: {e}"
        for e in validate_qa_outcomes_payload(bundle.get("qaOutcomeSummary") or {})
    )
    errors.extend(
        f"bundle.operationalImpact: {e}"
        for e in validate_operational_impact_payload(bundle.get("operationalImpact") or {})
    )
    errors.extend(
        f"bundle.validationDossier: {e}"
        for e in validate_validation_dossier_payload(bundle.get("validationDossier") or {})
    )
    errors.extend(
        f"bundle.productionTrustPlan: {e}"
        for e in validate_production_trust_plan_payload(bundle.get("productionTrustPlan") or {})
    )
    errors.extend(
        f"bundle.technicalArchitecture: {e}"
        for e in validate_technical_architecture_payload(bundle.get("technicalArchitecture") or {})
    )
    errors.extend(
        f"bundle.integrationContract: {e}"
        for e in validate_integration_contract_payload(bundle.get("integrationContract") or {})
    )
    errors.extend(
        f"bundle.pilotAdoptionPlan: {e}"
        for e in validate_pilot_adoption_plan_payload(bundle.get("pilotAdoptionPlan") or {})
    )
    errors.extend(
        f"bundle.innovationDifferentiation: {e}"
        for e in validate_innovation_differentiation_payload(bundle.get("innovationDifferentiation") or {})
    )
    errors.extend(
        f"bundle.demoScript: {e}"
        for e in validate_finals_demo_script_payload(bundle.get("demoScript") or {})
    )
    errors.extend(
        f"bundle.qnaDefense: {e}"
        for e in validate_qna_defense_payload(bundle.get("qnaDefense") or {})
    )
    errors.extend(
        f"bundle.heroDefenseCase: {e}"
        for e in validate_defense_case_payload(bundle.get("heroDefenseCase") or {})
    )
    errors.extend(
        f"bundle.heroCaseHandoff: {e}"
        for e in validate_case_handoff_payload(bundle.get("heroCaseHandoff") or {})
    )
    errors.extend(
        f"bundle.heroDecisionTrace: {e}"
        for e in validate_decision_trace_payload(bundle.get("heroDecisionTrace") or {})
    )
    errors.extend(
        f"bundle.heroCopilotLedger: {e}"
        for e in validate_copilot_ledger_payload(bundle.get("heroCopilotLedger") or {})
    )

    readiness = bundle.get("readiness") or {}
    if readiness.get("status") != "pass":
        errors.append("bundle.readiness.status must be pass")

    backed_by = {
        endpoint
        for claim in bundle.get("claims") or []
        for endpoint in claim.get("backedBy", [])
    }
    for endpoint in (
        "/metrics",
        "/governance/validation-dossier",
        "/production/trust-plan",
        "/operations/impact",
        "/architecture/technical",
        "/integration/contract",
        "/alerts/HERO-002/case-handoff",
        "/alerts/HERO-002/decision-trace",
        "/alerts/HERO-002/copilot-runs/precomputed-current/ledger",
        "/security/access-control",
        "/pilot/adoption-plan",
        "/innovation/differentiation",
        "/finals/demo-script",
        "/finals/qna-defense",
        "/alerts/HERO-002/defense-case",
        "/readiness/summary",
        "/governance/change-requests",
        "/qa/outcomes",
    ):
        if endpoint not in backed_by:
            errors.append(f"bundle claims must cite {endpoint}")
    claims_text = " ".join(
        f"{claim.get('claim', '')} {claim.get('caveat', '')}"
        for claim in bundle.get("claims") or []
    ).lower()
    if "pilot economics" not in claims_text or "not a production claim" not in claims_text:
        errors.append("bundle claims must frame pilot economics as not a production claim")
    return errors


def validate_production_trust_plan_payload(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = missing_keys(plan, PRODUCTION_TRUST_PLAN_KEYS)
    if missing:
        errors.append(f"missing production-trust-plan keys: {sorted(missing)}")
    if plan.get("mode") != "productionTrustPlan":
        errors.append("production-trust-plan.mode must be productionTrustPlan")

    systems = " ".join(plan.get("targetSystems") or []).lower()
    for expected in ("actimize", "mantas", "sas", "case-management", "goaml"):
        if expected not in systems:
            errors.append(f"production-trust-plan target systems must mention {expected}")

    data = " ".join(plan.get("minimumDataAccess") or []).lower()
    for expected in ("transaction id", "running balance", "screening", "analyst disposition", "str/no-str"):
        if expected not in data:
            errors.append(f"production-trust-plan minimum data must mention {expected}")

    controls = " ".join(plan.get("governanceControls") or []).lower()
    for expected in ("verifier", "qa", "leakage", "override", "screening"):
        if expected not in controls:
            errors.append(f"production-trust-plan controls must mention {expected}")

    gates = " ".join(plan.get("validationGates") or []).lower()
    for expected in ("historical replay", "shadow pilot", "model-risk", "rollback"):
        if expected not in gates:
            errors.append(f"production-trust-plan validation gates must mention {expected}")

    items = plan.get("items") or []
    areas = {item.get("area") for item in items}
    for expected in ("integration", "dataAccess", "falsePositiveGovernance", "validation", "productionGate"):
        if expected not in areas:
            errors.append(f"production-trust-plan missing {expected} item")
    for item in items:
        for key in ("requirement", "implementation", "evidenceEndpoints", "productionGate"):
            if not item.get(key):
                errors.append(f"production-trust-plan item {item.get('area', '<unknown>')} missing {key}")

    judge_response = str(plan.get("judgeResponse", "")).lower()
    if "should not trust" not in judge_response or "shadow pilot" not in judge_response:
        errors.append("production-trust-plan judge response must reject demo trust and require shadow pilot")

    non_claims = " ".join(plan.get("nonClaims") or []).lower()
    for expected in ("synthetic", "autonomous str", "source detector", "threshold"):
        if expected not in non_claims:
            errors.append(f"production-trust-plan non-claims must mention {expected}")
    return errors


def validate_technical_architecture_payload(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = missing_keys(packet, TECHNICAL_ARCHITECTURE_KEYS)
    if missing:
        errors.append(f"missing technical-architecture keys: {sorted(missing)}")
    if packet.get("mode") != "technicalArchitecture":
        errors.append("technical-architecture.mode must be technicalArchitecture")
    components = packet.get("components") or []
    if len(components) < 6:
        errors.append("technical-architecture must list at least six components")
    component_ids = {component.get("id") for component in components}
    for expected in ("bank-monitoring", "api-store", "queue-agent", "triage-agents", "control-plane", "analyst-ui"):
        if expected not in component_ids:
            errors.append(f"technical-architecture missing component {expected}")
    flows = packet.get("flows") or []
    if len(flows) < 5:
        errors.append("technical-architecture must list at least five flows")
    for flow in flows:
        if not all(flow.get(key) for key in ("source", "target", "payload", "control")):
            errors.append("technical-architecture flows must include source, target, payload, and control")
    controls = " ".join(packet.get("reliabilityControls") or []).lower()
    for expected in ("readiness", "auto-clear", "str"):
        if expected not in controls:
            errors.append(f"technical-architecture controls must mention {expected}")
    data_handling = " ".join(packet.get("dataHandling") or []).lower()
    if "read-only" not in data_handling:
        errors.append("technical-architecture data handling must mention read-only pilot/replay")
    demo_path = " ".join(packet.get("demoPath") or []).lower()
    if "technical architecture" not in demo_path or "evidence bundle" not in demo_path:
        errors.append("technical-architecture demo path must mention architecture and evidence bundle")
    return errors


def validate_operational_impact_payload(impact: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = missing_keys(impact, OPERATIONAL_IMPACT_KEYS)
    if missing:
        errors.append(f"missing operational-impact keys: {sorted(missing)}")
    if impact.get("mode") != "shiftImpact":
        errors.append("operational-impact.mode must be shiftImpact")
    processed = impact.get("processedAlerts", 0)
    auto_cleared = impact.get("autoClearedAlerts", 0)
    human_review = impact.get("humanReviewAlerts", 0)
    if processed != auto_cleared + human_review:
        errors.append("operational-impact processed alerts must equal auto-cleared plus human-review alerts")
    if impact.get("minutesReturned", 0) <= 0:
        errors.append("operational-impact must show positive minutes returned")
    if not 0 <= impact.get("queueReductionRate", -1) <= 1:
        errors.append("operational-impact.queueReductionRate must be between 0 and 1")
    controls = " ".join(impact.get("controlChecks") or []).lower()
    for expected in ("escalations", "qa", "historical replay"):
        if expected not in controls:
            errors.append(f"operational-impact controls must mention {expected}")
    caveat = str(impact.get("caveat", "")).lower()
    if "not a production roi claim" not in caveat:
        errors.append("operational-impact caveat must reject production ROI claim")
    return errors


def validate_pilot_adoption_plan_payload(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = missing_keys(plan, PILOT_ADOPTION_PLAN_KEYS)
    if missing:
        errors.append(f"missing pilot-adoption-plan keys: {sorted(missing)}")
    if plan.get("mode") != "bankPilot":
        errors.append("pilot-adoption-plan.mode must be bankPilot")

    stakeholders = plan.get("buyerStakeholders") or []
    for expected in ("Compliance", "Model risk", "Information security", "Procurement"):
        if not any(expected.lower() in s.lower() for s in stakeholders):
            errors.append(f"pilot-adoption-plan must name {expected} stakeholder")

    economics = plan.get("pilotEconomics") or {}
    for key in (
        "monthlyAlerts",
        "currentReviewMinutesPerAlert",
        "assistedReviewMinutesPerAlert",
        "estimatedMonthlyHoursSaved",
        "valueHypothesis",
        "caveat",
    ):
        if key not in economics:
            errors.append(f"pilot-adoption-plan.pilotEconomics missing {key}")
    if economics.get("estimatedMonthlyHoursSaved", 0) <= 0:
        errors.append("pilot-adoption-plan.pilotEconomics must show positive hours saved")
    if "not a production claim" not in str(economics.get("caveat", "")).lower():
        errors.append("pilot-adoption-plan.pilotEconomics caveat must reject production claim")

    target_segments = " ".join(plan.get("targetSegments") or []).lower()
    if "malaysia" not in target_segments and "apac" not in target_segments:
        errors.append("pilot-adoption-plan must name a Malaysia/APAC beachhead segment")

    sensitivity = plan.get("sensitivityCases") or []
    if len(sensitivity) < 3:
        errors.append("pilot-adoption-plan must include at least three sensitivity cases")
    elif not all(case.get("estimatedMonthlyHoursReturned", 0) > 0 for case in sensitivity):
        errors.append("pilot-adoption-plan sensitivity cases must show positive hours returned")

    tiers = plan.get("commercialModel") or []
    tier_names = " ".join(t.get("name", "") for t in tiers).lower()
    for expected in ("pilot", "production", "automation"):
        if expected not in tier_names:
            errors.append(f"pilot-adoption-plan commercial model missing {expected} tier")

    positioning = " ".join(plan.get("competitivePositioning") or []).lower()
    if "overlay" not in positioning or "not a replacement" not in positioning:
        errors.append("pilot-adoption-plan positioning must state overlay / not replacement")

    timeline = plan.get("pilotTimeline") or []
    if len(timeline) < 4:
        errors.append("pilot-adoption-plan must include a four-step pilot timeline")
    elif "week 8" not in " ".join(step.get("week", "").lower() for step in timeline):
        errors.append("pilot-adoption-plan timeline must end with week 8 decision")

    phases = plan.get("phases") or []
    phase_names = {p.get("name", "").lower() for p in phases}
    for expected in ("historical replay", "security", "shadow pilot", "limited production"):
        if not any(expected in name for name in phase_names):
            errors.append(f"pilot-adoption-plan missing {expected} phase")

    success = plan.get("successCriteria") or []
    if not any("leakage" in s.lower() for s in success):
        errors.append("pilot-adoption-plan success criteria must include leakage")

    risks = plan.get("procurementRisks") or []
    if not any("months" in r.lower() for r in risks):
        errors.append("pilot-adoption-plan must state procurement can take months")

    non_claims = plan.get("nonClaims") or []
    if not any("immediate annual contract" in n.lower() for n in non_claims):
        errors.append("pilot-adoption-plan must reject immediate annual contract claim")
    return errors


def validate_innovation_differentiation_payload(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = missing_keys(packet, INNOVATION_DIFFERENTIATION_KEYS)
    if missing:
        errors.append(f"missing innovation-differentiation keys: {sorted(missing)}")
    if packet.get("mode") != "evidenceBackedDifferentiation":
        errors.append("innovation-differentiation.mode must be evidenceBackedDifferentiation")

    capabilities = packet.get("capabilities") or []
    if len(capabilities) < 5:
        errors.append("innovation-differentiation must list at least five built capabilities")
    names = " ".join(str(c.get("name", "")) for c in capabilities).lower()
    for expected in ("verifier", "goaml", "mule", "defense", "shadow"):
        if expected not in names:
            errors.append(f"innovation-differentiation missing {expected} capability")
    for capability in capabilities:
        for key in ("genericAlternative", "verdictamlImplementation", "proofEndpoints", "defenseValue", "limitation"):
            if not capability.get(key):
                errors.append(f"innovation-differentiation capability {capability.get('name', '<unnamed>')} missing {key}")
    proof_endpoints = {
        endpoint
        for capability in capabilities
        for endpoint in capability.get("proofEndpoints", [])
    }
    for endpoint in ("/alerts/HERO-002/defense-case", "/governance/validation-dossier", "/pilot/adoption-plan"):
        if endpoint not in proof_endpoints:
            errors.append(f"innovation-differentiation proof endpoints must include {endpoint}")
    non_claims = packet.get("nonClaims") or []
    if not any("not novelty by llm usage alone" in n.lower() for n in non_claims):
        errors.append("innovation-differentiation must reject LLM-usage-only novelty")
    return errors


def validate_qna_defense_payload(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = missing_keys(packet, QNA_DEFENSE_KEYS)
    if missing:
        errors.append(f"missing qna-defense keys: {sorted(missing)}")
    if packet.get("mode") != "judgeDefense":
        errors.append("qna-defense.mode must be judgeDefense")

    answers = packet.get("answers") or []
    if len(answers) < 6:
        errors.append("qna-defense must cover at least six likely judge objections")
    objections = " ".join(str(answer.get("objection", "")) for answer in answers).lower()
    for expected in ("auto-clear", "metrics", "integration", "innovation", "procurement", "live"):
        if expected not in objections:
            errors.append(f"qna-defense missing {expected} objection")
    for answer in answers:
        for key in ("shortAnswer", "evidenceEndpoints", "demoAction", "trapToAvoid"):
            if not answer.get(key):
                errors.append(f"qna-defense answer {answer.get('objection', '<unnamed>')} missing {key}")
    answer_text = " ".join(
        f"{answer.get('objection', '')} {answer.get('shortAnswer', '')} {answer.get('demoAction', '')}"
        for answer in answers
    ).lower()
    if "pilot economics" not in answer_text or "not a production claim" not in answer_text:
        errors.append("qna-defense must answer commercial viability with pilot economics caveat")
    evidence_endpoints = {
        endpoint
        for answer in answers
        for endpoint in answer.get("evidenceEndpoints", [])
    }
    for endpoint in (
        "/metrics",
        "/governance/validation-dossier",
        "/integration/contract",
        "/production/trust-plan",
        "/innovation/differentiation",
        "/pilot/adoption-plan",
        "/readiness/summary",
    ):
        if endpoint not in evidence_endpoints:
            errors.append(f"qna-defense evidence endpoints must include {endpoint}")
    traps = " ".join(str(answer.get("trapToAvoid", "")) for answer in answers).lower()
    if "do not" not in traps and "don't" not in traps:
        errors.append("qna-defense traps must include explicit do-not-claim guidance")
    return errors


def validate_finals_demo_script_payload(script: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = missing_keys(script, DEMO_SCRIPT_KEYS)
    if missing:
        errors.append(f"missing finals-demo-script keys: {sorted(missing)}")
    if script.get("mode") != "finalsDemo":
        errors.append("finals-demo-script.mode must be finalsDemo")
    if script.get("totalMinutes", 0) > 8:
        errors.append("finals-demo-script totalMinutes must fit an 8-minute finals demo")
    steps = script.get("steps") or []
    if len(steps) < 5:
        errors.append("finals-demo-script must contain at least five steps")
    step_text = " ".join(
        f"{step.get('title', '')} {step.get('objective', '')} {step.get('action', '')} {step.get('judgeTakeaway', '')}"
        for step in steps
    ).lower()
    for expected in ("operational", "architecture", "queue", "defense", "validation", "adoption"):
        if expected not in step_text:
            errors.append(f"finals-demo-script missing {expected} demo beat")
    endpoints = {
        endpoint
        for step in steps
        for endpoint in step.get("evidenceEndpoints", [])
    }
    for endpoint in ("/operations/impact", "/architecture/technical", "/alerts/HERO-002/defense-case", "/readiness/summary"):
        if endpoint not in endpoints:
            errors.append(f"finals-demo-script evidence endpoints must include {endpoint}")
    if not all(step.get("fallback") for step in steps):
        errors.append("finals-demo-script every step must include a fallback")
    fallback_text = " ".join(script.get("fallbackMoves") or []).lower()
    if "precomputed" not in fallback_text or "readiness" not in fallback_text:
        errors.append("finals-demo-script fallback moves must cover precomputed path and readiness")
    non_claims = " ".join(script.get("nonClaims") or []).lower()
    if "production auto-clear" not in non_claims or "autonomous str" not in non_claims:
        errors.append("finals-demo-script non-claims must cover production auto-clear and autonomous STR")
    return errors


def check_local_artifacts(repo: Path = REPO) -> list[CheckResult]:
    data = repo / "backend" / "data"
    fixtures = repo / "frontend" / "src" / "fixtures"
    out: list[CheckResult] = []

    metrics_path = data / "metrics.json"
    if metrics_path.exists():
        errors = validate_metrics_payload(load_json(metrics_path))
        out.append(CheckResult("local metrics contract", not errors, "; ".join(errors) or "metrics.json carries finals fields"))
    else:
        out.append(CheckResult("local metrics contract", False, "backend/data/metrics.json missing"))

    for backend_name, fixture_name in FIXTURE_PAIRS:
        src = data / backend_name
        dst = fixtures / fixture_name
        if not src.exists() or not dst.exists():
            out.append(CheckResult(f"fixture sync {fixture_name}", False, f"missing {src} or {dst}"))
            continue
        same = load_json(src) == load_json(dst)
        detail = "in sync" if same else f"drifted from data/{backend_name}; run python -m data.sync_fixtures"
        out.append(CheckResult(f"fixture sync {fixture_name}", same, detail))

    return out


def fetch_json(base_url: str, path: str, timeout: float = 10.0) -> dict[str, Any]:
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    with urlopen(url, timeout=timeout) as response:  # nosec B310 - explicit operator-provided URL
        if response.status != 200:
            raise RuntimeError(f"{path} returned HTTP {response.status}")
        return json.loads(response.read().decode("utf-8"))


def check_live_endpoints(base_url: str) -> list[CheckResult]:
    out: list[CheckResult] = []

    endpoint_specs = [
        ("/health", lambda d: [] if d.get("status") == "ok" and d.get("alertsLoaded", 0) > 0 else ["health not ready"]),
        ("/metrics", validate_metrics_payload),
        ("/governance", validate_governance_payload),
        ("/security/access-control", validate_access_control_payload),
        ("/governance/change-requests", validate_governance_change_payload),
        ("/qa/outcomes", validate_qa_outcomes_payload),
        ("/queue/briefing", lambda d: [f"missing briefing keys: {sorted(missing_keys(d, BRIEFING_KEYS))}"] if missing_keys(d, BRIEFING_KEYS) else []),
        ("/alerts/HERO-002/defense-case", validate_defense_case_payload),
        ("/alerts/HERO-002/case-handoff", validate_case_handoff_payload),
        ("/alerts/HERO-002/decision-trace", validate_decision_trace_payload),
        ("/alerts/HERO-002/copilot-runs/precomputed-current/ledger", validate_copilot_ledger_payload),
        ("/operations/impact", validate_operational_impact_payload),
        ("/architecture/technical", validate_technical_architecture_payload),
        ("/integration/contract", validate_integration_contract_payload),
        ("/production/trust-plan", validate_production_trust_plan_payload),
        ("/pilot/adoption-plan", validate_pilot_adoption_plan_payload),
        ("/innovation/differentiation", validate_innovation_differentiation_payload),
        ("/finals/demo-script", validate_finals_demo_script_payload),
        ("/finals/qna-defense", validate_qna_defense_payload),
        ("/governance/validation-dossier", validate_validation_dossier_payload),
        ("/finals/evidence-bundle", validate_finals_evidence_bundle_payload),
    ]

    for path, validator in endpoint_specs:
        try:
            payload = fetch_json(base_url, path)
            errors = validator(payload)
            out.append(CheckResult(f"live {path}", not errors, "; ".join(errors) or "ok"))
        except (HTTPError, URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
            out.append(CheckResult(f"live {path}", False, str(exc)))

    return out


def run_checks(base_url: str | None = None, repo: Path = REPO) -> list[CheckResult]:
    checks = check_local_artifacts(repo)
    if base_url:
        checks.extend(check_live_endpoints(base_url))
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run finals readiness checks.")
    parser.add_argument("--base-url", help="Optional live API base URL, e.g. https://...onrender.com")
    args = parser.parse_args(argv)

    checks = run_checks(args.base_url)
    for c in checks:
        mark = "PASS" if c.ok else "FAIL"
        print(f"[{mark}] {c.name}: {c.detail}")

    return 0 if all(c.ok for c in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
