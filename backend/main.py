"""FastAPI serving layer (PIPELINE Phase 7).

Loads the precomputed `results.json` on startup and serves it from memory, so the
filmed demo never waits on an LLM (CLAUDE.md > Architecture). The single live
endpoint, POST /alerts/{id}/triage, re-runs the pipeline for Q&A only: it returns
a fresh result WITHOUT mutating the precomputed demo source, and falls back to the
precomputed triage if the provider hiccups (ADR-0003).

Run from /backend:  python -m uvicorn main:app --reload
(use `python -m uvicorn`, not bare `uvicorn` — Windows Application Control blocks the
unsigned uvicorn.exe shim in .venv\\Scripts\\.)
"""

from __future__ import annotations

import json
import logging
import hashlib
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse

import config
import store
from activity_profile import compute_activity_profile
from agents.evidence import render_alert_evidence
from agents.knowledge_base import rank_cards, select_cards
from agents.pipeline import enrich_served_alert, run_triage, run_triage_events
from agents.memory import envelope_benign_consistent, signature as memory_signature
from assurance import auto_clear_leakage
from decision_control import DecisionControlPlane
from sla import filing_sla
from timeutil import now_local
from decision import final_disposition_for, learn_from_decision, resolve_str_draft
from goaml import GoamlConfig, submission_reference, to_goaml_str_xml
from schemas import (
    AccountActivityProfile,
    AccessControlPosture,
    AccessControlRule,
    Alert,
    Actor,
    ActorRole,
    AuditEntry,
    ArchitectureComponent,
    ArchitectureFlow,
    BankIntegrationContract,
    CamelModel,
    CaseHandoff,
    CopilotRunLedger,
    CopilotRunList,
    Decision,
    DecisionTrace,
    DefenseCase,
    DifferentiatedCapability,
    DecisionSummary,
    EvidenceClaim,
    FilingSla,
    FinalsDemoScript,
    FinalsDemoStep,
    FinalsEvidenceBundle,
    FinalsQADefensePacket,
    Governance,
    GovernanceChangeRequest,
    GovernanceChangeRequestList,
    GovernanceModel,
    GovernanceOverride,
    GovernanceThresholds,
    GovernanceValidation,
    InnovationDifferentiation,
    Metrics,
    MuleNetwork,
    OperationalImpact,
    PilotAdoptionPlan,
    ProductionTrustItem,
    ProductionTrustPlan,
    QAOutcome,
    QAOutcomeRequest,
    QAOutcomeSummary,
    ReadinessCheck,
    ReadinessSummary,
    ShiftBriefing,
    STRDraft,
    SubmissionAck,
    SuppressionFrontier,
    SuppressionPoint,
    TechnicalArchitecture,
    ValidationDossier,
    JudgeDefenseAnswer,
)
from llm import begin_run_capture, finish_run_capture
from readiness import (
    validate_defense_case_payload,
    validate_case_handoff_payload,
    validate_copilot_ledger_payload,
    validate_decision_trace_payload,
    validate_access_control_payload,
    validate_governance_change_payload,
    validate_governance_payload,
    validate_integration_contract_payload,
    validate_finals_evidence_bundle_payload,
    validate_finals_demo_script_payload,
    validate_innovation_differentiation_payload,
    validate_metrics_payload,
    validate_operational_impact_payload,
    validate_pilot_adoption_plan_payload,
    validate_production_trust_plan_payload,
    validate_qa_outcomes_payload,
    validate_qna_defense_payload,
    validate_technical_architecture_payload,
    validate_validation_dossier_payload,
    missing_keys,
    BRIEFING_KEYS,
)

# Security posture (ADR-0020) — honest current-state + roadmap for the governance panel.
_SECURITY_POSTURE = [
    "Mutating endpoints require an actor role envelope (`X-Actor-Id`, `X-Actor-Role`) with a documented demo fallback; production swaps this seam for OIDC/JWT claims.",
    "Analyst decisions, QA outcomes, governance changes, resets, and STR filing are role-gated and actor-attributed in audit events.",
    "Roadmap: PII minimisation — customer identifiers tokenised before any LLM call; the on-prem model swap (Slice B) keeps customer data in-bank.",
    "Roadmap: prompt-injection defence — evidence is structured, never free-text from counterparties; model output is schema-validated and figure/citation-anchored (ADR-0013).",
]

_INTEGRATION_WORKFLOW = [
    {
        "title": "Existing monitoring",
        "body": "SAS / Actimize / Mantas / bank rule engine emits alert id, account, trigger, risk score, and transaction window.",
    },
    {
        "title": "VerdictAML shadow triage",
        "body": "Runs read-only first; triage, verifier, confidence, screening, defense packet, and queue routing are computed without changing the source workflow.",
    },
    {
        "title": "Case-management worklist",
        "body": "needsReview goes to analyst queue; autoCleared remains inspectable, QA-sampled, and logged.",
    },
    {
        "title": "Analyst decision",
        "body": "Human accepts or overrides the AI recommendation. Escalations keep the STR draft; dismissals keep a dismissal record.",
    },
    {
        "title": "goAML filing seam",
        "body": "Approved STR exports as schema-valid goAML XML; filing returns FIU acknowledgement and audit event.",
    },
]

_MINIMUM_INTEGRATION_FIELDS = [
    {
        "name": "alertId",
        "required": True,
        "source": "transaction-monitoring system",
        "reason": "Stable key to reconcile VerdictAML output with the bank case.",
    },
    {
        "name": "trigger / originatingRule",
        "required": True,
        "source": "transaction-monitoring system",
        "reason": "Explains why the source system generated the alert.",
    },
    {
        "name": "riskScore",
        "required": True,
        "source": "transaction-monitoring system",
        "reason": "Preserves the bank's existing risk signal for queue prioritisation and audit.",
    },
    {
        "name": "subject account id, type, opening date",
        "required": True,
        "source": "core banking / case-management system",
        "reason": "Identifies the reviewed account without needing broad customer PII.",
    },
    {
        "name": "transaction id, timestamp, direction, amount, currency",
        "required": True,
        "source": "ledger / alert transaction window",
        "reason": "Grounds typology indicators, cited transactions, and STR amounts.",
    },
    {
        "name": "counterparty name, account, bank, channel",
        "required": True,
        "source": "ledger / payment rails",
        "reason": "Supports counterparty concentration, screening, and money-flow explanation.",
    },
    {
        "name": "running balance",
        "required": True,
        "source": "ledger",
        "reason": "Supports pass-through and balance-drain evidence without inventing figures.",
    },
]

_OPTIONAL_INTEGRATION_FIELDS = [
    {
        "name": "customer declared occupation / expected activity",
        "required": False,
        "source": "KYC profile",
        "reason": "Unlocks KYC-mismatch typologies; absent in public datasets, so it is not fabricated.",
    },
    {
        "name": "confirmed STR / no-STR outcome",
        "required": False,
        "source": "case-management disposition history",
        "reason": "Needed for bank-specific validation, threshold approval, and override analysis.",
    },
    {
        "name": "watchlist match snapshots",
        "required": False,
        "source": "screening system",
        "reason": "Lets VerdictAML preserve the bank's deterministic sanctions/PEP fail-safe.",
    },
]

# Configure logging once at import so the api/llm loggers actually emit (a bare
# getLogger has no handler). Idempotent — a no-op if a host (uvicorn) already set up
# root handlers, so it never double-logs.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

_DATA = Path(__file__).resolve().parent / "data"
_RESULTS = _DATA / "results.json"
_METRICS = _DATA / "metrics.json"
_AUDIT_SEED = _DATA / "audit_seed.json"  # Queue Agent autoClear events (ADR-0010)
_CLEARED_SEED = _DATA / "cleared_patterns_seed.json"  # Slice A demo suppression patterns
_BRIEFING = _DATA / "shift_briefing.json"
_SUPPRESSION = _DATA / "suppression_metrics.json"  # closed-loop suppression frontier (ADR-0021)
_NETWORKS = _DATA / "networks.json"  # frozen Mule Network heroes (ADR-0009/0015)
_IBM_SEED = _DATA / "ibm_seed_alerts.json"  # the hidden mule's own account as a queue alert (ADR-0015)
_DEMO_CLUSTER = _DATA / "demo_cluster_alerts.json"  # Slice A beat-3 self-suppression cluster
_STANDING_CLUSTER = _DATA / "standing_cluster_alerts.json"  # Slice A standing seeded suppression pair
_GOAML_CONFIG = GoamlConfig.model_validate(
    json.loads((_DATA / "goaml_config.json").read_text(encoding="utf-8"))
)
_CONTROL_PLANE = DecisionControlPlane(
    auto_clear_threshold=config.AUTO_CLEAR_THRESHOLD,
    review_threshold=config.REVIEW_THRESHOLD,
    qa_sample_rate=config.QA_SAMPLE_RATE,
    borderline_margin=config.BORDERLINE_MARGIN,
)
_MY_HOLIDAYS_FILE = _DATA / "my_holidays.json"  # MY federal/WP-KL public holidays for the SLA clock


def _load_my_holidays() -> set[date]:
    """Malaysian public holidays as a date set, so the STR filing-SLA clock skips them as
    non-working days (ADR-0016). Missing file -> empty set (weekends still skipped)."""
    if not _MY_HOLIDAYS_FILE.exists():
        return set()
    data = json.loads(_MY_HOLIDAYS_FILE.read_text(encoding="utf-8"))
    return {date.fromisoformat(h["date"]) for h in data.get("holidays", [])}


_MY_HOLIDAYS = _load_my_holidays()


def _load_alert_catalog() -> list[dict]:
    """Load the precomputed alert catalog (camelCase dicts), validating each against the
    contract. The seed source for the alert tables and the file-of-record (ADR-0003)."""
    catalog = json.loads(_RESULTS.read_text(encoding="utf-8"))
    for a in catalog:
        Alert.model_validate(a)  # fail fast on a malformed results.json
    return catalog


def _load_ibm_seed_alerts() -> list[dict]:
    """The hidden mule's own account as a benign-looking, dismiss-triaged queue alert (ADR-0015),
    so opening it and revealing its network plays the recall beat end-to-end. Built by
    data/ibm_network.py; missing file (extractor not run) -> none, and the beat simply isn't seeded."""
    if not _IBM_SEED.exists():
        return []
    catalog = json.loads(_IBM_SEED.read_text(encoding="utf-8"))
    for a in catalog:
        Alert.model_validate(a)  # fail fast on a malformed seed alert
    return catalog


def _load_demo_cluster() -> list[dict]:
    """The Slice A beat-3 cluster (agents/memory): three benign alerts sharing one counterparty, so
    dismissing the first self-suppresses the rest on stage. Built by data/build_demo_cluster.py;
    missing file -> none, and the beat simply isn't seeded."""
    if not _DEMO_CLUSTER.exists():
        return []
    catalog = json.loads(_DEMO_CLUSTER.read_text(encoding="utf-8"))
    for a in catalog:
        Alert.model_validate(a)  # fail fast on a malformed cluster alert
    return catalog


def _load_standing_cluster() -> list[dict]:
    """The Slice A standing cluster (data/build_standing_cluster.py): a benign FI-01 committee pair
    sharing one envelope. STANDCL-01 is seeded into cleared_patterns_seed.json as a prior clearance,
    so STANDCL-02 shows a real standing suppression (and a truthful '1 future alert affected') on a
    cold load, without pre-empting the live DEMO-CL beat. Missing file -> none."""
    if not _STANDING_CLUSTER.exists():
        return []
    catalog = json.loads(_STANDING_CLUSTER.read_text(encoding="utf-8"))
    for a in catalog:
        Alert.model_validate(a)  # fail fast on a malformed cluster alert
    return catalog


def _load_audit_seed() -> list[dict]:
    """The Queue Agent's autoClear events (ADR-0010), so /audit opens populated with the
    autonomous overnight run instead of empty until a human acts. Missing file
    (precompute not yet run) -> empty trail."""
    if not _AUDIT_SEED.exists():
        return []
    return json.loads(_AUDIT_SEED.read_text(encoding="utf-8"))


def _load_cleared_patterns_seed() -> list[dict]:
    """Slice A demo suppression patterns, so /learned-patterns opens populated (and a matching
    alert shows a suppression) in LIVE mode too, matching the mock. Missing file -> empty."""
    if not _CLEARED_SEED.exists():
        return []
    return json.loads(_CLEARED_SEED.read_text(encoding="utf-8"))


def _load_networks() -> dict[str, dict]:
    """The frozen Mule Network heroes (ADR-0009/0015), keyed by seed alertId. A real IBM AMLworld
    fan-in cluster shown qualitatively (no metric). Missing file (extractor not run) -> empty."""
    if not _NETWORKS.exists():
        return {}
    data = json.loads(_NETWORKS.read_text(encoding="utf-8"))
    for net in data.values():
        MuleNetwork.model_validate(net)  # fail fast on a malformed networks.json
    return data


_NETWORKS_DATA = _load_networks()


# The DB (store.py, behind the DATABASE_URL seam) is the source of truth for the alert
# catalog (alerts + their transactions), the analyst's decisions, and the audit trail —
# all survive a restart and are safe under concurrent requests. The catalog is seeded
# from results.json (the file-of-record, ADR-0003) and the trail from the Queue Agent's
# autonomous run (ADR-0010); each seed only takes when its table is empty, so a restart
# keeps decision-updated alert statuses and real runtime events.
store.init()
# reconcile_alerts (not seed_alerts): inserts any catalog alert missing from the DB and leaves
# existing (decided) rows untouched, so a durable Neon-backed deploy picks up newly-added seed
# alerts (e.g. the standing cluster) on the next boot instead of staying frozen on first-seed.
store.reconcile_alerts(
    _load_alert_catalog() + _load_ibm_seed_alerts() + _load_demo_cluster() + _load_standing_cluster()
)
store.seed_audit(_load_audit_seed())
store.seed_cleared_patterns(_load_cleared_patterns_seed())


# --- error shape: { "error": { "code", "message" } } (CLAUDE.md > API contract) ---

class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message


def _require_alert(alert_id: str) -> dict:
    alert = store.get_alert(alert_id)
    if alert is None:
        raise ApiError(404, "ALERT_NOT_FOUND", f"No alert with id '{alert_id}'.")
    return alert


class DecisionRequest(CamelModel):
    action: Literal["approve", "override"]
    final_disposition: Literal["escalate", "dismiss"]
    edited_str_draft: STRDraft | None = None
    note: str | None = None


_ACTOR_ROLES = {"analyst", "qa", "compliance", "modelRisk", "amlOps", "security", "admin"}
_DEMO_FALLBACK_ACTOR = Actor(actor_id="demo-operator", actor_role="admin", source="demoFallback")


def actor_from_headers(
    x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
    x_actor_role: str | None = Header(default=None, alias="X-Actor-Role"),
) -> Actor:
    """Production-shaped actor envelope.

    The demo keeps running without auth headers via an explicit fallback actor, but any caller that
    does provide actor headers is validated and role-checked. In production this seam becomes
    OIDC/JWT claims without changing endpoint authorization logic.
    """
    if x_actor_id is None and x_actor_role is None:
        return _DEMO_FALLBACK_ACTOR
    if not x_actor_id or not x_actor_role:
        raise ApiError(401, "ACTOR_HEADERS_REQUIRED", "Provide both X-Actor-Id and X-Actor-Role.")
    if x_actor_role not in _ACTOR_ROLES:
        raise ApiError(403, "ACTOR_ROLE_INVALID", f"Unknown actor role '{x_actor_role}'.")
    return Actor(actor_id=x_actor_id.strip(), actor_role=x_actor_role, source="headers")


def require_actor(*allowed_roles: ActorRole):
    allowed = set(allowed_roles)

    def _dependency(actor: Actor = Depends(actor_from_headers)) -> Actor:
        if actor.actor_role == "admin" or actor.actor_role in allowed:
            return actor
        raise ApiError(
            403,
            "ROLE_FORBIDDEN",
            f"Role '{actor.actor_role}' cannot perform this action; allowed roles: {', '.join(sorted(allowed))}.",
        )

    return _dependency


def get_llm_client():
    """Injectable LLM client. None in prod → agents lazily build the real DeepSeek
    client; tests override this dependency with a fake so /triage spends no tokens."""
    return None


app = FastAPI(title="AML Alert-Triage Copilot")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    """The single error envelope (CLAUDE.md > API contract): every error exits here."""
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})


@app.exception_handler(ApiError)
def _api_error_handler(_request, exc: ApiError):
    return _error_response(exc.status_code, exc.code, exc.message)


@app.exception_handler(RequestValidationError)
def _validation_error_handler(_request, exc: RequestValidationError):
    """Malformed request body/params — keep the contract shape instead of FastAPI's default."""
    detail = "; ".join(
        f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
    )
    return _error_response(422, "VALIDATION_ERROR", detail or "Request validation failed.")


@app.exception_handler(Exception)
def _unexpected_error_handler(_request, exc: Exception):
    """Last-resort catch-all so an unexpected failure still exits in the contract
    shape. The message is generic — internals aren't leaked to the client."""
    logger.exception("Unhandled error serving request")
    return _error_response(500, "INTERNAL_ERROR", "An unexpected error occurred.")


@app.get("/health")
def health():
    """Liveness + readiness for the live path. `llmKeyPresent` confirms the live
    /triage run is actually wired BEFORE you're on camera — a missing key otherwise
    only surfaces as a logged warning mid-Q&A, then falls back to precomputed
    (ADR-0003). Cheap to hit during a pre-demo check."""
    return {
        "status": "ok",
        "alertsLoaded": store.count_alerts(),
        "transactionsLoaded": store.count_transactions(),
        # Active-provider credential check (Slice B): LLM_API_KEY is the cloud key in DeepSeek
        # mode and the (always-present) local key in on-prem mode — so this stays a true
        # "is the live path wired" signal whichever provider is selected.
        "llmKeyPresent": bool(config.LLM_API_KEY),
        "model": config.MODEL_WORKHORSE,
        "provider": config.LLM_PROVIDER,
    }


def _qa_sampled_ids() -> set[str]:
    """The risk-weighted QA sample of the auto-cleared lane (ADR-0019), computed over the FULL
    catalog so it is stable under any status/routing filter and identical for the list and the
    detail view. Deterministic (marginal-confidence ranking)."""
    return _CONTROL_PLANE.qa_sample_ids(store.list_alerts(None, None))


def _apply_control(alert: dict, *, qa_sample_ids: set[str] | None = None) -> dict:
    """Attach serve-time control-plane fields to a full alert."""
    decision = _CONTROL_PLANE.evaluate_alert(
        alert,
        qa_sample_ids=qa_sample_ids if qa_sample_ids is not None else _qa_sampled_ids(),
    )
    alert["routing"] = decision.routing
    alert["qaSampled"] = decision.qa_sampled
    alert["borderlineDismiss"] = decision.borderline_dismiss
    return alert




@app.get("/alerts")
def list_alerts(status: str | None = None, routing: str | None = None):
    """Queue. Optional ?status= and ?routing= filters (the Queue Agent lanes, ADR-0010),
    with queue items omitting embedded transactions.
    Marks each alert's `qaSampled` (ADR-0019) and re-routes a borderline dismiss that a learned
    suppression now auto-clears (ADR-0021), so the worklist shrinks as the analyst clears look-alikes."""
    sampled = _qa_sampled_ids()
    # Routing is a serve-time control-plane decision: learned suppression can flip a stored
    # needsReview row to autoCleared after the DB query. So when the caller filters by routing,
    # we must evaluate the full status-filtered population first, then apply the lane filter to
    # the post-control routing, or the queue can contradict itself on the wire.
    alerts = store.list_alerts(status, None if routing is not None else routing)
    filtered: list[dict] = []
    for a in alerts:
        full = None
        if _CONTROL_PLANE.requires_ledger_for_suppression(a):
            full = store.get_alert(a["alertId"])
            if full is not None:
                enrich_served_alert(full)
        decision = _CONTROL_PLANE.evaluate_queue_item(a, full_alert=full, qa_sample_ids=sampled)
        a["routing"] = decision.routing
        a["qaSampled"] = decision.qa_sampled
        a["borderlineDismiss"] = decision.borderline_dismiss
        # Surface the learned suppression on the queue row too: the frontend's "Learning loop impact"
        # card counts routing==autoCleared AND triage.suppression==suppressed. enrich_served_alert
        # attached it to the hydrated `full`; the returned queue row carries the stored triage (no
        # transactions, no suppression), so copy it across or the productized proof reads 0.
        if full is not None and (supp := full["triage"].get("suppression")) is not None:
            a["triage"]["suppression"] = supp
        if routing is None or a["routing"] == routing:
            filtered.append(a)
    return filtered


def _attach_serve_time_insight(alert: dict) -> None:
    """Attach the read-only, serve-time derivations (ADR-0016): the ledger-based Account
    Activity Profile and the BNM STR filing-SLA clock. Both are pure functions over data
    already on the alert, so they need no results.json regen and are never persisted. The
    SLA clock keys off the analyst's escalate decision (real GMT+8) — never the synthetic
    transaction date — so it shows a prospective deadline until the alert is adjudicated."""
    txns = alert.get("transactions") or []
    profile = compute_activity_profile(txns)

    decision = store.get_decision(alert["alertId"])
    established_at = (
        datetime.fromisoformat(decision["decidedAt"])
        if decision and decision.get("decidedAt") else None
    )
    sla = filing_sla(
        recommendation=alert["triage"]["recommendation"],
        final_disposition=(decision or {}).get("finalDisposition"),
        established_at=established_at,
        now=now_local(),
        holidays=_MY_HOLIDAYS,
    )
    alert["activityProfile"] = AccountActivityProfile.model_validate(profile).model_dump(
        by_alias=True, mode="json")
    alert["filingSla"] = FilingSla.model_validate(sla).model_dump(by_alias=True, mode="json")


@app.get("/alerts/{alert_id}")
def get_alert(alert_id: str):
    """Detail: account + embedded transactions + embedded triage, plus the serve-time
    Account Activity Profile and STR filing-SLA clock (ADR-0016)."""
    alert = _require_alert(alert_id)
    enrich_served_alert(alert)  # Slice A: attach a serve-time suppression if the pattern was learned
    # ADR-0021: close the loop — a matched, envelope-consistent suppression auto-clears a borderline
    # dismiss here at serve time (the queue list stays suppression-blind: it omits transactions, which
    # the envelope gate needs). Session-dynamic, so it is never baked into results.json.
    _apply_control(alert)
    _attach_serve_time_insight(alert)
    return alert


def _str_anchor_summary(str_draft: dict | None) -> dict | None:
    if not str_draft:
        return None
    current_grounds = {g.strip() for g in str_draft.get("groundsForSuspicion", []) if g.strip()}
    pulled = [c.strip() for c in str_draft.get("unanchoredClaims") or [] if c.strip()]
    unanchored_in_filing = [c for c in pulled if c in current_grounds]
    traced = str_draft.get("tracedClaims") or []
    anchored = sum(1 for c in traced if c.get("anchored"))
    return {
        "claimCount": len(current_grounds),
        "tracedClaimCount": len(traced),
        "anchoredClaimCount": anchored,
        "pulledUnanchoredClaimCount": len(pulled),
        "unanchoredClaimsStillInFiling": unanchored_in_filing,
        "exportBlocked": bool(unanchored_in_filing),
    }


def _auto_clear_defense(alert: dict) -> dict:
    decision = _CONTROL_PLANE.evaluate_alert(
        alert,
        qa_sample_ids={alert["alertId"]} if alert.get("qaSampled") else set(),
    )
    return {
        "routing": decision.routing,
        "eligible": decision.eligible,
        "thresholds": {
            "review": config.REVIEW_THRESHOLD,
            "autoClear": config.AUTO_CLEAR_THRESHOLD,
            "qaSample": config.QA_SAMPLE_RATE,
        },
        "qaSampled": decision.qa_sampled,
        "borderlineDismiss": decision.borderline_dismiss,
        "reasons": decision.reasons,
    }


@app.get("/alerts/{alert_id}/defense-case", response_model=DefenseCase)
def get_alert_defense_case(alert_id: str):
    """Machine-readable defense packet for one alert: evidence, controls, and audit.

    This is the API counterpart of the alert detail's Defense Case panel. It is assembled from the
    stored triage, deterministic policy gates, and append-only audit trail — no LLM, no fabricated
    explanation.
    """
    alert = _require_alert(alert_id)
    enrich_served_alert(alert)
    _apply_control(alert)
    decision = store.get_decision(alert_id)
    triage = alert["triage"]
    str_summary = _str_anchor_summary(triage.get("strDraft"))
    audit_events = [e for e in reversed(store.all_audit()) if e["alertId"] == alert_id]
    can_file = (
        decision is not None
        and decision.get("finalDisposition") == "escalate"
        and triage.get("strDraft") is not None
        and not (str_summary or {}).get("exportBlocked", False)
    )
    packet = {
        "alertId": alert_id,
        "generatedAt": now_local().isoformat(),
        "subject": {
            "accountId": alert["account"]["accountId"],
            "holderName": alert["account"]["holderName"],
        },
        "decisionContext": {
            "status": alert["status"],
            "aiRecommendation": triage["recommendation"],
            "confidence": triage["confidence"],
            "finalDisposition": (decision or {}).get("finalDisposition"),
            "decisionAction": (decision or {}).get("action"),
        },
        "evidence": {
            "matchedTypology": triage["matchedTypology"],
            "indicatorCoverage": triage["indicatorCoverage"],
            "citedTransactionIds": triage["citedTransactionIds"],
            "strAnchoring": str_summary,
        },
        "controls": {
            "autoClearPolicy": _auto_clear_defense(alert),
            "verifier": triage["verifier"],
            "screening": triage.get("screening"),
            "debatePresent": triage.get("debate") is not None,
            "strFiling": {
                "canFile": can_file,
                "requiresEscalateSignoff": True,
                "blocksUnanchoredGrounds": True,
                "xsdValidatedOnExport": True,
            },
        },
        "audit": audit_events,
    }
    return DefenseCase.model_validate(packet).model_dump(by_alias=True, mode="json")


def _case_status_update(alert: dict, decision: dict | None, audit_events: list[dict]) -> str:
    submission_ref = next((e.get("submissionRef") for e in audit_events if e.get("submissionRef")), None)
    if submission_ref:
        return "filed"
    final_disposition = (decision or {}).get("finalDisposition")
    if final_disposition == "escalate":
        return "escalated"
    if final_disposition == "dismiss":
        return "dismissed"
    if alert.get("routing") == "autoCleared":
        return "autoCleared"
    return "needsReview"


def _case_handoff_note(alert: dict, status_update: str, decision: dict | None) -> str:
    triage = alert["triage"]
    typology = triage["matchedTypology"]
    verifier_status = triage["verifier"]["status"]
    indicator_count = len(triage["indicatorCoverage"]["fired"])
    total_indicators = len(triage["indicatorCoverage"]["indicators"])
    cited_count = len(triage["citedTransactionIds"])
    final_disposition = (decision or {}).get("finalDisposition")
    if status_update == "filed":
        action = "Approved STR filed to goAML"
    elif final_disposition:
        action = f"Human final disposition: {final_disposition}"
    elif status_update == "autoCleared":
        action = "Queue Agent auto-cleared in demo shadow mode"
    else:
        action = "Routed to analyst review"
    return (
        f"{action}. AI recommended {triage['recommendation']} at {round(triage['confidence'] * 100)}% "
        f"confidence on {typology['code']} ({typology['name']}); verifier {verifier_status}; "
        f"{indicator_count}/{total_indicators} indicators fired; {cited_count} cited transaction(s)."
    )


def _gate_result(name: str, active: bool) -> str:
    return f"{name}:blocked" if active else f"{name}:clear"


def _decision_trace_steps(alert: dict, decision: dict | None) -> list[dict[str, Any]]:
    triage = alert["triage"]
    coverage = triage["indicatorCoverage"]
    indicators = coverage.get("indicators") or []
    fired = set(coverage.get("fired") or [])
    cited_ids = triage.get("citedTransactionIds") or []
    screening = triage.get("screening") or {}
    suppression = triage.get("suppression") or {}
    str_summary = _str_anchor_summary(triage.get("strDraft"))
    str_blocked = bool((str_summary or {}).get("exportBlocked"))
    final_disposition = (decision or {}).get("finalDisposition")
    can_file = (
        decision is not None
        and final_disposition == "escalate"
        and triage.get("strDraft") is not None
        and not str_blocked
    )
    steps: list[dict[str, Any]] = []

    for indicator in indicators:
        active = indicator in fired
        steps.append({
            "step": "indicatorEvaluation",
            "label": indicator,
            "inputs": {
                "matchedTypology": triage["matchedTypology"]["code"],
                "indicator": indicator,
            },
            "result": "fired" if active else "notFired",
            "evidenceIds": cited_ids if active else [],
            "deterministic": True,
        })

    steps.append({
        "step": "confidenceComputation",
        "label": "Served confidence",
        "inputs": {
            "firedIndicatorCount": len(fired),
            "totalIndicatorCount": len(indicators),
            "servedConfidence": triage["confidence"],
            "matchedTypology": triage["matchedTypology"]["code"],
        },
        "result": str(triage["confidence"]),
        "evidenceIds": cited_ids,
        "deterministic": True,
    })
    verifier_claims = triage["verifier"].get("claims") or []
    steps.append({
        "step": "verifierGate",
        "label": "Verifier agreement",
        "inputs": {
            "status": triage["verifier"]["status"],
            "agreesWithRecommendation": triage["verifier"].get("agreesWithRecommendation"),
            "claimCount": len(verifier_claims),
            "anchoredClaimCount": sum(1 for c in verifier_claims if c.get("anchored")),
        },
        "result": triage["verifier"]["status"],
        "evidenceIds": cited_ids,
        "deterministic": False,
    })
    steps.append({
        "step": "screeningGate",
        "label": "Sanctions and PEP screening",
        "inputs": {
            "status": screening.get("status"),
            "blocked": bool(screening.get("blocked")),
            "matches": len(screening.get("matches") or []),
        },
        "result": _gate_result("screening", bool(screening.get("blocked"))),
        "evidenceIds": [],
        "deterministic": True,
    })
    steps.append({
        "step": "debateGate",
        "label": "Adversarial debate",
        "inputs": {
            "present": triage.get("debate") is not None,
            "outcome": ((triage.get("debate") or {}).get("reverdict") or {}).get("outcome"),
        },
        "result": "present" if triage.get("debate") else "absent",
        "evidenceIds": cited_ids if triage.get("debate") else [],
        "deterministic": False,
    })
    steps.append({
        "step": "suppressionGate",
        "label": "Learned suppression",
        "inputs": {
            "status": suppression.get("status"),
            "matchedPatternId": suppression.get("matchedPatternId"),
            "sourceDecisionId": suppression.get("sourceDecisionId"),
        },
        "result": suppression.get("status") or "absent",
        "evidenceIds": [suppression["sourceDecisionId"]] if suppression.get("sourceDecisionId") else [],
        "deterministic": True,
    })
    steps.append({
        "step": "routePolicy",
        "label": "Queue routing policy",
        "inputs": {
            "recommendation": triage["recommendation"],
            "confidence": triage["confidence"],
            "routing": alert.get("routing"),
            "reviewThreshold": config.REVIEW_THRESHOLD,
            "autoClearThreshold": config.AUTO_CLEAR_THRESHOLD,
            "verifierStatus": triage["verifier"]["status"],
            "screeningBlocked": bool(screening.get("blocked")),
            "debatePresent": triage.get("debate") is not None,
            "suppressionStatus": suppression.get("status"),
        },
        "result": alert.get("routing") or "needsReview",
        "evidenceIds": cited_ids,
        "deterministic": True,
    })
    steps.append({
        "step": "strFilingGate",
        "label": "STR/goAML filing gate",
        "inputs": {
            "finalDisposition": final_disposition,
            "strDraftPresent": triage.get("strDraft") is not None,
            "anchoringExportBlocked": str_blocked,
            "requiresHumanEscalateSignoff": True,
        },
        "result": "canFile" if can_file else "locked",
        "evidenceIds": cited_ids if triage.get("strDraft") else [],
        "deterministic": True,
    })
    return steps


def _decision_trace_packet(alert_id: str) -> dict[str, Any]:
    alert = _require_alert(alert_id)
    enrich_served_alert(alert)
    _apply_control(alert)
    decision = store.get_decision(alert_id)
    triage = alert["triage"]
    total = len(triage["indicatorCoverage"].get("indicators") or [])
    formula = (
        "confidence = firedIndicators / totalIndicators, persisted from the served triage output"
        if total
        else "confidence = 1.0 when no covered typology indicators matched (NONE)"
    )
    return {
        "alertId": alert_id,
        "generatedAt": now_local().isoformat(),
        "currentRecommendation": triage["recommendation"],
        "currentConfidence": triage["confidence"],
        "routing": alert.get("routing"),
        "formula": formula,
        "steps": _decision_trace_steps(alert, decision),
        "nonClaims": [
            "This trace is not DeepSeek chain-of-thought and does not expose private model reasoning.",
            "This endpoint does not rerun the LLM; it replays stored triage outputs and deterministic control gates.",
            "Evidence IDs reference stored alert evidence such as cited transaction IDs and prior decision IDs; the full ledger remains in the alert detail contract.",
        ],
    }


@app.get("/alerts/{alert_id}/decision-trace", response_model=DecisionTrace)
def get_decision_trace(alert_id: str):
    """Observable decision trace: stored triage outputs plus deterministic control gates."""
    return DecisionTrace.model_validate(_decision_trace_packet(alert_id)).model_dump(by_alias=True, mode="json")


def _hash_payload(payload: dict | list | str | None) -> str:
    raw = payload if isinstance(payload, str) else json.dumps(payload or {}, sort_keys=True, default=str)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _copilot_run_non_claims(mode: str) -> list[str]:
    return [
        "This ledger exposes the prompt/response envelope VerdictAML controls; it is not DeepSeek chain-of-thought.",
        "Live runs capture redacted request messages, raw response text, schema validation, and retries at the LLM seam.",
        (
            "Precomputed runs are reconstructed from stored triage outputs and current source templates; "
            "the original provider request/response body was not captured when the fixture was generated."
            if mode == "precomputed" else
            "Raw unredacted prompts are represented by hashes; privileged production audit storage should retain encrypted originals."
        ),
    ]


def _ledger_context(alert: dict, final_output: dict) -> tuple[dict, dict, list[dict]]:
    alert_model = Alert.model_validate(alert)
    evidence = render_alert_evidence(alert_model)
    cards = select_cards(alert_model)
    ranked = rank_cards(evidence, cards)
    triage = final_output
    deterministic = [
        {
            "stage": "retrieval",
            "result": "ranked",
            "detail": f"{len(cards)} typology cards ranked by signal overlap.",
        },
        {
            "stage": "screening",
            "result": (triage.get("screening") or {}).get("status", "unknown"),
            "detail": "Deterministic sanctions/PEP screening is computed before LLM routing gates.",
        },
        {
            "stage": "citationGrounding",
            "result": "grounded",
            "detail": f"{len(triage.get('citedTransactionIds') or [])} cited transaction id(s) retained in final output.",
        },
        {
            "stage": "routingPolicy",
            "result": alert.get("routing") or "needsReview",
            "detail": "Routing is derived from recommendation, confidence, verifier, debate, screening, and suppression gates.",
        },
    ]
    input_snapshot = {
        "alertId": alert["alertId"],
        "trigger": alert.get("trigger"),
        "transactionCount": len(alert.get("transactions") or []),
        "riskScore": alert.get("riskScore"),
        "evidenceHash": _hash_payload(evidence),
    }
    retrieval = {
        "candidateCount": len(cards),
        "topCandidates": [
            {
                "code": card.code,
                "name": card.name,
                "source": card.source,
                "score": score,
            }
            for card, score in ranked[:5]
        ],
        "selectedTypology": triage.get("matchedTypology"),
    }
    return input_snapshot, retrieval, deterministic


def _precomputed_copilot_ledger(alert_id: str) -> dict:
    alert = _require_alert(alert_id)
    enrich_served_alert(alert)
    _apply_control(alert)
    triage = alert["triage"]
    generated_at = triage.get("generatedAt") or now_local().isoformat()
    input_snapshot, retrieval, deterministic = _ledger_context(alert, triage)
    evidence_note = (
        "Reconstructed prompt envelope from current source templates and stored alert evidence. "
        "Original provider request body was not captured for this precomputed fixture."
    )
    llm_calls = [
        {
            "stage": "triageAgent",
            "templateId": "triage-agent-v1",
            "model": triage.get("model") or config.MODEL_WORKHORSE,
            "responseModel": "TriageOutput",
            "attempt": 1,
            "messages": [
                {
                    "role": "system",
                    "content": "Reconstructed current triage system prompt and candidate typology cards.",
                    "contentHash": _hash_payload("triage-agent-v1"),
                    "redactionLevel": "piiRedacted",
                },
                {
                    "role": "user",
                    "content": evidence_note,
                    "contentHash": input_snapshot["evidenceHash"],
                    "redactionLevel": "piiRedacted",
                },
            ],
            "rawResponse": json.dumps({
                "matchedTypologyCode": (triage.get("matchedTypology") or {}).get("code"),
                "firedIndicators": (triage.get("indicatorCoverage") or {}).get("fired", []),
                "recommendation": triage.get("recommendation"),
                "claims": triage.get("claims", []),
            }),
            "rawResponseHash": _hash_payload(triage),
            "schemaValid": True,
            "validationError": None,
        },
        {
            "stage": "verifier",
            "templateId": "verifier-v1",
            "model": config.MODEL_VERIFIER,
            "responseModel": "Verifier",
            "attempt": 1,
            "messages": [
                {
                    "role": "system",
                    "content": "Reconstructed current verifier prompt; raw provider prompt was not captured.",
                    "contentHash": _hash_payload("verifier-v1"),
                    "redactionLevel": "piiRedacted",
                }
            ],
            "rawResponse": json.dumps(triage.get("verifier") or {}),
            "rawResponseHash": _hash_payload(triage.get("verifier") or {}),
            "schemaValid": True,
            "validationError": None,
        },
    ]
    if triage.get("strDraft"):
        llm_calls.append({
            "stage": "strDrafter",
            "templateId": "str-drafter-v1",
            "model": config.MODEL_WORKHORSE,
            "responseModel": "STRDraft",
            "attempt": 1,
            "messages": [
                {
                    "role": "system",
                    "content": "Reconstructed current STR drafter prompt; raw provider prompt was not captured.",
                    "contentHash": _hash_payload("str-drafter-v1"),
                    "redactionLevel": "piiRedacted",
                }
            ],
            "rawResponse": json.dumps(triage["strDraft"]),
            "rawResponseHash": _hash_payload(triage["strDraft"]),
            "schemaValid": True,
            "validationError": None,
        })
    return {
        "runId": "precomputed-current",
        "alertId": alert_id,
        "mode": "precomputed",
        "provider": "precomputed-fixture",
        "model": triage.get("model") or config.MODEL_WORKHORSE,
        "status": "reconstructed",
        "startedAt": generated_at,
        "completedAt": generated_at,
        "latencyMs": 0,
        "promptVersion": "current-source-reconstruction",
        "inputSnapshot": input_snapshot,
        "retrieval": retrieval,
        "llmCalls": llm_calls,
        "deterministicEvents": deterministic,
        "finalOutput": triage,
        "redactions": [
            "Precomputed fixture prompts are reconstructed; original raw prompts were not stored.",
            "Evidence content is represented by hash in this reconstructed ledger.",
        ],
        "nonClaims": _copilot_run_non_claims("precomputed"),
    }


def _normalise_live_ledger(payload: dict) -> dict:
    alert = _require_alert(payload["alertId"])
    final_output = payload.get("finalOutput") or alert["triage"]
    input_snapshot, retrieval, deterministic = _ledger_context(alert, final_output)
    return {
        "runId": payload["runId"],
        "alertId": payload["alertId"],
        "mode": "live",
        "provider": payload.get("provider") or config.LLM_PROVIDER,
        "model": payload.get("model") or config.MODEL_WORKHORSE,
        "status": payload.get("status", "completed"),
        "startedAt": payload["startedAt"],
        "completedAt": payload.get("completedAt"),
        "latencyMs": payload.get("latencyMs"),
        "promptVersion": "captured-runtime-envelope",
        "inputSnapshot": input_snapshot,
        "retrieval": retrieval,
        "llmCalls": payload.get("llmCalls") or [],
        "deterministicEvents": deterministic,
        "finalOutput": final_output,
        "redactions": payload.get("redactions") or [],
        "nonClaims": _copilot_run_non_claims("live"),
    }


def _copilot_summary(ledger: dict) -> dict:
    return {
        "runId": ledger["runId"],
        "alertId": ledger["alertId"],
        "mode": ledger["mode"],
        "provider": ledger["provider"],
        "model": ledger["model"],
        "status": ledger["status"],
        "startedAt": ledger["startedAt"],
        "completedAt": ledger.get("completedAt"),
        "latencyMs": ledger.get("latencyMs"),
        "promptVersion": ledger["promptVersion"],
        "outputHash": _hash_payload(ledger.get("finalOutput") or {}),
        "ledgerEndpoint": f"/alerts/{ledger['alertId']}/copilot-runs/{ledger['runId']}/ledger",
    }


@app.get("/alerts/{alert_id}/copilot-runs", response_model=CopilotRunList)
def get_copilot_runs(alert_id: str):
    _require_alert(alert_id)
    ledgers = [_normalise_live_ledger(r) for r in store.list_copilot_runs(alert_id)]
    ledgers.append(_precomputed_copilot_ledger(alert_id))
    return CopilotRunList(
        alert_id=alert_id,
        runs=[_copilot_summary(ledger) for ledger in ledgers],
    ).model_dump(by_alias=True, mode="json")


@app.get("/alerts/{alert_id}/copilot-runs/{run_id}/ledger", response_model=CopilotRunLedger)
def get_copilot_run_ledger(alert_id: str, run_id: str):
    _require_alert(alert_id)
    if run_id == "precomputed-current":
        ledger = _precomputed_copilot_ledger(alert_id)
    else:
        stored = store.get_copilot_run(alert_id, run_id)
        if stored is None:
            raise ApiError(404, "COPILOT_RUN_NOT_FOUND", f"No copilot run '{run_id}' for alert '{alert_id}'.")
        ledger = _normalise_live_ledger(stored)
    return CopilotRunLedger.model_validate(ledger).model_dump(by_alias=True, mode="json")


@app.get("/alerts/{alert_id}/case-handoff", response_model=CaseHandoff)
def get_case_handoff(alert_id: str):
    """Bank case-management handoff packet for one alert.

    This is the integration counterpart to /defense-case: it shows the status update,
    case note, artifacts, audit events, and write-back gate VerdictAML would hand to
    Actimize/SAS/Mantas or a bank case-management queue. It is read-only in the demo.
    """
    alert = _require_alert(alert_id)
    enrich_served_alert(alert)
    _apply_control(alert)
    decision = store.get_decision(alert_id)
    triage = alert["triage"]
    str_summary = _str_anchor_summary(triage.get("strDraft"))
    audit_events = [e for e in reversed(store.all_audit()) if e["alertId"] == alert_id]
    submission_ref = next((e.get("submissionRef") for e in audit_events if e.get("submissionRef")), None)
    can_export = (
        decision is not None
        and decision.get("finalDisposition") == "escalate"
        and triage.get("strDraft") is not None
        and not (str_summary or {}).get("exportBlocked", False)
    )
    status_update = _case_status_update(alert, decision, audit_events)
    human_decided = decision is not None
    packet = {
        "alertId": alert_id,
        "generatedAt": now_local().isoformat(),
        "sourceSystem": "VerdictAML case handoff API",
        "targetSystems": [
            "SAS AML",
            "NICE Actimize",
            "Oracle Mantas",
            "bank case-management queue",
            "goAML e-filing seam",
        ],
        "caseStatusUpdate": status_update,
        "caseNote": _case_handoff_note(alert, status_update, decision),
        "decision": {
            "aiRecommendation": triage["recommendation"],
            "confidence": triage["confidence"],
            "verifierStatus": triage["verifier"]["status"],
            "finalDisposition": (decision or {}).get("finalDisposition"),
            "decisionAction": (decision or {}).get("action"),
            "overrideReason": (decision or {}).get("note") if (decision or {}).get("action") == "override" else None,
        },
        "attachments": [
            {
                "name": "Per-alert defense case",
                "endpoint": f"/alerts/{alert_id}/defense-case",
                "available": True,
                "reason": "Evidence, controls, and audit replay are always attached.",
            },
            {
                "name": "goAML STR XML",
                "endpoint": f"/alerts/{alert_id}/str.xml",
                "available": can_export,
                "reason": (
                    "Unlocked after human escalate sign-off and STR anchoring checks."
                    if can_export
                    else "Locked until human escalate sign-off and STR anchoring checks pass."
                ),
            },
            {
                "name": "Audit trail",
                "endpoint": "/audit",
                "available": bool(audit_events),
                "reason": f"{len(audit_events)} event(s) recorded for this alert.",
            },
        ],
        "auditEvents": audit_events,
        "submissionRef": submission_ref,
        "writeBack": {
            "mode": "humanApprovedWriteback" if human_decided else "shadowOnly",
            "allowed": human_decided,
            "requiresHumanDecision": True,
            "blockedReason": None if human_decided else (
                "No analyst final disposition yet; VerdictAML returns a shadow packet and does not mutate the bank case."
            ),
            "productionGate": (
                "Enable write-back only after bank historical replay, compliance approval, and case-management integration sign-off."
            ),
        },
        "nonClaims": [
            "This demo endpoint does not mutate a live bank case-management system.",
            "Auto-cleared alerts are inspectable and QA-sampled; they are not STR filings.",
            "goAML filing remains human-approved and evidence-anchored.",
        ],
    }
    return CaseHandoff.model_validate(packet).model_dump(by_alias=True, mode="json")


@app.get("/alerts/{alert_id}/network")
def get_network(alert_id: str):
    """The precomputed Mule Network for a seed alert (ADR-0009/0015): a real IBM AMLworld fan-in
    cluster, shown qualitatively — no metric is claimed. 404 in contract shape when the alert has
    no network (most alerts don't). Reveals the hidden mule single-account triage cleared."""
    net = _NETWORKS_DATA.get(alert_id)
    if net is None:
        raise ApiError(404, "NETWORK_NOT_FOUND", f"No mule network for alert '{alert_id}'.")
    return MuleNetwork.model_validate(net).model_dump(by_alias=True, mode="json")


@app.get("/learned-patterns")
def learned_patterns():
    """Slice A: cross-customer suppression patterns learned from analyst dismissals."""
    return store.all_cleared_patterns()


def _learning_loop_scan() -> dict:
    """Explain the full learning-loop opportunity space.

    This is deliberately broader than /learned-patterns. It scans every alert in the catalog and shows
    which dismiss-shaped alerts could teach reusable memory, which future alerts would be affected by
    that memory, and which apparent matches are blocked by the suppression firewall.
    """
    metas = store.list_alerts(None, None)
    full_alerts = [store.get_alert(a["alertId"]) for a in metas]
    alerts = [a for a in full_alerts if a is not None]
    by_signature: dict[str, list[dict]] = {}
    signatures: dict[str, str] = {}

    for alert in alerts:
        sig = memory_signature(alert)
        if not sig:
            continue
        signatures[alert["alertId"]] = sig
        by_signature.setdefault(sig, []).append(alert)

    candidates = []
    for alert in alerts:
        triage = alert["triage"]
        sig = signatures.get(alert["alertId"])
        recommendation = triage["recommendation"]
        verifier_status = triage["verifier"]["status"]
        screening = triage.get("screening") or {}
        can_teach = sig is not None and recommendation == "dismiss"
        blocked_reason = None
        if sig is None:
            blocked_reason = "No reusable signature: no matched typology or reusable ledger envelope."
        elif recommendation != "dismiss":
            blocked_reason = "Not a benign-clearance source unless a human overrides to dismiss."
        elif verifier_status != "agreed":
            blocked_reason = "Verifier contested the call; not a clean precedent."
        elif screening.get("blocked"):
            blocked_reason = "Screening block prevents benign memory."

        future = []
        blocked_future = []
        if sig:
            for other in by_signature.get(sig, []):
                if other["alertId"] == alert["alertId"]:
                    continue
                other_triage = other["triage"]
                other_screening = other_triage.get("screening") or {}
                gate_reasons = []
                if other_triage["recommendation"] != "dismiss":
                    gate_reasons.append("future alert is not a dismiss")
                if other_triage["verifier"]["status"] != "agreed":
                    gate_reasons.append("verifier not agreed")
                if other_triage.get("debate"):
                    gate_reasons.append("debated alert")
                if other_screening.get("blocked"):
                    gate_reasons.append("screening blocked")
                if not (config.REVIEW_THRESHOLD <= other_triage["confidence"] < config.AUTO_CLEAR_THRESHOLD):
                    gate_reasons.append("outside learned-suppression confidence band")
                if not envelope_benign_consistent(other.get("transactions") or []):
                    gate_reasons.append("ledger envelope not benign-consistent")

                item = {
                    "alertId": other["alertId"],
                    "holderName": other["account"]["holderName"],
                    "currentRouting": other.get("routing"),
                    "confidence": other_triage["confidence"],
                    "recommendation": other_triage["recommendation"],
                }
                if gate_reasons:
                    blocked_future.append({**item, "reason": "; ".join(gate_reasons)})
                else:
                    future.append(item)

        candidates.append({
            "sourceAlertId": alert["alertId"],
            "holderName": alert["account"]["holderName"],
            "signature": sig,
            "typology": (triage.get("matchedTypology") or {}).get("code"),
            "recommendation": recommendation,
            "verifierStatus": verifier_status,
            "canTeach": can_teach,
            "blockedReason": blocked_reason,
            "affectedFutureAlerts": future,
            "blockedFutureAlerts": blocked_future,
        })

    reusable = [c for c in candidates if c["canTeach"] and c["affectedFutureAlerts"]]
    return {
        "scannedAlerts": len(alerts),
        "signatureCount": len(by_signature),
        "teachableSources": sum(1 for c in candidates if c["canTeach"]),
        "reusableSources": len(reusable),
        "affectedFutureAlerts": sum(len(c["affectedFutureAlerts"]) for c in reusable),
        "candidates": sorted(
            candidates,
            key=lambda c: (
                0 if c["affectedFutureAlerts"] else 1,
                0 if c["canTeach"] else 1,
                c["sourceAlertId"],
            ),
        ),
    }


@app.get("/learning-loop/opportunities")
def learning_loop_opportunities():
    """Full population scan behind the learning-loop demo.

    Judges can see that the system scanned every alert, found which dismissals are reusable, and also
    explains why most alerts do not create future-work impact.
    """
    return _learning_loop_scan()


@app.get("/typologies/{code}/handbook")
def typology_handbook(code: str, client=Depends(get_llm_client)):
    """Live DeepSeek RAG: retrieve the most relevant KB passages for the typology (hybrid BM25 +
    semantic) and have DeepSeek write a 'what to check' handbook grounded ONLY in them, each check
    cited to its source page. Q&A path — falls back to the card's curated checks if generation
    fails, so it never 500s on camera (ADR-0003 philosophy)."""
    from agents.coaching import generate_handbook
    from agents.knowledge_base import get_card
    from schemas import CoachingHandbook, HandbookCheck

    try:
        card = get_card(code)
    except KeyError:
        raise ApiError(404, "TYPOLOGY_NOT_FOUND", f"No typology card with code '{code}'.")
    try:
        handbook = generate_handbook(card, client=client)
    except Exception as e:  # noqa: BLE001 — demo resilience: fall back to the curated checks
        logger.warning("Handbook RAG for %s failed (%s); serving the card's curated checks.", code, e)
        handbook = CoachingHandbook(
            typology_code=code,
            what_to_check=[HandbookCheck(check=q, source="curated typology card")
                           for q in (card.what_to_check or [])],
            sources=[],
        )
    return handbook.model_dump(by_alias=True, mode="json")


@app.post("/alerts/{alert_id}/triage")
def live_triage(alert_id: str, semantic: bool = False, client=Depends(get_llm_client)):
    """LIVE pipeline run (Q&A only). Returns a fresh TriageResult; never persists it.
    Falls back to the precomputed triage if the provider fails (ADR-0003). `?semantic=true` opts into
    the extra LLM semantic anchor pass (ADR-0013) — one cheap MODEL_VERIFIER call; off by default so a
    normal live run spends nothing extra."""
    alert = _require_alert(alert_id)
    begin_run_capture(alert_id, mode="live", semantic=semantic)
    try:
        # Stored record has triage; parse as Alert (an AlertInput) at this seam.
        result = run_triage(Alert.model_validate(alert), client=client, semantic=semantic)
        payload = result.model_dump(by_alias=True, mode="json")
        ledger = finish_run_capture("completed", final_output=payload)
        if ledger:
            store.record_copilot_run(ledger)
        return payload
    except Exception as e:  # noqa: BLE001 — demo resilience: replay precomputed on any failure
        logger.warning("Live triage for %s failed (%s); serving precomputed fallback.", alert_id, e)
        enrich_served_alert(alert)  # parity with GET /alerts/{id}: same serve-time suppression
        ledger = finish_run_capture("fallback", final_output=alert["triage"], error=str(e))
        if ledger:
            store.record_copilot_run(ledger)
        return alert["triage"]


@app.get("/alerts/{alert_id}/triage/stream")
def live_triage_stream(alert_id: str, semantic: bool = False, client=Depends(get_llm_client)):
    """LIVE pipeline run, streamed as Server-Sent Events so the UI can show the agent's
    reasoning step-by-step as each stage actually completes (Q&A 'thinking' view). Never
    persists. On any provider failure it emits an error event then the precomputed result,
    so the demo still resolves (ADR-0003). Cost-sensitive, to match the served demo data.
    `?semantic=true` adds the LLM semantic anchor stage (ADR-0013); off by default."""
    alert = _require_alert(alert_id)

    def gen():
        begin_run_capture(alert_id, mode="live", semantic=semantic)
        try:
            for ev in run_triage_events(
                Alert.model_validate(alert), client=client, cost_sensitive=True, semantic=semantic):
                if ev["type"] == "result":
                    payload = {"type": "result", "triage": ev["triage"].model_dump(by_alias=True, mode="json")}
                    ledger = finish_run_capture("completed", final_output=payload["triage"])
                    if ledger:
                        store.record_copilot_run(ledger)
                else:
                    payload = ev
                yield f"data: {json.dumps(payload)}\n\n"
        except Exception as e:  # noqa: BLE001 — demo resilience: fall back to precomputed
            logger.warning("Live triage stream for %s failed (%s); serving precomputed fallback.", alert_id, e)
            yield f"data: {json.dumps({'type': 'error', 'message': 'Live run failed; showing the precomputed result.'})}\n\n"
            enrich_served_alert(alert)  # parity with GET /alerts/{id}: same serve-time suppression
            ledger = finish_run_capture("fallback", final_output=alert["triage"], error=str(e))
            if ledger:
                store.record_copilot_run(ledger)
            yield f"data: {json.dumps({'type': 'result', 'triage': alert['triage']})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.post("/alerts/{alert_id}/decision")
def decide(
    alert_id: str,
    body: DecisionRequest,
    actor: Actor = Depends(require_actor("analyst", "compliance")),
):
    """Analyst approve/override → updates status (+ STR per disposition), returns the Alert."""
    alert = _require_alert(alert_id)
    expected_disposition = final_disposition_for(alert["triage"]["recommendation"], body.action)
    if body.final_disposition != expected_disposition:
        raise ApiError(
            422,
            "DECISION_DISPOSITION_MISMATCH",
            "finalDisposition must match the stored AI recommendation and requested decision action.",
        )
    normalized_note = body.note.strip() if body.note and body.note.strip() else None
    if body.action == "override" and normalized_note is None:
        raise ApiError(
            422,
            "OVERRIDE_REASON_REQUIRED",
            "Override decisions require an analyst reason in note.",
        )
    decision = Decision(
        alert_id=alert_id,
        action=body.action,
        final_disposition=body.final_disposition,
        edited_str_draft=body.edited_str_draft,
        note=normalized_note,
        decided_at=now_local(),
        actor_id=actor.actor_id,
        actor_role=actor.actor_role,
    )

    new_status = "approved" if decision.action == "approve" else "overridden"
    # The disposition->STR invariant lives in decision.resolve_str_draft (reset restores it).
    new_str_draft = resolve_str_draft(
        alert["triage"]["strDraft"], decision.final_disposition, decision.edited_str_draft
    )
    # Persist the decision's effect on the alert row (survives restart), the decision
    # record (the filing gate), and the audit event — all in the DB.
    store.set_alert_decision(alert_id, new_status, new_str_draft)
    store.record_decision(alert_id, decision.model_dump(by_alias=True, mode="json"))
    learn_from_decision(alert, decision)  # Slice A: a benign dismiss teaches a suppression pattern
    alert["status"] = new_status
    alert["triage"]["strDraft"] = new_str_draft
    triage = alert["triage"]
    store.append_audit(AuditEntry(
        alert_id=alert_id,
        event="decision",
        at=decision.decided_at,
        action=decision.action,
        ai_recommendation=triage["recommendation"],
        final_disposition=decision.final_disposition,
        confidence=triage["confidence"],
        verifier_status=triage["verifier"]["status"],
        note=decision.note,
        actor_id=actor.actor_id,
        actor_role=actor.actor_role,
    ).model_dump(by_alias=True, mode="json"))
    return alert


def _require_escalate_signoff(alert_id: str) -> tuple[Alert, dict]:
    """The STR filing gate, recomputed live from the current decision: an STR exists
    only after an analyst signs off on an escalation. Raises 409 (no decision /
    dismissed) so a later change-of-mind revokes both export and submission. Returns
    the validated Alert plus its decision record."""
    alert_dict = _require_alert(alert_id)
    decision = store.get_decision(alert_id)
    if decision is None:
        raise ApiError(
            409, "STR_NOT_ADJUDICATED",
            "Alert has not been adjudicated; an STR cannot be filed until an analyst signs off.",
        )
    if decision["finalDisposition"] != "escalate":
        raise ApiError(409, "STR_DISMISSED", "Alert was dismissed; there is no STR to file.")
    alert = Alert.model_validate(alert_dict)
    if alert.triage.str_draft is None:  # invariant: an escalate decision keeps the draft
        raise ApiError(409, "STR_DISMISSED", "No STR draft is present for this alert.")
    return alert, decision


@app.get("/alerts/{alert_id}/str.xml")
def export_goaml_str(alert_id: str):
    """Export the approved STR as a schema-valid goAML STR report (the integration seam)."""
    alert, decision = _require_escalate_signoff(alert_id)
    try:
        xml = to_goaml_str_xml(
            alert.triage.str_draft,
            alert.transactions or [],
            _GOAML_CONFIG,
            submission_date=datetime.fromisoformat(decision["decidedAt"]),
        )
    except ValueError as exc:
        raise ApiError(422, "GOAML_EXPORT_FAILED", str(exc)) from exc
    return Response(content=xml, media_type="application/xml")


@app.post("/alerts/{alert_id}/str/submit")
def submit_goaml_str(alert_id: str, actor: Actor = Depends(require_actor("compliance"))):
    """File the approved STR and return the FIU acknowledgement. Generates+validates
    the goAML report (so an unfileable report can't be acked), records the filing in
    the audit trail, and returns a demo-stable submission reference."""
    alert, decision = _require_escalate_signoff(alert_id)
    try:
        to_goaml_str_xml(  # validate the report is well-formed before acknowledging it
            alert.triage.str_draft, alert.transactions or [], _GOAML_CONFIG,
            submission_date=datetime.fromisoformat(decision["decidedAt"]),
        )
    except ValueError as exc:
        raise ApiError(422, "GOAML_EXPORT_FAILED", str(exc)) from exc
    ack = SubmissionAck(
        alert_id=alert_id,
        submission_ref=submission_reference(alert_id),
        status="accepted",
        submitted_at=now_local(),
        actor_id=actor.actor_id,
        actor_role=actor.actor_role,
    )
    store.append_audit(AuditEntry(
        alert_id=alert_id,
        event="submission",
        at=ack.submitted_at,
        submission_ref=ack.submission_ref,
        actor_id=actor.actor_id,
        actor_role=actor.actor_role,
    ).model_dump(by_alias=True, mode="json"))
    return ack.model_dump(by_alias=True, mode="json")


@app.get("/audit")
def get_audit():
    """The append-only accountability trail, newest first (decisions + submissions)."""
    return list(reversed(store.all_audit()))


@app.get("/audit/summary")
def get_audit_summary():
    """Session AI–analyst agreement, computed from the audit log's `decision` events — the
    authoritative record, so every client agrees (vs. a per-client tally that would drift).
    Decision-scoped: autoClear / debateResolved / submission events never count. `agreementRate`
    is null until a decision is made. A session-activity signal, NOT held-out performance
    (that is /metrics) — surfaced on the audit trail, never the performance dashboard."""
    decisions = [e for e in store.all_audit() if e["event"] == "decision"]
    approvals = sum(1 for e in decisions if e.get("action") == "approve")
    n = len(decisions)
    return DecisionSummary(
        decisions=n,
        approvals=approvals,
        overrides=n - approvals,
        agreement_rate=round(approvals / n, 4) if n else None,
    ).model_dump(by_alias=True, mode="json")


def _qa_summary() -> QAOutcomeSummary:
    outcomes = [QAOutcome.model_validate(o) for o in store.all_qa_outcomes()]
    confirmed = sum(1 for o in outcomes if o.outcome == "confirmedClear")
    missed = sum(1 for o in outcomes if o.outcome == "missedSuspicion")
    reviewed = len(outcomes)
    return QAOutcomeSummary(
        reviewed=reviewed,
        confirmed_clears=confirmed,
        missed_suspicion=missed,
        miss_rate=round(missed / reviewed, 4) if reviewed else None,
        outcomes=outcomes,
    )


@app.post("/alerts/{alert_id}/qa-outcome", response_model=QAOutcome)
def record_qa_outcome(
    alert_id: str,
    body: QAOutcomeRequest,
    actor: Actor = Depends(require_actor("qa", "compliance")),
):
    """Record QA review of an auto-cleared or sampled alert.

    This is the feedback loop banks need before trusting limited automation: a sampled clear can be
    confirmed, or marked as missed suspicion, without changing thresholds silently.
    """
    alert = _require_alert(alert_id)
    normalized_note = body.note.strip()
    if not normalized_note:
        raise ApiError(422, "QA_NOTE_REQUIRED", "QA outcome requires a reviewer note.")
    enrich_served_alert(alert)
    _apply_control(alert)
    sampled = bool(alert.get("qaSampled"))
    outcome = QAOutcome(
        alert_id=alert_id,
        outcome=body.outcome,
        reviewer=body.reviewer.strip() or "aml-qa",
        note=normalized_note,
        reviewed_at=now_local(),
        source="qaSample" if sampled else "manualReview",
        evidence_endpoints=[
            f"/alerts/{alert_id}/defense-case",
            f"/alerts/{alert_id}/decision-trace",
            f"/alerts/{alert_id}/copilot-runs/precomputed-current/ledger",
        ],
        actor_id=actor.actor_id,
        actor_role=actor.actor_role,
    )
    payload = outcome.model_dump(by_alias=True, mode="json")
    store.record_qa_outcome(payload)
    store.append_audit(AuditEntry(
        alert_id=alert_id,
        event="qaOutcome",
        at=outcome.reviewed_at,
        ai_recommendation=alert["triage"]["recommendation"],
        confidence=alert["triage"]["confidence"],
        verifier_status=alert["triage"]["verifier"]["status"],
        note=f"{outcome.outcome}: {outcome.note}",
        actor_id=actor.actor_id,
        actor_role=actor.actor_role,
    ).model_dump(by_alias=True, mode="json"))
    return payload


@app.get("/qa/outcomes", response_model=QAOutcomeSummary)
def get_qa_outcomes():
    """QA outcomes recorded against sampled/manual reviewed clears."""
    return _qa_summary().model_dump(by_alias=True, mode="json")


def _access_control_posture() -> AccessControlPosture:
    return AccessControlPosture(
        mode="actorRoleHeaders",
        demo_fallback_actor=_DEMO_FALLBACK_ACTOR,
        rules=[
            AccessControlRule(
                endpoint="/alerts/{alert_id}/decision",
                method="POST",
                allowed_roles=["analyst", "compliance", "admin"],
                control="Only an analyst/compliance actor can approve or override the AI recommendation; overrides still require a reason.",
                audit_event="decision",
            ),
            AccessControlRule(
                endpoint="/alerts/{alert_id}/str/submit",
                method="POST",
                allowed_roles=["compliance", "admin"],
                control="Filing requires an existing analyst escalation decision plus a compliance-capable actor at submission time.",
                audit_event="submission",
            ),
            AccessControlRule(
                endpoint="/alerts/{alert_id}/qa-outcome",
                method="POST",
                allowed_roles=["qa", "compliance", "admin"],
                control="QA outcomes can only be recorded by QA/compliance actors and are written to the audit trail.",
                audit_event="qaOutcome",
            ),
            AccessControlRule(
                endpoint="/governance/change-requests",
                method="POST",
                allowed_roles=["modelRisk", "compliance", "security", "amlOps", "admin"],
                control="Governance changes are recorded as proposed/rejected unless required role approvals are present for approved/applied status.",
                audit_event="governanceChange",
            ),
            AccessControlRule(
                endpoint="/reset",
                method="POST",
                allowed_roles=["admin"],
                control="Reset is an administrative operation and is blocked for ordinary analyst/QA actors.",
                audit_event="reset",
            ),
        ],
        four_eyes_controls=[
            "STR submission is separated from the decision endpoint: an escalation decision exists first, then a compliance-capable actor files.",
            "Governance changes with approved/applied status must carry approvals for every required role.",
            "Every protected write records actor id/role either in the returned contract, the audit trail, or both.",
        ],
        non_claims=[
            "This is not production SSO; it is the authorization seam a bank would bind to OIDC/JWT claims.",
            "The demo fallback actor exists so filmed demos and tests still run without an identity provider.",
            "Role checks do not make synthetic metrics production authorization.",
        ],
    )


@app.get("/security/access-control", response_model=AccessControlPosture)
def get_access_control_posture():
    """Machine-readable actor/role contract for protected writes."""
    return _access_control_posture().model_dump(by_alias=True, mode="json")


def _default_governance_changes() -> list[GovernanceChangeRequest]:
    requested_at = now_local()
    return [
        GovernanceChangeRequest(
            change_id="chg-threshold-auto-clear-hardening",
            type="thresholdChange",
            status="proposed",
            requested_by="model-risk",
            requested_at=requested_at,
            current_value={
                "review": config.REVIEW_THRESHOLD,
                "autoClear": config.AUTO_CLEAR_THRESHOLD,
                "qaSample": config.QA_SAMPLE_RATE,
            },
            proposed_value={
                "autoClear": min(0.95, round(config.AUTO_CLEAR_THRESHOLD + 0.05, 2)),
                "qaSample": min(1.0, round(config.QA_SAMPLE_RATE + 0.1, 2)),
            },
            rationale="Raise the auto-clear bar until bank historical replay and QA outcomes prove leakage remains inside tolerance.",
            evidence=[
                "/governance/validation-dossier",
                "/metrics",
                "/qa/outcomes",
                "/alerts/HERO-002/decision-trace",
            ],
            required_approvals=["compliance", "modelRisk"],
            approvals=[],
            rollback_plan="Restore previous thresholds, replay the shadow sample, and compare auto-clear leakage plus QA miss rate.",
            non_claims=[
                "This proposal does not mutate runtime thresholds.",
                "Threshold changes require approval and deployment outside the demo API.",
            ],
        ),
        GovernanceChangeRequest(
            change_id="chg-prompt-ledger-versioning",
            type="promptTemplate",
            status="proposed",
            requested_by="aml-ops",
            requested_at=requested_at,
            current_value={"promptVersion": "captured-runtime-envelope"},
            proposed_value={"requiredLedgerFields": ["templateId", "contentHash", "schemaValid", "rawResponseHash"]},
            rationale="Prevent silent prompt drift by requiring every live copilot run to preserve prompt template ids and response validation evidence.",
            evidence=[
                "/alerts/HERO-002/copilot-runs/precomputed-current/ledger",
                "/readiness/summary",
            ],
            required_approvals=["modelRisk", "security"],
            approvals=[],
            rollback_plan="Revert to the previous prompt template id and compare ledger hashes against the last approved run.",
            non_claims=[
                "This record governs prompt transparency; it does not expose DeepSeek chain-of-thought.",
            ],
        ),
    ]


def _governance_change_list() -> GovernanceChangeRequestList:
    custom = [GovernanceChangeRequest.model_validate(c) for c in store.all_governance_changes()]
    by_id = {c.change_id: c for c in _default_governance_changes()}
    by_id.update({c.change_id: c for c in custom})
    changes = sorted(by_id.values(), key=lambda c: c.requested_at, reverse=True)
    approved = sum(1 for c in changes if c.status in {"approved", "applied"})
    pending = sum(1 for c in changes if c.status == "proposed")
    return GovernanceChangeRequestList(
        mode="modelRiskChangeControl",
        pending=pending,
        approved=approved,
        blocked_reason="Runtime config is immutable from the API; changes require explicit approval and deployment.",
        changes=changes,
    )


@app.get("/governance/change-requests", response_model=GovernanceChangeRequestList)
def get_governance_change_requests():
    """Model-risk change control: no silent threshold/model/prompt/card changes."""
    return _governance_change_list().model_dump(by_alias=True, mode="json")


@app.post("/governance/change-requests", response_model=GovernanceChangeRequest)
def propose_governance_change(
    body: GovernanceChangeRequest,
    actor: Actor = Depends(require_actor("modelRisk", "compliance", "security", "amlOps")),
):
    if body.status not in {"proposed", "rejected"}:
        approval_roles = {approval.role for approval in body.approvals}
        missing = set(body.required_approvals) - approval_roles
        if missing:
            raise ApiError(
                422,
                "APPROVAL_REQUIRED",
                f"Approved/applied changes must carry approvals for: {', '.join(sorted(missing))}.",
            )
        if actor.actor_role != "admin" and actor.actor_role not in approval_roles:
            raise ApiError(
                403,
                "APPROVER_ROLE_REQUIRED",
                "The submitting actor must be one of the approval roles on approved/applied changes.",
            )
    payload = body.model_dump(by_alias=True, mode="json")
    store.record_governance_change(payload)
    return payload


@app.get("/queue/briefing")
def get_briefing():
    """The Queue Agent's Shift Briefing (ADR-0010) — the precomputed overnight-run summary
    the analyst sees on arrival. 404s in contract shape until precompute has written it."""
    if not _BRIEFING.exists():
        raise ApiError(404, "BRIEFING_NOT_READY", "shift_briefing.json has not been generated yet.")
    data = json.loads(_BRIEFING.read_text(encoding="utf-8"))
    return ShiftBriefing.model_validate(data).model_dump(by_alias=True, mode="json")


@app.get("/metrics")
def get_metrics():
    """Serve metrics.json (Phase 8). 404s in contract shape until that artifact exists."""
    if not _METRICS.exists():
        raise ApiError(404, "METRICS_NOT_READY", "metrics.json has not been generated yet (Phase 8).")
    data = json.loads(_METRICS.read_text(encoding="utf-8"))
    # Auto-clear false-negative leakage (ADR-0019): derived serve-time & token-free from the locked
    # aggregates, so the ADR-0012 numbers stay locked. Guarded for a pre-auto-clear metrics.json.
    if {"autoClearedShare", "autoClearPrecision", "confusionMatrix"} <= data.keys():
        data.update(auto_clear_leakage(data))
    return Metrics.model_validate(data).model_dump(by_alias=True, mode="json")


@app.get("/operations/impact", response_model=OperationalImpact)
def get_operational_impact():
    """Shift-level operations impact derived from the Queue Agent run and locked metrics.

    This is the practical problem-relevance artifact: how much analyst work the current
    demo shift removes, how much remains human-gated, and which assumptions must be
    replaced by bank data before making production claims.
    """
    briefing = ShiftBriefing.model_validate(get_briefing())
    metrics = Metrics.model_validate(get_metrics())

    qa_sample_alerts = max(1, round(briefing.auto_cleared * config.QA_SAMPLE_RATE)) if briefing.auto_cleared else 0
    baseline_minutes = round(briefing.processed * metrics.avg_review_time_baseline_min, 1)
    assisted_minutes = round(
        briefing.needs_review * metrics.avg_review_time_with_copilot_min + qa_sample_alerts * 5,
        1,
    )
    minutes_returned = round(max(0.0, baseline_minutes - assisted_minutes), 1)
    impact = OperationalImpact(
        mode="shiftImpact",
        processed_alerts=briefing.processed,
        auto_cleared_alerts=briefing.auto_cleared,
        human_review_alerts=briefing.needs_review,
        qa_sample_alerts=qa_sample_alerts,
        escalations_held_for_signoff=briefing.escalations,
        verifier_flagged=briefing.flagged,
        baseline_review_minutes=baseline_minutes,
        assisted_review_minutes=assisted_minutes,
        minutes_returned=minutes_returned,
        analyst_hours_returned=round(minutes_returned / 60, 2),
        queue_reduction_rate=round(briefing.auto_cleared / briefing.processed, 4) if briefing.processed else 0.0,
        review_focus_multiplier=round(briefing.processed / max(1, briefing.needs_review), 2),
        assumptions=[
            f"Baseline review time uses the locked metric artifact: {metrics.avg_review_time_baseline_min:g} minutes per alert.",
            f"Assisted review time uses the locked metric artifact: {metrics.avg_review_time_with_copilot_min:g} minutes per human-reviewed alert.",
            "QA sample effort is modeled at 5 minutes per sampled auto-clear for demo impact only.",
        ],
        control_checks=[
            "Escalations remain in human review and cannot be auto-filed.",
            "Verifier-flagged, screening-hit, debated, revoked, or low-confidence cases stay in needsReview.",
            "Auto-cleared cases remain inspectable through the cleared lane and QA sample.",
            "Production impact must be remeasured on bank historical replay before release.",
        ],
        demo_narrative=(
            f"The operational problem is alert overload: this shift started with {briefing.processed} alerts. "
            f"The Queue Agent removed {briefing.auto_cleared} from the analyst inbox, left "
            f"{briefing.needs_review} for judgment, and returned about {minutes_returned / 60:.1f} analyst hours "
            "while keeping escalations, flagged cases, and QA sampling human-visible."
        ),
        caveat=(
            "This is a shift-level demo calculation, not a production ROI claim; a bank pilot must replace "
            "the review-time and QA assumptions with its own case data, staffing model, and leakage tolerance."
        ),
    )
    return impact.model_dump(by_alias=True, mode="json")


def _suppression_frontier() -> SuppressionFrontier | None:
    """The closed-loop suppression leakage/coverage frontier (ADR-0021) from
    data/suppression_metrics.json, if the token-free eval has run. Derives the achievable
    trade-off curve (min leakage at each coverage) for the plot. Never fabricated."""
    if not _SUPPRESSION.exists():
        return None
    d = json.loads(_SUPPRESSION.read_text(encoding="utf-8"))

    def pt(o: dict) -> SuppressionPoint:
        return SuppressionPoint(
            coverage=o["coverage"], leakage=o["leakage"],
            leakage95_upper=o.get("leakage95Upper"),
            suppressed=o.get("suppressed"), leaked=o.get("leaked"))

    # Achievable frontier: the minimum leakage reached at each distinct coverage level, so the
    # curve traces the honest trade-off (more coverage costs more leakage) without plotting all 36
    # configs. Sorted by coverage.
    best: dict[float, dict] = {}
    for p in d.get("frontier") or []:
        c = round(p["coverage"], 3)
        if c not in best or p["leakage"] < best[c]["leakage"]:
            best[c] = p
    curve = [pt(best[c]) for c in sorted(best)]
    return SuppressionFrontier(
        n=d["n"], n_benign=d["nBenign"], naive=pt(d["naiveBaseline"]),
        operating_point=pt(d["operatingPoint"]), curve=curve,
        headline=d["headline"], caveat=d["caveat"])


@app.get("/governance")
def get_governance():
    """Model-governance snapshot (ADR-0020): the model, the operating-point thresholds, the last
    held-out validation (real date + model + numbers), session override monitoring, and the
    security-posture roadmap — the 'is this model-risk-managed?' surface (SR 11-7 / BNM). Assembled
    serve-time from config + metrics.json + the audit trail; never fabricated."""
    metrics = json.loads(_METRICS.read_text(encoding="utf-8")) if _METRICS.exists() else {}
    leak = (
        auto_clear_leakage(metrics)
        if {"autoClearedShare", "autoClearPrecision", "confusionMatrix"} <= metrics.keys()
        else {}
    )
    decisions = [e for e in store.all_audit() if e["event"] == "decision"]
    overrides = sum(1 for e in decisions if e.get("action") == "override")
    n_dec = len(decisions)
    gov = Governance(
        model=GovernanceModel(
            workhorse=config.MODEL_WORKHORSE,
            verifier=config.MODEL_VERIFIER,
            provider=config.LLM_PROVIDER,
        ),
        thresholds=GovernanceThresholds(
            review=config.REVIEW_THRESHOLD,
            auto_clear=config.AUTO_CLEAR_THRESHOLD,
            qa_sample=config.QA_SAMPLE_RATE,
            borderline_margin=config.BORDERLINE_MARGIN,
        ),
        validation=GovernanceValidation(
            validated_at=metrics.get("validatedAt"),
            model=metrics.get("model"),
            n=metrics.get("totalAlerts"),
            recall=metrics.get("recall"),
            auto_clear_leakage_rate=leak.get("autoClearLeakageRate"),
            auto_clear_precision=metrics.get("autoClearPrecision"),
            measured_typologies=metrics.get("measuredTypologies") or [],
            roadmap_typologies=metrics.get("roadmapTypologies") or [],
        ),
        override=GovernanceOverride(
            decisions=n_dec,
            overrides=overrides,
            override_rate=round(overrides / n_dec, 4) if n_dec else None,
        ),
        security_posture=_SECURITY_POSTURE,
        suppression_frontier=_suppression_frontier(),
    )
    return gov.model_dump(by_alias=True, mode="json")


@app.get("/integration/contract", response_model=BankIntegrationContract)
def get_integration_contract():
    """Bank-facing integration contract: required data, outputs, non-goals, and rollout gates."""
    contract = BankIntegrationContract(
        mode="shadowFirst",
        inbound_systems=[
            "SAS AML / Actimize / Mantas / existing bank rule engine",
            "Core banking account profile",
            "Ledger / payment transaction window",
            "Case-management disposition history for validation",
        ],
        workflow=_INTEGRATION_WORKFLOW,
        minimum_required_fields=_MINIMUM_INTEGRATION_FIELDS,
        optional_enrichments=_OPTIONAL_INTEGRATION_FIELDS,
        outbound_artifacts=[
            "needsReview queue routing",
            "autoCleared queue routing with QA-sample flag",
            "typed defense-case packet per alert",
            "dismissal record for cleared alerts",
            "schema-valid goAML XML only after escalation sign-off",
            "append-only audit events for auto-clear, decision, debate, and filing",
        ],
        production_gates=[
            "Run read-only historical replay before touching live workflow.",
            "Compare recommendations against known analyst dispositions and confirmed STR/no-STR outcomes.",
            "Approve operating thresholds with compliance/model-risk owners.",
            "Enable auto-clear only for dismiss + verifier-agreed + threshold-gated alerts.",
            "Keep QA sampling, override monitoring, and audit replay always on.",
        ],
        non_goals=[
            "Does not replace the bank's source transaction-monitoring system.",
            "Does not auto-file STRs or auto-escalate without analyst sign-off.",
            "Does not infer missing KYC fields from public datasets.",
            "Does not train silently from analyst overrides; governance review decides threshold/card changes.",
        ],
    )
    return contract.model_dump(by_alias=True, mode="json")


@app.get("/production/trust-plan", response_model=ProductionTrustPlan)
def get_production_trust_plan():
    """Production trust plan answering bank integration, data access, false-positive governance, and validation."""
    plan = ProductionTrustPlan(
        mode="productionTrustPlan",
        position=(
            "VerdictAML does not ask a bank to trust demo auto-clear. It asks for a read-only pilot "
            "where existing AML alerts are replayed through explicit data, control, and validation gates "
            "before any suppression or escalation recommendation can affect production work."
        ),
        target_systems=[
            "Existing transaction-monitoring engine: SAS AML, Actimize, Mantas, Oracle FCCM, or equivalent rule engine.",
            "Core banking and KYC profile store for account age, customer segment, occupation, expected activity, and risk rating.",
            "Ledger, payments, and channel logs for the alert transaction window plus running balance.",
            "Case-management system for analyst dispositions, override reasons, QA review, and confirmed STR/no-STR outcomes.",
            "Screening/watchlist service for sanctions, PEP, adverse media, and previous match snapshots.",
            "FIU/goAML filing rail as a human-approved export target, never an autonomous filing target.",
        ],
        minimum_data_access=[
            "Alert id, trigger/rule id, risk score, created timestamp, and source system.",
            "Subject account id, account type, opened date, customer risk rating, and KYC expected activity.",
            "Transaction id, timestamp, direction, amount, currency, channel, counterparty, and running balance.",
            "Screening snapshot showing whether sanctions, PEP, or adverse-media matches exist at decision time.",
            "Historical analyst disposition, QA result, override reason, and confirmed STR/no-STR outcome for validation.",
            "Policy thresholds and suppression exceptions approved by compliance/model-risk owners.",
        ],
        governance_controls=[
            "Auto-clear can only be a dismiss recommendation with verifier agreement, no screening hit, no adversarial debate, and confidence above threshold.",
            "Every auto-cleared item remains QA-sampled and replayable with evidence, threshold, verifier, screening, and audit provenance.",
            "Analyst override reasons feed governance review; they do not silently retrain or change thresholds.",
            "Learned suppression is bounded by pattern provenance, leakage measurement, and network revocation when risk reappears.",
            "STR drafting and goAML export remain blocked until human escalation sign-off and evidence anchoring pass.",
        ],
        validation_gates=[
            "Read-only historical replay on bank alerts before live workflow impact.",
            "Compare recommendations against analyst dispositions, QA decisions, and confirmed STR/no-STR outcomes.",
            "Calibrate thresholds against bank-approved leakage tolerance and typology coverage gaps.",
            "Run a shadow pilot where analysts see recommendations but production queues and filings remain unchanged.",
            "Model-risk, compliance, information-security, and rollback sign-off before limited production automation.",
        ],
        items=[
            ProductionTrustItem(
                area="integration",
                requirement="Show where the product sits in a real AML stack.",
                implementation="Post-monitoring, pre-case-handling: VerdictAML consumes existing alerts and returns queue routing, defense cases, QA flags, audit events, and human-gated goAML exports.",
                evidence_endpoints=["/integration/contract", "/architecture/technical"],
                production_gate="No source detector replacement; pilot starts read-only against historical alerts.",
            ),
            ProductionTrustItem(
                area="dataAccess",
                requirement="State exactly what bank data is required.",
                implementation="Minimum access is alert metadata, KYC/account profile, transaction window with running balance, screening snapshot, and historical disposition/outcome labels.",
                evidence_endpoints=["/production/trust-plan", "/integration/contract"],
                production_gate="No production claim until bank data owners approve field mapping and retention boundaries.",
            ),
            ProductionTrustItem(
                area="falsePositiveGovernance",
                requirement="Govern false positives without creating false clears.",
                implementation="Suppression only applies when verifier, screening, debate, threshold, QA, leakage, and revocation controls agree that the case can leave the primary inbox.",
                evidence_endpoints=["/governance/validation-dossier", "/queue/briefing"],
                production_gate="Suppression starts shadow-only; limited automation requires approved leakage tolerance and QA sample results.",
            ),
            ProductionTrustItem(
                area="validation",
                requirement="Define what must be proven before recommendations are trusted.",
                implementation="Historical replay and shadow pilot compare recommendations to analyst dispositions, QA results, and confirmed STR/no-STR outcomes before thresholds move.",
                evidence_endpoints=["/metrics", "/governance/validation-dossier", "/pilot/adoption-plan"],
                production_gate="Synthetic metrics are evidence of the validation machinery, not authorization for bank production.",
            ),
            ProductionTrustItem(
                area="productionGate",
                requirement="Prevent unsafe auto-clear or auto-escalation.",
                implementation="Consequential actions stay human-gated; readiness verifies every finals contract and production rollout requires model-risk, compliance, security, and rollback sign-off.",
                evidence_endpoints=["/readiness/summary", "/finals/evidence-bundle"],
                production_gate="No autonomous STR filing, no autonomous escalation, no clearing screening hits, and no clearing unanchored suspicious activity.",
            ),
        ],
        judge_response=(
            "The objection is valid. A bank should not trust our demo to auto-clear production alerts. "
            "What we can prove now is the integration, data, governance, and validation contract a bank would "
            "use to decide whether limited automation is safe after replay and shadow pilot evidence."
        ),
        non_claims=[
            "Synthetic held-out metrics are not bank-production performance.",
            "No autonomous STR filing or autonomous escalation.",
            "No clearing of sanctions, PEP, adverse-media, debated, or unanchored suspicious-activity cases.",
            "No replacement of SAS AML, Actimize, Mantas, Oracle FCCM, or the bank source detector.",
            "No threshold or suppression change without compliance/model-risk governance.",
        ],
    )
    return plan.model_dump(by_alias=True, mode="json")


@app.get("/architecture/technical", response_model=TechnicalArchitecture)
def get_technical_architecture():
    """Judge-facing technical architecture contract for the finals architecture rubric."""
    packet = TechnicalArchitecture(
        mode="technicalArchitecture",
        thesis=(
            "VerdictAML is an end-to-end AML triage workflow, not a standalone chatbot: existing "
            "bank alerts enter a typed API, agents generate controlled decisions, deterministic "
            "gates decide what can leave the human queue, and every action is replayable through "
            "evidence, audit, and readiness contracts."
        ),
        components=[
            ArchitectureComponent(
                id="bank-monitoring",
                name="Existing bank monitoring engine",
                layer="bank",
                responsibility="Emits alert id, trigger, risk score, account, and transaction window.",
                proof_endpoints=["/integration/contract"],
            ),
            ArchitectureComponent(
                id="api-store",
                name="FastAPI service and relational store",
                layer="api",
                responsibility="Serves typed contracts, persists alerts, decisions, audit events, and learned suppression patterns.",
                proof_endpoints=["/health", "/alerts", "/audit"],
            ),
            ArchitectureComponent(
                id="queue-agent",
                name="Queue Agent",
                layer="agent",
                responsibility="Runs the overnight queue split: autoCleared, needsReview, QA sample, blocked reasons, and next actions.",
                proof_endpoints=["/queue/briefing", "/operations/impact"],
            ),
            ArchitectureComponent(
                id="triage-agents",
                name="Triage, verifier, screening, and debate agents",
                layer="agent",
                responsibility="Match typologies, challenge decisions, screen counterparties, and preserve contested calls for humans.",
                proof_endpoints=["/alerts/HERO-002/defense-case", "/innovation/differentiation"],
            ),
            ArchitectureComponent(
                id="control-plane",
                name="Deterministic control plane",
                layer="control",
                responsibility="Applies thresholds, verifier gates, screening failsafes, QA sampling, STR filing gates, and readiness checks.",
                proof_endpoints=["/governance", "/governance/validation-dossier", "/readiness/summary"],
            ),
            ArchitectureComponent(
                id="analyst-ui",
                name="Analyst and judge dashboard",
                layer="ui",
                responsibility="Shows queue, evidence, network view, governance, defense artifacts, and judge Q&A from live contracts.",
                proof_endpoints=["/finals/evidence-bundle", "/finals/qna-defense"],
            ),
            ArchitectureComponent(
                id="filing-seam",
                name="goAML filing seam",
                layer="control",
                responsibility="Exports schema-valid goAML XML only after escalation signoff and evidence anchoring.",
                proof_endpoints=["/alerts/HERO-002/defense-case", "/integration/contract"],
            ),
        ],
        flows=[
            ArchitectureFlow(
                source="bank-monitoring",
                target="api-store",
                payload="Alert metadata plus ledger transaction window.",
                control="Input schema validation rejects malformed alert catalogs before persistence.",
            ),
            ArchitectureFlow(
                source="api-store",
                target="triage-agents",
                payload="Account, trigger, transactions, typology cards, screening data, and learned patterns.",
                control="LLM output is schema-validated; fallback serves precomputed triage for demo reliability.",
            ),
            ArchitectureFlow(
                source="triage-agents",
                target="control-plane",
                payload="Recommendation, confidence, verifier status, screening result, debate, STR draft, and suppression status.",
                control="Deterministic gates override model confidence for screening hits, verifier flags, debates, and low confidence.",
            ),
            ArchitectureFlow(
                source="control-plane",
                target="queue-agent",
                payload="Routing decision, QA sample flag, blocked reasons, and next operating moves.",
                control="Auto-clear is limited to verifier-agreed dismissals above threshold; QA sample remains inspectable.",
            ),
            ArchitectureFlow(
                source="queue-agent",
                target="analyst-ui",
                payload="Shift briefing, operational impact, alert queue, defense case, and audit trail.",
                control="Human actions write decision events; readiness validates every judge-facing contract.",
            ),
            ArchitectureFlow(
                source="analyst-ui",
                target="filing-seam",
                payload="Human-approved escalation and anchored STR draft.",
                control="goAML export is blocked until signoff, XML schema validation, and anchored grounds pass.",
            ),
        ],
        data_handling=[
            "Queue list omits embedded transactions; full ledger window loads only on alert detail.",
            "Defense cases cite transaction ids and controls without dumping the full ledger.",
            "Learned suppression stores source-decision provenance and bounded signatures, not silent model retraining.",
            "Pilot deployment starts read-only on historical alerts before any customer-impacting automation.",
        ],
        ai_execution=[
            "Triage agent maps evidence to AML typology indicators and a recommendation.",
            "Verifier agent independently challenges the first-pass decision.",
            "Debate is preserved when the verifier contests the call.",
            "Queue Agent converts per-alert decisions into a shift-level worklist plan.",
        ],
        reliability_controls=[
            "Typed Pydantic response models on judge-facing endpoints.",
            "In-process readiness validates health, metrics, governance, queue, operations, architecture, integration, pilot, innovation, Q&A, and evidence bundle.",
            "Auto-clear is threshold-gated, verifier-gated, screening-gated, QA-sampled, and shadow-only until bank replay.",
            "STR filing is human-gated and evidence-anchored.",
        ],
        demo_path=[
            "Open Operational Impact to state the workflow pain and measured shift effect.",
            "Open Technical Architecture to show the end-to-end flow and controls.",
            "Open Queue Agent briefing and click needsReview / QA sample lanes.",
            "Open HERO-002 defense case and network view to show explainability and hidden mule recall.",
            "Open Readiness Summary / Evidence Bundle to prove the referenced contracts are live.",
        ],
        caveat=(
            "This architecture is the finals demo deployment shape. Production deployment must replace "
            "demo fixtures with bank historical replay, identity/access controls, customer-data residency, "
            "and model-risk signoff."
        ),
    )
    return packet.model_dump(by_alias=True, mode="json")


@app.get("/pilot/adoption-plan", response_model=PilotAdoptionPlan)
def get_pilot_adoption_plan():
    """Conservative bank adoption plan for procurement/model-risk questions.

    This is the market-adoption defense: no claim of instant production rollout. It states the
    stakeholders, pilot phases, evidence, success criteria, procurement risks, and non-claims a
    bank-facing AML tool must satisfy.
    """
    plan = PilotAdoptionPlan(
        mode="bankPilot",
        target_segments=[
            "Malaysia/APAC mid-sized banks with high alert queues and limited analyst capacity.",
            "Digital banks and payment providers with fast-growing transaction volume.",
            "Financial institutions that already run SAS, Actimize, Mantas, or equivalent monitoring and need a defensible review overlay.",
        ],
        buyer_stakeholders=[
            "Head of AML operations",
            "Compliance / MLRO owner",
            "Model risk management",
            "Information security / data protection",
            "Core banking / case-management integration owner",
            "Procurement and legal",
        ],
        pilot_economics={
            "monthlyAlerts": 5000,
            "currentReviewMinutesPerAlert": 12,
            "assistedReviewMinutesPerAlert": 7,
            "qaSampleMinutesPerAlert": 5,
            "estimatedMonthlyHoursSaved": 360,
            "valueHypothesis": (
                "At 5,000 alerts/month, a conservative 5-minute handling reduction on reviewed alerts "
                "plus bounded auto-clear recovers ~360 analyst hours/month - about RM 216k/year at a "
                "fully-loaded RM 50/hour - while preserving QA. The RM 120k/year platform is priced "
                "below the analyst time it returns."
            ),
            "caveat": (
                "Pilot economics are a validation target, not a production claim; the bank must replace "
                "these assumptions with its own alert volume, salary bands, QA policy, and leakage tolerance."
            ),
        },
        sensitivity_cases=[
            {
                "monthlyAlerts": 1000,
                "minutesSavedPerAlert": 3,
                "estimatedMonthlyHoursReturned": 50,
                "caveat": "Low-volume pilot case; validates workflow quality before material ROI claims.",
            },
            {
                "monthlyAlerts": 5000,
                "minutesSavedPerAlert": 5,
                "estimatedMonthlyHoursReturned": 417,
                "caveat": "Mid-market operating case; replace with bank queue data during replay.",
            },
            {
                "monthlyAlerts": 20000,
                "minutesSavedPerAlert": 8,
                "estimatedMonthlyHoursReturned": 2667,
                "caveat": "Scale case; procurement must validate staffing, QA, and leakage tolerance before quoting value.",
            },
        ],
        commercial_model=[
            {
                "name": "Paid shadow pilot",
                "customerStage": "Historical replay and shadow validation",
                "pricingModel": "RM 50,000 (~US$11k) fixed for the 8-week pilot, creditable toward year 1; scoped by alert volume and integration effort.",
                "includes": [
                    "Data mapping and historical replay.",
                    "Validation dossier and leakage report.",
                    "Pilot business case using the bank's own alert volumes.",
                ],
                "conversionGate": "Compliance and model-risk owners accept success criteria and rollout plan.",
            },
            {
                "name": "Production assist",
                "customerStage": "Live triage with human-owned decisions",
                "pricingModel": "RM 120,000/year (~US$26k) platform including up to 5,000 reviewed alerts/month, plus RM 2 (~US$0.40) per additional reviewed alert (volume-tiered). Priced below the ~RM 216k/year of analyst time it returns at that volume.",
                "includes": [
                    "Queue triage, defense cases, QA sampling, and audit.",
                    "Human-gated STR/goAML export.",
                    "Readiness and governance reporting.",
                ],
                "conversionGate": "Security, legal, and operations sign off on live workflow integration.",
            },
            {
                "name": "Governed automation",
                "customerStage": "Limited auto-clear after bank validation",
                "pricingModel": "From RM 250,000/year (~US$53k), custom. Self-hosted open-weight model in the bank's VPC so data never leaves the perimeter (customer-provided or surcharged GPU); the LLM client is swappable by config.",
                "includes": [
                    "Approved auto-clear thresholds.",
                    "Ongoing leakage monitoring and rollback.",
                    "Model-risk change control and audit evidence bundle.",
                    "Self-hosted open-weight LLM inside the bank's VPC - data never leaves the perimeter.",
                ],
                "conversionGate": "Historical replay and shadow pilot show acceptable leakage under bank policy.",
            },
        ],
        competitive_positioning=[
            "VerdictAML is an overlay after existing transaction monitoring, not a replacement for SAS, Actimize, Mantas, Verafin, or the bank's rule engine.",
            "The commercial wedge is defensible false-positive reduction: queue triage, evidence replay, QA sampling, and human-gated filing.",
            "Compared with analyst outsourcing, VerdictAML keeps institutional knowledge, thresholds, audit, and model-risk controls inside the bank workflow.",
        ],
        pilot_timeline=[
            {
                "week": "Weeks 1-2",
                "objective": "Map fields, confirm data residency, and approve read-only access.",
                "owner": "IT / security / AML operations",
                "evidence": "/integration/contract plus security and data-flow review.",
            },
            {
                "week": "Weeks 3-5",
                "objective": "Run historical replay against known analyst dispositions.",
                "owner": "AML operations / model risk",
                "evidence": "/governance/validation-dossier with bank-known outcomes.",
            },
            {
                "week": "Weeks 6-7",
                "objective": "Run shadow pilot beside analysts without changing case outcomes.",
                "owner": "AML operations / compliance",
                "evidence": "Override review, QA pack, and weekly readiness summaries.",
            },
            {
                "week": "Week 8",
                "objective": "Decide whether limited production assist is justified.",
                "owner": "Compliance / model risk / procurement",
                "evidence": "Success criteria, leakage tolerance, business case, and rollout decision.",
            },
        ],
        phases=[
            {
                "name": "Read-only historical replay",
                "objective": "Run VerdictAML on historical alerts without touching the bank workflow.",
                "exitCriteria": [
                    "Input contract mapped to available bank fields.",
                    "Known analyst dispositions and STR/no-STR outcomes loaded for comparison.",
                    "No customer-impacting automation enabled.",
                ],
                "evidenceProduced": [
                    "Validation dossier on bank data.",
                    "Threshold recommendation with leakage and QA sampling.",
                    "Typology coverage and coverage-gap report.",
                ],
            },
            {
                "name": "Security and legal review",
                "objective": "Approve deployment shape, data residency, access controls, and audit obligations.",
                "exitCriteria": [
                    "Data processing and retention boundaries documented.",
                    "Cloud or on-prem LLM path approved.",
                    "Analyst identity and audit attribution design approved.",
                ],
                "evidenceProduced": [
                    "Architecture and data-flow diagram.",
                    "Access-control and audit-log plan.",
                    "PII minimisation and tokenisation plan.",
                ],
            },
            {
                "name": "Shadow pilot",
                "objective": "Run beside analysts on live alerts while the bank workflow remains authoritative.",
                "exitCriteria": [
                    "Override reasons reviewed with compliance.",
                    "Auto-clear leakage stays within approved tolerance.",
                    "goAML filing remains human-gated.",
                ],
                "evidenceProduced": [
                    "Weekly readiness summaries.",
                    "Override feedback report.",
                    "False-clear QA review pack.",
                ],
            },
            {
                "name": "Limited production gate",
                "objective": "Enable only bounded dismiss automation after sign-off.",
                "exitCriteria": [
                    "Compliance and model-risk owners approve operating thresholds.",
                    "Rollback procedure tested.",
                    "QA sampling and audit monitoring are always on.",
                ],
                "evidenceProduced": [
                    "Production threshold approval record.",
                    "Rollback runbook.",
                    "Ongoing monitoring dashboard.",
                ],
            },
        ],
        success_criteria=[
            "Recall and leakage measured against bank-known outcomes, not only public synthetic data.",
            "Reduction in analyst review volume without unreviewed sanctions/PEP hits or unanchored STR claims.",
            "Analyst override rate and reasons remain explainable to compliance.",
            "goAML export is accepted only after human escalation sign-off.",
        ],
        validation_evidence=[
            "Market pain: Nasdaq 2024 Global Financial Crime Report estimates $3.1T in illicit funds flowed through the financial system in 2023 and reports money mule activity among top AFC concerns.",
            "Budget pressure: LexisNexis Risk Solutions / Forrester 2023 True Cost of Financial Crime Compliance study reports 98% of financial institutions saw FCC cost increases.",
            "Adoption constraint: Federal Reserve SR 11-7 says material model use needs validation, effective challenge, governance, documentation, and ongoing monitoring.",
            "/metrics for held-out demo metrics.",
            "/governance/validation-dossier for validation gates and prohibited actions.",
            "/operations/impact for shift-level workload reduction and caveats.",
            "/integration/contract for the bank-system fields, outputs, gates, and non-goals.",
            "/readiness/summary for live contract availability.",
            "/finals/evidence-bundle for a single judge-facing evidence packet.",
            "Bank historical replay report before any production automation.",
        ],
        procurement_risks=[
            "Bank procurement and security review can take months, not days.",
            "Production use needs customer-data agreements, deployment approval, and model-risk sign-off.",
            "Confirmed STR/no-STR outcomes may be incomplete or delayed, affecting validation timeline.",
            "Integration effort depends on the bank's case-management and transaction-monitoring stack.",
        ],
        non_claims=[
            "No claim of immediate annual contract after a short pilot.",
            "No claim that synthetic metrics alone authorize production auto-clear.",
            "No unattended STR filing or escalation.",
            "No replacement of the bank's source transaction-monitoring system.",
        ],
    )
    return plan.model_dump(by_alias=True, mode="json")


@app.get("/innovation/differentiation", response_model=InnovationDifferentiation)
def get_innovation_differentiation():
    """Evidence-backed differentiation contract for the finals innovation question."""
    packet = InnovationDifferentiation(
        mode="evidenceBackedDifferentiation",
        thesis=(
            "VerdictAML is not differentiated by using an LLM. It is differentiated by the control "
            "system a bank needs to trust overnight AML queue reduction: analyst-taught suppression, "
            "deterministic policy gates, network revocation, adversarial verification, human-gated "
            "goAML export, and replayable defense cases."
        ),
        capabilities=[
            DifferentiatedCapability(
                name="Overnight queue trust workflow",
                generic_alternative="Demo a single alert explanation and leave the bank's daily worklist problem unresolved.",
                verdictaml_implementation=(
                    "The Queue Agent processes the alert queue before the analyst arrives, auto-clears "
                    "only verifier-agreed dismissals, leaves uncertain or consequential cases in "
                    "needsReview, and records the work in metrics, defense cases, and audit."
                ),
                proof_endpoints=["/queue/briefing", "/operations/impact", "/governance/validation-dossier", "/finals/evidence-bundle"],
                defense_value=(
                    "Shows the practical use case judges can trust: reduce false-positive workload "
                    "without hiding what was cleared, what was blocked, or what still needs a human."
                ),
                limitation=(
                    "Finals evidence proves the workflow and controls; production thresholds still "
                    "require bank historical replay and compliance sign-off."
                ),
            ),
            DifferentiatedCapability(
                name="Closed-loop suppression with network revocation",
                generic_alternative="Treat every false positive as a one-off review, or whitelist a pattern without a measured safety loop.",
                verdictaml_implementation=(
                    "A human dismissal can teach a suppression pattern for future look-alikes; the "
                    "pattern may auto-clear only inside the deterministic firewall, and mule-network "
                    "revocation cancels it if the cleared counterparty becomes a consolidation hub."
                ),
                proof_endpoints=["/governance/validation-dossier", "/alerts/HERO-002/defense-case", "/finals/evidence-bundle"],
                defense_value=(
                    "Turns analyst judgment into reusable workload reduction while preserving leakage "
                    "measurement, source-decision provenance, and an exploitation defense."
                ),
                limitation=(
                    "The leakage frontier is measured on the held-out slice; network revocation is "
                    "shown illustratively on frozen demo networks, not as a production aggregate rate."
                ),
            ),
            DifferentiatedCapability(
                name="Adversarial verifier and debate",
                generic_alternative="Single-pass LLM classification with a persuasive explanation.",
                verdictaml_implementation=(
                    "A verifier independently challenges the triage call; contested cases are routed "
                    "through debate and preserved in the defense case and audit trail."
                ),
                proof_endpoints=["/alerts/HERO-002/defense-case", "/queue/briefing"],
                defense_value="Shows why a recommendation survived challenge instead of trusting first-pass model confidence.",
                limitation="Still requires human judgment for flagged or consequential decisions.",
            ),
            DifferentiatedCapability(
                name="Mule-network recall layer",
                generic_alternative="Review each alert as an isolated transaction-monitoring hit.",
                verdictaml_implementation=(
                    "The network view recovers hidden mule behavior from shared counterparties and "
                    "distinguishes benign neighbors from laundering cluster members."
                ),
                proof_endpoints=["/alerts/HERO-002/network", "/alerts/HERO-002/defense-case"],
                defense_value="Turns Christopher's mule-network point into a concrete demo beat, not a slide claim.",
                limitation="Network evidence is qualitative in the demo; production metrics need bank graph data.",
            ),
            DifferentiatedCapability(
                name="Human-gated goAML export",
                generic_alternative="Generate a narrative STR draft and leave filing controls implicit.",
                verdictaml_implementation=(
                    "goAML XML is schema-validated and blocked unless the alert is escalated, human-signed, "
                    "and the STR grounds are anchored to cited evidence."
                ),
                proof_endpoints=["/alerts/HERO-002/defense-case", "/integration/contract"],
                defense_value="Makes the filing seam auditable and bounded instead of letting an LLM imply a report.",
                limitation="The demo validates/export-controls the XML; real submission depends on bank/FIU filing rails.",
            ),
            DifferentiatedCapability(
                name="Machine-readable defense case",
                generic_alternative="A UI explanation card that cannot be independently verified.",
                verdictaml_implementation=(
                    "Each alert exposes evidence, verifier status, auto-clear controls, STR gates, and audit "
                    "events as a typed API contract."
                ),
                proof_endpoints=["/alerts/HERO-002/defense-case", "/finals/evidence-bundle"],
                defense_value="Lets a judge or compliance reviewer replay why the system cleared, escalated, or blocked action.",
                limitation="The packet proves provenance and controls; it does not prove the bank will approve every judgment.",
            ),
            DifferentiatedCapability(
                name="Shadow-first auto-clear governance",
                generic_alternative="Advertise automation percentage as a production-ready outcome.",
                verdictaml_implementation=(
                    "Auto-clear is bounded by thresholds, verifier agreement, screening failsafes, leakage "
                    "measurement, QA sampling, and bank pilot release gates."
                ),
                proof_endpoints=["/governance/validation-dossier", "/pilot/adoption-plan", "/readiness/summary"],
                defense_value="Answers Rahiman's false-clear concern by making automation conditional and measurable.",
                limitation="Synthetic metrics are demo evidence only; production release requires bank historical replay.",
            ),
        ],
        non_claims=[
            "Not novelty by LLM usage alone.",
            "Not claiming autonomous STR filing.",
            "Not claiming production auto-clear from synthetic metrics alone.",
            "Not claiming a replacement for the bank's transaction-monitoring system.",
        ],
    )
    return packet.model_dump(by_alias=True, mode="json")


@app.get("/finals/qna-defense", response_model=FinalsQADefensePacket)
def get_finals_qna_defense():
    """Prepared judge Q&A packet: pressure questions mapped to live evidence."""
    packet = FinalsQADefensePacket(
        mode="judgeDefense",
        primary_position=(
            "VerdictAML is built to make AML triage defensible, not to replace compliance judgment. "
            "Every strong claim should be answered by opening the relevant contract, metric, or defense case."
        ),
        answers=[
            JudgeDefenseAnswer(
                objection="Problem relevance: what real AML operations pain does this solve?",
                short_answer=(
                    "The operational problem is not writing a nicer explanation for one alert; it is morning queue overload. "
                    "The system shows how many alerts were processed, how many left the inbox, how many still require "
                    "human judgment, and how much analyst time the shift-level workflow returns."
                ),
                evidence_endpoints=["/operations/impact", "/queue/briefing"],
                demo_action="Start in Governance with Operational Impact, then open the Queue Agent briefing and click the remaining needsReview lane.",
                trap_to_avoid="Do not lead with abstract AI capability before showing the workflow bottleneck.",
            ),
            JudgeDefenseAnswer(
                objection="Auto-clear safety: if you clear 40 percent automatically, how do you catch a false clear?",
                short_answer=(
                    "We do not present auto-clear as production-approved. It is threshold-gated, verifier-gated, "
                    "screening-gated, QA-sampled, and shadow-only until bank historical replay proves leakage."
                ),
                evidence_endpoints=["/governance/validation-dossier", "/alerts/HERO-002/defense-case"],
                demo_action="Open Governance, show auto-clear leakage, release gates, prohibited actions, then open the HERO-002 defense case controls.",
                trap_to_avoid="Do not say the 40 percent clear rate is already safe for production.",
            ),
            JudgeDefenseAnswer(
                objection="Metrics: recall 0.72, precision 0.75, accuracy 0.69 are modest. Why should we trust this?",
                short_answer=(
                    "The honest answer is that the numbers are modest and measured on a synthetic held-out slice. "
                    "The value is the validation machinery: baseline meaning, confusion matrix, leakage, and release gates are visible."
                ),
                evidence_endpoints=["/metrics", "/governance/validation-dossier"],
                demo_action="Open Metrics, explain the always-dismiss baseline, then show the validation dossier caveats and gates.",
                trap_to_avoid="Do not oversell the metric as bank-production performance.",
            ),
            JudgeDefenseAnswer(
                objection="Integration: how does this fit a real bank AML stack?",
                short_answer=(
                    "VerdictAML sits after the bank's existing monitoring engine and before analyst case handling. "
                    "The integration contract names required fields, optional enrichments, outputs, gates, and non-goals."
                ),
                evidence_endpoints=["/integration/contract", "/pilot/adoption-plan"],
                demo_action="Open the Bank Integration card, walk inbound systems, required fields, outbound artifacts, and shadow-first gates.",
                trap_to_avoid="Do not imply we replace SAS, Actimize, Mantas, or the source detector.",
            ),
            JudgeDefenseAnswer(
                objection="Production trust: what data, governance, and validation are needed before a bank can trust auto-clear?",
                short_answer=(
                    "Hans is right to ask this. The product answer is a production trust plan: connect to the "
                    "existing AML stack, use only approved alert/KYC/ledger/screening/disposition fields, govern "
                    "false positives through verifier, QA, leakage, and override controls, then require historical "
                    "replay and a shadow pilot before limited automation."
                ),
                evidence_endpoints=["/production/trust-plan", "/integration/contract", "/governance/validation-dossier", "/pilot/adoption-plan"],
                demo_action="Open Production Trust Plan and walk target systems, minimum data access, governance controls, validation gates, and non-claims.",
                trap_to_avoid="Do not say demo metrics authorize production auto-clear.",
            ),
            JudgeDefenseAnswer(
                objection="Technical architecture: what exactly runs end to end?",
                short_answer=(
                    "The architecture is explicit: bank monitoring feeds a typed API and store; triage, verifier, "
                    "screening, debate, and Queue Agent produce recommendations; deterministic controls gate "
                    "auto-clear, QA, STR export, audit, and readiness."
                ),
                evidence_endpoints=["/architecture/technical", "/integration/contract", "/readiness/summary"],
                demo_action="Open Technical Architecture and walk components, execution flow, data handling, AI execution, and reliability controls.",
                trap_to_avoid="Do not describe it as a prompt around a dataset; show the typed workflow and control plane.",
            ),
            JudgeDefenseAnswer(
                objection="Innovation: why is this not just another LLM triage wrapper?",
                short_answer=(
                    "The novelty is the practical AML control workflow around the model: overnight queue "
                    "triage, analyst-taught suppression, deterministic firewalls, measured leakage, "
                    "network revocation, independent verifier, human-gated goAML, and machine-readable "
                    "defense cases."
                ),
                evidence_endpoints=["/innovation/differentiation", "/queue/briefing", "/governance/validation-dossier", "/alerts/HERO-002/defense-case"],
                demo_action=(
                    "Open the shift briefing first, then Innovation Differentiation, the suppression "
                    "frontier, and the defense case as proof artifacts."
                ),
                trap_to_avoid="Do not call suppression a whitelist or claim novelty because the system uses an LLM.",
            ),
            JudgeDefenseAnswer(
                objection="Procurement: your go-to-market sounds too fast for banks.",
                short_answer=(
                    "We agree. The credible path is read-only replay, security/legal review, shadow pilot, "
                    "then limited production only after sign-off. The 5,000-alert/month, 360-hour saving "
                    "case is a validation target, not a production claim."
                ),
                evidence_endpoints=["/pilot/adoption-plan", "/integration/contract"],
                demo_action=(
                    "Open the Pilot Adoption Plan and show stakeholders, phases, pilot economics, "
                    "success criteria, procurement risks, and non-claims."
                ),
                trap_to_avoid="Do not promise immediate annual conversion after a short pilot.",
            ),
            JudgeDefenseAnswer(
                objection="Live reliability: Christopher found a referenced endpoint that 404ed. How do we know finals endpoints work?",
                short_answer=(
                    "The app now exposes a readiness summary that shape-checks the live contracts behind the pitch, "
                    "including metrics, governance, integration, pilot, innovation, Q&A, and evidence bundle."
                ),
                evidence_endpoints=["/readiness/summary", "/finals/evidence-bundle"],
                demo_action="Open Defense Artifacts and show every listed endpoint passing readiness before Q&A starts.",
                trap_to_avoid="Do not ask judges to trust README links without opening the readiness contract.",
            ),
        ],
        closing_line=(
            "The defensible claim is not that VerdictAML is perfect; it is that the system exposes the evidence, "
            "controls, limits, and validation gates needed before a bank could trust it."
        ),
    )
    return packet.model_dump(by_alias=True, mode="json")


@app.get("/finals/demo-script", response_model=FinalsDemoScript)
def get_finals_demo_script():
    """Timed finals demo path with evidence endpoints and fallback moves."""
    script = FinalsDemoScript(
        mode="finalsDemo",
        opening_line=(
            "The operational problem is AML queue overload: banks need to remove benign noise "
            "without hiding risk, losing auditability, or pretending synthetic metrics authorize production."
        ),
        total_minutes=7.0,
        steps=[
            FinalsDemoStep(
                title="Start with operational pain",
                timebox_minutes=1.0,
                objective="Show the queue overload problem and measurable shift-level impact.",
                route="#/governance",
                action="Open Operational Impact; say processed, auto-cleared, human-review, hours returned, and caveat.",
                evidence_endpoints=["/operations/impact", "/queue/briefing"],
                judge_takeaway="This is a concrete operations workflow, not a generic chatbot demo.",
                fallback="If the UI is slow, open /operations/impact directly and read the demoNarrative.",
            ),
            FinalsDemoStep(
                title="Show the architecture",
                timebox_minutes=1.0,
                objective="Prove the system is end-to-end: data, agents, controls, UI, audit, and filing seam.",
                route="#/governance",
                action="Open Technical Architecture and walk components plus execution flow.",
                evidence_endpoints=["/architecture/technical", "/integration/contract"],
                judge_takeaway="Architecture and data handling are explicit, typed, and demo-verifiable.",
                fallback="If the card is not visible, open /architecture/technical and walk components/flows from JSON.",
            ),
            FinalsDemoStep(
                title="Operate the Queue Agent",
                timebox_minutes=1.0,
                objective="Show automation that preserves human judgment.",
                route="#/queue",
                action="Use Queue Agent next moves; click needsReview, QA sample, and auto-cleared lanes.",
                evidence_endpoints=["/queue/briefing", "/governance/validation-dossier"],
                judge_takeaway="The agent removes noise, but contested and consequential cases stay human-gated.",
                fallback="If a lane filter misbehaves, show /queue/briefing and the blockedReasons list.",
            ),
            FinalsDemoStep(
                title="Open the hero defense case",
                timebox_minutes=1.25,
                objective="Show explainability, verifier challenge, evidence anchoring, and filing controls.",
                route="#/alerts/HERO-002",
                action="Open HERO-002, point to defense case, money flow, network, STR/goAML gate, and audit.",
                evidence_endpoints=["/alerts/HERO-002/defense-case", "/alerts/HERO-002/network"],
                judge_takeaway="Every decision is replayable through evidence and controls.",
                fallback="If the network panel is not visible, open the defense-case endpoint and focus on controls/audit.",
            ),
            FinalsDemoStep(
                title="Answer safety and validation",
                timebox_minutes=1.0,
                objective="Preempt false-clear and modest-metrics objections.",
                route="#/governance",
                action="Show Validation Dossier: leakage, release gates, prohibited actions, and shadow-only state.",
                evidence_endpoints=["/governance/validation-dossier", "/metrics"],
                judge_takeaway="The claim is controlled shadow automation, not production autonomy.",
                fallback="If metrics are challenged, say the numbers are modest and point to release gates.",
            ),
            FinalsDemoStep(
                title="Close with adoption and proof",
                timebox_minutes=1.75,
                objective="Show commercial realism and verify every referenced endpoint.",
                route="#/governance",
                action="Open Pilot Adoption Plan, Defense Artifacts, Readiness Summary, and Finals Q&A Defense.",
                evidence_endpoints=["/pilot/adoption-plan", "/readiness/summary", "/finals/evidence-bundle", "/finals/qna-defense"],
                judge_takeaway="Adoption is bank-realistic and every claim has a live evidence contract.",
                fallback="If time is short, open /readiness/summary and say every contract is passing.",
            ),
        ],
        fallback_moves=[
            "If live LLM/RAG fails, say the demo is designed to fall back to precomputed triage and curated checks.",
            "If a panel is slow, open the matching endpoint directly and show readiness still passes.",
            "If challenged on metrics, acknowledge modest synthetic performance and pivot to validation gates.",
            "If challenged on production, repeat: shadow-only until bank historical replay and signoff.",
        ],
        closing_line=(
            "VerdictAML is built to win trust by reducing AML queue work while exposing evidence, controls, "
            "limits, and the bank validation path."
        ),
        non_claims=[
            "Do not claim production auto-clear approval from synthetic metrics.",
            "Do not claim autonomous STR filing.",
            "Do not claim VerdictAML replaces SAS, Actimize, Mantas, or the bank source detector.",
            "Do not claim immediate bank procurement conversion.",
        ],
    )
    return script.model_dump(by_alias=True, mode="json")


def _readiness_summary(include_bundle: bool) -> ReadinessSummary:
    specs = [
        ("/health", health, lambda d: [] if d.get("status") == "ok" and d.get("alertsLoaded", 0) > 0 else ["health not ready"]),
        ("/metrics", get_metrics, validate_metrics_payload),
        ("/governance", get_governance, validate_governance_payload),
        ("/security/access-control", get_access_control_posture, validate_access_control_payload),
        ("/governance/change-requests", get_governance_change_requests, validate_governance_change_payload),
        ("/qa/outcomes", get_qa_outcomes, validate_qa_outcomes_payload),
        ("/queue/briefing", get_briefing, lambda d: [f"missing briefing keys: {sorted(missing_keys(d, BRIEFING_KEYS))}"] if missing_keys(d, BRIEFING_KEYS) else []),
        ("/alerts/HERO-002/defense-case", lambda: get_alert_defense_case("HERO-002"), validate_defense_case_payload),
        ("/alerts/HERO-002/case-handoff", lambda: get_case_handoff("HERO-002"), validate_case_handoff_payload),
        ("/alerts/HERO-002/decision-trace", lambda: get_decision_trace("HERO-002"), validate_decision_trace_payload),
        ("/alerts/HERO-002/copilot-runs/precomputed-current/ledger", lambda: get_copilot_run_ledger("HERO-002", "precomputed-current"), validate_copilot_ledger_payload),
        ("/operations/impact", get_operational_impact, validate_operational_impact_payload),
        ("/architecture/technical", get_technical_architecture, validate_technical_architecture_payload),
        ("/integration/contract", get_integration_contract, validate_integration_contract_payload),
        ("/production/trust-plan", get_production_trust_plan, validate_production_trust_plan_payload),
        ("/pilot/adoption-plan", get_pilot_adoption_plan, validate_pilot_adoption_plan_payload),
        ("/innovation/differentiation", get_innovation_differentiation, validate_innovation_differentiation_payload),
        ("/finals/demo-script", get_finals_demo_script, validate_finals_demo_script_payload),
        ("/finals/qna-defense", get_finals_qna_defense, validate_qna_defense_payload),
        ("/governance/validation-dossier", get_validation_dossier, validate_validation_dossier_payload),
    ]
    if include_bundle:
        specs.append(("/finals/evidence-bundle", get_finals_evidence_bundle, validate_finals_evidence_bundle_payload))

    checks: list[ReadinessCheck] = []
    for endpoint, loader, validator in specs:
        try:
            payload = loader()
            errors = validator(payload)
            checks.append(ReadinessCheck(
                name=f"contract {endpoint}",
                endpoint=endpoint,
                ok=not errors,
                detail="ok" if not errors else "; ".join(errors),
            ))
        except Exception as exc:  # noqa: BLE001 - readiness must report failures, not hide them.
            checks.append(ReadinessCheck(
                name=f"contract {endpoint}",
                endpoint=endpoint,
                ok=False,
                detail=str(exc),
            ))

    return ReadinessSummary(
        status="pass" if all(c.ok for c in checks) else "fail",
        checked_at=now_local(),
        checks=checks,
    )


@app.get("/readiness/summary", response_model=ReadinessSummary)
def get_readiness_summary():
    """In-process finals readiness summary for deployed demos.

    This does not call back over HTTP. It validates the same machine-readable contracts the
    Governance tab lists, so judges can see whether the deployed service is serving the artifacts
    behind the pitch claims.
    """
    summary = _readiness_summary(include_bundle=True)
    return summary.model_dump(by_alias=True, mode="json")


@app.get("/finals/evidence-bundle", response_model=FinalsEvidenceBundle)
def get_finals_evidence_bundle():
    """Single machine-readable evidence bundle for finals judging.

    This endpoint packages the already-typed contracts behind the demo claims into one response:
    measured metrics, governance, validation dossier, bank integration contract, readiness state,
    and one representative per-alert defense case. It is intentionally read-only and assembled from
    existing endpoints so it cannot drift from what the app shows.
    """
    bundle = FinalsEvidenceBundle(
        generated_at=now_local(),
        claims=[
            EvidenceClaim(
                claim="Headline metrics are measured on the held-out SAML-D slice, not invented.",
                backed_by=["/metrics", "/governance/validation-dossier"],
                caveat="Synthetic data; production requires bank historical replay.",
            ),
            EvidenceClaim(
                claim="Auto-clear remains shadow-gated until leakage, QA, and compliance gates pass.",
                backed_by=["/governance/validation-dossier", "/governance"],
            ),
            EvidenceClaim(
                claim="Operational impact is shown as live shift workload reduction, not slide-only ROI.",
                backed_by=["/operations/impact", "/queue/briefing"],
                caveat="Shift-level hours returned are demo impact, not a production ROI claim.",
            ),
            EvidenceClaim(
                claim="Technical architecture is explicit: components, flows, data handling, AI execution, and controls.",
                backed_by=["/architecture/technical", "/integration/contract"],
                caveat="Production deployment still requires bank data residency, access control, and model-risk signoff.",
            ),
            EvidenceClaim(
                claim="Protected write actions are actor-attributed and role-gated before decisions, QA outcomes, STR filing, governance changes, or reset operations can mutate state.",
                backed_by=["/security/access-control", "/audit", "/readiness/summary"],
                caveat="Demo actor headers are the authorization seam; production binds the same roles to bank SSO/OIDC.",
            ),
            EvidenceClaim(
                claim="Bank integration assumptions are explicit and machine-readable.",
                backed_by=["/integration/contract"],
            ),
            EvidenceClaim(
                claim="Per-alert case-management handoff is explicit: status update, case note, artifacts, write-back gate, and audit events.",
                backed_by=["/alerts/HERO-002/case-handoff", "/integration/contract"],
                caveat="Demo endpoint is read-only; live bank write-back requires integration sign-off.",
            ),
            EvidenceClaim(
                claim="Per-alert decisions are replayable through observable evidence, model outputs, deterministic gates, and audit state.",
                backed_by=["/alerts/HERO-002/decision-trace", "/alerts/HERO-002/defense-case"],
                caveat="Decision trace is not DeepSeek chain-of-thought and does not rerun the LLM.",
            ),
            EvidenceClaim(
                claim="Copilot transparency includes the prompt/response envelope, schema validation path, deterministic gates, and redaction boundaries.",
                backed_by=["/alerts/HERO-002/copilot-runs/precomputed-current/ledger", "/alerts/HERO-002/decision-trace"],
                caveat="Precomputed fixture ledger is reconstructed; live runs capture actual redacted LLM messages and raw responses.",
            ),
            EvidenceClaim(
                claim="Operating-point changes are governed: thresholds, prompt templates, model/provider settings, and suppression rules cannot move silently.",
                backed_by=["/governance/change-requests", "/governance/validation-dossier", "/readiness/summary"],
                caveat="Demo API records proposals; production application still requires bank approval and deployment workflow.",
            ),
            EvidenceClaim(
                claim="QA-sampled auto-clears can be reviewed as confirmed clears or missed suspicion, feeding governance without silent retraining.",
                backed_by=["/qa/outcomes", "/governance", "/operations/impact"],
            ),
            EvidenceClaim(
                claim="Production trust is gated by bank-system integration, minimum approved data access, false-positive governance, and replay/shadow validation.",
                backed_by=["/production/trust-plan", "/integration/contract", "/governance/validation-dossier", "/pilot/adoption-plan"],
                caveat="This is the plan for earning trust; it is not a claim that a bank has already approved production auto-clear.",
            ),
            EvidenceClaim(
                claim="Pilot economics are stated as a conservative validation target, alongside procurement and security gates.",
                backed_by=["/pilot/adoption-plan"],
                caveat="Hours saved are not a production claim; the bank must replace assumptions with its own volumes, QA policy, and leakage tolerance.",
            ),
            EvidenceClaim(
                claim="Innovation is evidenced by built AML controls, not by LLM usage alone.",
                backed_by=["/innovation/differentiation"],
                caveat="Differentiators still need bank-data validation before production claims.",
            ),
            EvidenceClaim(
                claim="Finals Q&A objections are answerable from live evidence contracts.",
                backed_by=["/finals/qna-defense"],
            ),
            EvidenceClaim(
                claim="The presentation path is timed, evidence-backed, and has fallback moves for live-demo risk.",
                backed_by=["/finals/demo-script", "/readiness/summary"],
            ),
            EvidenceClaim(
                claim="Per-alert answers are defensible through evidence, controls, and audit.",
                backed_by=["/alerts/HERO-002/defense-case"],
            ),
            EvidenceClaim(
                claim="The live demo contracts are reachable and shape-validated.",
                backed_by=["/readiness/summary"],
            ),
        ],
        readiness=_readiness_summary(include_bundle=False),
        metrics=Metrics.model_validate(get_metrics()),
        governance=Governance.model_validate(get_governance()),
        access_control=AccessControlPosture.model_validate(get_access_control_posture()),
        governance_change_control=GovernanceChangeRequestList.model_validate(get_governance_change_requests()),
        qa_outcome_summary=QAOutcomeSummary.model_validate(get_qa_outcomes()),
        operational_impact=OperationalImpact.model_validate(get_operational_impact()),
        validation_dossier=ValidationDossier.model_validate(get_validation_dossier()),
        production_trust_plan=ProductionTrustPlan.model_validate(get_production_trust_plan()),
        technical_architecture=TechnicalArchitecture.model_validate(get_technical_architecture()),
        integration_contract=BankIntegrationContract.model_validate(get_integration_contract()),
        pilot_adoption_plan=PilotAdoptionPlan.model_validate(get_pilot_adoption_plan()),
        innovation_differentiation=InnovationDifferentiation.model_validate(get_innovation_differentiation()),
        demo_script=FinalsDemoScript.model_validate(get_finals_demo_script()),
        qna_defense=FinalsQADefensePacket.model_validate(get_finals_qna_defense()),
        hero_defense_case=DefenseCase.model_validate(get_alert_defense_case("HERO-002")),
        hero_case_handoff=CaseHandoff.model_validate(get_case_handoff("HERO-002")),
        hero_decision_trace=DecisionTrace.model_validate(get_decision_trace("HERO-002")),
        hero_copilot_ledger=CopilotRunLedger.model_validate(get_copilot_run_ledger("HERO-002", "precomputed-current")),
    )
    return bundle.model_dump(by_alias=True, mode="json")


@app.get("/governance/validation-dossier", response_model=ValidationDossier)
def get_validation_dossier():
    """Compliance-facing validation dossier for the current operating point.

    The dossier derives from the same locked metrics artifact as /metrics and /governance, so the
    numbers cannot diverge across surfaces.
    """
    if not _METRICS.exists():
        raise ApiError(404, "METRICS_NOT_READY", "metrics.json has not been generated yet (Phase 8).")
    metrics = json.loads(_METRICS.read_text(encoding="utf-8"))
    leak = (
        auto_clear_leakage(metrics)
        if {"autoClearedShare", "autoClearPrecision", "confusionMatrix"} <= metrics.keys()
        else {}
    )
    dossier = ValidationDossier(
        validated_at=metrics.get("validatedAt"),
        model=metrics.get("model"),
        dataset="SAML-D held-out report-enriched slice",
        n=metrics["totalAlerts"],
        accuracy_vs_labels=metrics["accuracyVsLabels"],
        baseline_accuracy=metrics["baselineAccuracy"],
        baseline_explanation=(
            "Always-dismiss baseline on this held-out slice: it equals the benign share and catches "
            "zero reportable cases."
        ),
        recall=metrics["recall"],
        precision=metrics["precision"],
        specificity=metrics["specificity"],
        confusion_matrix=metrics["confusionMatrix"],
        auto_cleared_share=metrics.get("autoClearedShare"),
        auto_clear_precision=metrics.get("autoClearPrecision"),
        auto_cleared_reports=leak.get("autoClearedReports"),
        total_reports=leak.get("totalReports"),
        auto_clear_leakage_rate=leak.get("autoClearLeakageRate"),
        thresholds=GovernanceThresholds(
            review=config.REVIEW_THRESHOLD,
            auto_clear=config.AUTO_CLEAR_THRESHOLD,
            qa_sample=config.QA_SAMPLE_RATE,
            borderline_margin=config.BORDERLINE_MARGIN,
        ),
        measured_typologies=metrics.get("measuredTypologies") or [],
        roadmap_typologies=metrics.get("roadmapTypologies") or [],
        production_state="shadowOnly",
        release_gates=[
            "Historical replay against bank alerts with known analyst dispositions.",
            "Known-outcome comparison for STR/no-STR outcomes before enabling any auto-clear.",
            "Compliance/model-risk approval of review, auto-clear, borderline, and QA thresholds.",
            "Risk-weighted QA sampling of auto-cleared alerts remains enabled.",
            "Override monitoring feeds deliberate threshold/card review; no silent model training.",
        ],
        prohibited_actions=[
            "No auto-escalation.",
            "No auto-filing.",
            "No auto-clear on verifier flags, debate, screening hits, or below-threshold dismissals.",
        ],
    )
    return dossier.model_dump(by_alias=True, mode="json")


@app.get("/evaluation")
def get_evaluation():
    """The held-out evaluation SET the accuracy is measured over (250 SAML-D alerts + ground-truth
    labels, ADR-0012) — so the number isn't hidden behind a percentage. Token-free artifact built
    by data/build_evaluation.py; 404s in contract shape until it exists."""
    evaluation = _DATA / "evaluation.json"
    if not evaluation.exists():
        raise ApiError(404, "EVALUATION_NOT_READY",
                       "evaluation.json has not been generated yet (run data/build_evaluation.py).")
    return json.loads(evaluation.read_text(encoding="utf-8"))


@app.post("/reset")
def reset(actor: Actor = Depends(require_actor("admin"))):
    """Reset the persisted store: re-seed the alert catalog, drop session decisions + audit
    events, and restore the Queue Agent's autonomous seed. Not in the core contract — a
    demo convenience to clear edits between rehearsals."""
    store.reset()
    return {
        "status": "success",
        "message": "State reset from the seeded catalog.",
        "actorId": actor.actor_id,
        "actorRole": actor.actor_role,
    }
