import json
from pathlib import Path

import readiness


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def valid_metrics():
    return {
        "totalAlerts": 4,
        "accuracyVsLabels": 0.75,
        "baselineAccuracy": 0.5,
        "recall": 0.5,
        "precision": 1.0,
        "specificity": 1.0,
        "confusionMatrix": {"tp": 1, "fp": 0, "fn": 1, "tn": 2},
        "autoClearedShare": 0.25,
        "autoClearPrecision": 1.0,
        "validatedAt": "2026-07-06T10:00:00+08:00",
        "model": "deepseek-v4-pro",
    }


def test_auto_clear_leakage_derives_from_metrics_aggregates():
    leak = readiness.auto_clear_leakage(valid_metrics())
    assert leak == {
        "autoClearedReports": 0,
        "totalReports": 2,
        "autoClearLeakageRate": 0.0,
    }


def test_validate_metrics_requires_finals_fields():
    m = valid_metrics()
    del m["validatedAt"]
    errors = readiness.validate_metrics_payload(m)
    assert any("validatedAt" in e for e in errors)


def test_validate_governance_requires_leakage_and_thresholds():
    errors = readiness.validate_governance_payload({
        "model": {},
        "thresholds": {"review": 0.6, "autoClear": 0.85},
        "validation": {"validatedAt": "x", "model": "m", "n": 250, "recall": 0.7},
        "override": {},
        "securityPosture": [],
    })
    assert "governance.validation.autoClearLeakageRate is missing" in errors
    assert "governance.thresholds.qaSample is missing" in errors


def test_validate_defense_case_requires_controls_and_filing_gates():
    errors = readiness.validate_defense_case_payload({
        "alertId": "HERO-002",
        "decisionContext": {},
        "evidence": {
            "matchedTypology": {},
            "indicatorCoverage": {},
            "citedTransactionIds": [],
            "strAnchoring": {},
        },
        "controls": {
            "autoClearPolicy": {"reasons": ["AI recommendation is escalate."]},
            "verifier": {},
            "strFiling": {
                "requiresEscalateSignoff": True,
                "xsdValidatedOnExport": True,
            },
        },
        "audit": [],
    })

    assert "defense-case.controls.strFiling.blocksUnanchoredGrounds must be true" in errors


def test_validate_integration_contract_requires_shadow_mode_and_data_fields():
    errors = readiness.validate_integration_contract_payload({
        "mode": "shadowFirst",
        "inboundSystems": ["Actimize"],
        "workflow": [],
        "minimumRequiredFields": [
            {"name": "alertId", "required": True},
            {"name": "riskScore", "required": True},
        ],
        "optionalEnrichments": [],
        "outboundArtifacts": ["goAML XML"],
        "productionGates": ["Threshold approval"],
        "nonGoals": [],
    })

    assert "integration-contract missing required field running balance" in errors
    assert "integration-contract must expose defense-case output" in errors
    assert "integration-contract must require historical replay" in errors


def test_validate_production_trust_plan_requires_bank_systems_data_governance_and_validation():
    errors = readiness.validate_production_trust_plan_payload({
        "mode": "productionTrustPlan",
        "position": "Trust us.",
        "targetSystems": ["Generic API"],
        "minimumDataAccess": ["Alert id"],
        "governanceControls": ["Some manual review"],
        "validationGates": ["Quick pilot"],
        "items": [
            {
                "area": "integration",
                "requirement": "Connect systems.",
                "implementation": "API.",
                "evidenceEndpoints": ["/integration/contract"],
                "productionGate": "Approval.",
            }
        ],
        "judgeResponse": "The demo is safe.",
        "nonClaims": ["No claim."],
    })

    assert "production-trust-plan target systems must mention actimize" in errors
    assert "production-trust-plan target systems must mention mantas" in errors
    assert "production-trust-plan minimum data must mention transaction id" in errors
    assert "production-trust-plan minimum data must mention running balance" in errors
    assert "production-trust-plan controls must mention verifier" in errors
    assert "production-trust-plan controls must mention leakage" in errors
    assert "production-trust-plan validation gates must mention historical replay" in errors
    assert "production-trust-plan validation gates must mention shadow pilot" in errors
    assert "production-trust-plan missing falsePositiveGovernance item" in errors
    assert "production-trust-plan judge response must reject demo trust and require shadow pilot" in errors
    assert "production-trust-plan non-claims must mention synthetic" in errors


def test_validate_validation_dossier_requires_shadow_state_and_release_gates():
    errors = readiness.validate_validation_dossier_payload({
        "validatedAt": "2026-07-06T10:00:00+08:00",
        "model": "deepseek-v4-pro",
        "dataset": "SAML-D",
        "n": 250,
        "accuracyVsLabels": 0.69,
        "baselineAccuracy": 0.4,
        "baselineExplanation": "Always dismiss baseline.",
        "recall": 0.72,
        "precision": 0.75,
        "specificity": 0.65,
        "confusionMatrix": {"tp": 1, "fp": 1, "fn": 1, "tn": 1},
        "autoClearLeakageRate": 0.12,
        "thresholds": {"review": 0.6, "autoClear": 0.85, "qaSample": 0.1},
        "productionState": "pilotLive",
        "releaseGates": ["Threshold approval"],
        "prohibitedActions": ["No auto-escalation."],
    })

    assert "validation-dossier.productionState must be shadowOnly" in errors
    assert "validation-dossier baseline explanation must state zero reportable cases" in errors
    assert "validation-dossier.thresholds.borderlineMargin is missing" in errors
    assert "validation-dossier must require historical replay" in errors
    assert "validation-dossier must prohibit auto-filing" in errors


def test_validate_operational_impact_requires_controls_and_caveat():
    errors = readiness.validate_operational_impact_payload({
        "mode": "shiftImpact",
        "processedAlerts": 10,
        "autoClearedAlerts": 4,
        "humanReviewAlerts": 5,
        "qaSampleAlerts": 1,
        "escalationsHeldForSignoff": 2,
        "verifierFlagged": 1,
        "baselineReviewMinutes": 120,
        "assistedReviewMinutes": 70,
        "minutesReturned": 50,
        "analystHoursReturned": 0.83,
        "queueReductionRate": 0.4,
        "reviewFocusMultiplier": 2,
        "assumptions": ["demo"],
        "controlChecks": ["Escalations remain human reviewed."],
        "demoNarrative": "Queue overload reduced.",
        "caveat": "Trust this ROI.",
    })

    assert "operational-impact processed alerts must equal auto-cleared plus human-review alerts" in errors
    assert "operational-impact controls must mention qa" in errors
    assert "operational-impact controls must mention historical replay" in errors
    assert "operational-impact caveat must reject production ROI claim" in errors


def test_validate_technical_architecture_requires_components_flows_and_controls():
    errors = readiness.validate_technical_architecture_payload({
        "mode": "technicalArchitecture",
        "thesis": "Prompt wrapper.",
        "components": [
            {
                "id": "bank-monitoring",
                "name": "Bank",
                "layer": "bank",
                "responsibility": "Feeds alerts.",
                "proofEndpoints": [],
            }
        ],
        "flows": [{"source": "bank-monitoring", "target": "api-store", "payload": "alerts"}],
        "dataHandling": ["Load demo fixtures."],
        "aiExecution": ["Prompt model."],
        "reliabilityControls": ["Some tests."],
        "demoPath": ["Show a slide."],
        "caveat": "Demo only.",
    })

    assert "technical-architecture must list at least six components" in errors
    assert "technical-architecture missing component api-store" in errors
    assert "technical-architecture must list at least five flows" in errors
    assert "technical-architecture flows must include source, target, payload, and control" in errors
    assert "technical-architecture controls must mention readiness" in errors
    assert "technical-architecture data handling must mention read-only pilot/replay" in errors
    assert "technical-architecture demo path must mention architecture and evidence bundle" in errors


def test_validate_finals_demo_script_requires_beats_fallbacks_and_non_claims():
    errors = readiness.validate_finals_demo_script_payload({
        "mode": "finalsDemo",
        "openingLine": "Demo starts.",
        "totalMinutes": 12,
        "steps": [
            {
                "title": "Talk",
                "timeboxMinutes": 1,
                "objective": "Explain AI.",
                "route": "#/governance",
                "action": "Talk.",
                "evidenceEndpoints": [],
                "judgeTakeaway": "Trust us.",
                "fallback": "",
            }
        ],
        "fallbackMoves": ["Refresh the page."],
        "closingLine": "Done.",
        "nonClaims": ["No replacement."],
    })

    assert "finals-demo-script totalMinutes must fit an 8-minute finals demo" in errors
    assert "finals-demo-script must contain at least five steps" in errors
    assert "finals-demo-script missing operational demo beat" in errors
    assert "finals-demo-script evidence endpoints must include /operations/impact" in errors
    assert "finals-demo-script every step must include a fallback" in errors
    assert "finals-demo-script fallback moves must cover precomputed path and readiness" in errors
    assert "finals-demo-script non-claims must cover production auto-clear and autonomous STR" in errors


def test_validate_finals_evidence_bundle_requires_nested_contracts_and_claim_sources():
    errors = readiness.validate_finals_evidence_bundle_payload({
        "generatedAt": "2026-07-06T10:00:00+08:00",
        "claims": [{"claim": "x", "backedBy": ["/metrics"]}],
        "readiness": {"status": "fail", "checkedAt": "2026-07-06T10:00:00+08:00", "checks": []},
        "metrics": valid_metrics(),
        "governance": {
            "model": {},
            "thresholds": {"review": 0.6, "autoClear": 0.85, "qaSample": 0.2, "borderlineMargin": 0.1},
            "validation": {
                "validatedAt": "2026-07-06T10:00:00+08:00",
                "model": "deepseek-v4-pro",
                "n": 4,
                "recall": 0.5,
                "autoClearLeakageRate": 0.0,
            },
            "override": {},
            "securityPosture": [],
        },
        "validationDossier": {
            "validatedAt": "2026-07-06T10:00:00+08:00",
            "model": "deepseek-v4-pro",
            "dataset": "SAML-D",
            "n": 4,
            "accuracyVsLabels": 0.75,
            "baselineAccuracy": 0.5,
            "baselineExplanation": "Always-dismiss baseline catches zero reportable cases.",
            "recall": 0.5,
            "precision": 1.0,
            "specificity": 1.0,
            "confusionMatrix": {"tp": 1, "fp": 0, "fn": 1, "tn": 2},
            "autoClearLeakageRate": 0.0,
            "thresholds": {"review": 0.6, "autoClear": 0.85, "qaSample": 0.2, "borderlineMargin": 0.1},
            "productionState": "shadowOnly",
            "releaseGates": ["Historical replay"],
            "prohibitedActions": ["No auto-filing."],
        },
        "integrationContract": {
            "mode": "shadowFirst",
            "inboundSystems": [],
            "workflow": [],
            "minimumRequiredFields": [
                {"name": "alertId", "required": True},
                {"name": "riskScore", "required": True},
                {"name": "running balance", "required": True},
            ],
            "optionalEnrichments": [],
            "outboundArtifacts": ["defense-case packet"],
            "productionGates": ["historical replay"],
            "nonGoals": [],
        },
        "pilotAdoptionPlan": {
            "mode": "bankPilot",
            "buyerStakeholders": ["Compliance", "Model risk", "Information security", "Procurement"],
            "pilotEconomics": {
                "monthlyAlerts": 5000,
                "currentReviewMinutesPerAlert": 12,
                "assistedReviewMinutesPerAlert": 7,
                "qaSampleMinutesPerAlert": 5,
                "estimatedMonthlyHoursSaved": 360,
                "valueHypothesis": "Conservative handling reduction.",
                "caveat": "Pilot economics are not a production claim.",
            },
            "phases": [
                {"name": "historical replay", "objective": "", "exitCriteria": [], "evidenceProduced": []},
                {"name": "security review", "objective": "", "exitCriteria": [], "evidenceProduced": []},
                {"name": "shadow pilot", "objective": "", "exitCriteria": [], "evidenceProduced": []},
                {"name": "limited production", "objective": "", "exitCriteria": [], "evidenceProduced": []},
            ],
            "successCriteria": ["leakage within tolerance"],
            "validationEvidence": [],
            "procurementRisks": ["Procurement can take months."],
            "nonClaims": ["No claim of immediate annual contract."],
        },
        "innovationDifferentiation": {
            "mode": "evidenceBackedDifferentiation",
            "thesis": "Controls differentiate VerdictAML from generic LLM triage.",
            "capabilities": [
                {
                    "name": "Adversarial verifier",
                    "genericAlternative": "single pass",
                    "verdictamlImplementation": "verifier",
                    "proofEndpoints": ["/alerts/HERO-002/defense-case"],
                    "defenseValue": "challenge",
                    "limitation": "human review",
                },
                {
                    "name": "goAML export",
                    "genericAlternative": "prose",
                    "verdictamlImplementation": "schema",
                    "proofEndpoints": ["/integration/contract"],
                    "defenseValue": "filing control",
                    "limitation": "bank rails",
                },
                {
                    "name": "Mule network",
                    "genericAlternative": "isolated alert",
                    "verdictamlImplementation": "network recall",
                    "proofEndpoints": ["/alerts/HERO-002/network"],
                    "defenseValue": "hidden mule",
                    "limitation": "bank graph validation",
                },
                {
                    "name": "Defense case",
                    "genericAlternative": "UI copy",
                    "verdictamlImplementation": "typed packet",
                    "proofEndpoints": ["/finals/evidence-bundle"],
                    "defenseValue": "replay",
                    "limitation": "provenance not approval",
                },
                {
                    "name": "Shadow governance",
                    "genericAlternative": "automation claim",
                    "verdictamlImplementation": "gates",
                    "proofEndpoints": ["/governance/validation-dossier", "/pilot/adoption-plan"],
                    "defenseValue": "measurable release",
                    "limitation": "bank replay required",
                },
            ],
            "nonClaims": ["Not novelty by LLM usage alone."],
        },
        "qnaDefense": {
            "mode": "judgeDefense",
            "primaryPosition": "Defensible AML triage.",
            "answers": [
                {
                    "objection": "auto-clear safety",
                    "shortAnswer": "gated",
                    "evidenceEndpoints": ["/governance/validation-dossier"],
                    "demoAction": "open dossier",
                    "trapToAvoid": "Do not claim production safety.",
                },
                {
                    "objection": "metrics modest",
                    "shortAnswer": "honest validation",
                    "evidenceEndpoints": ["/metrics"],
                    "demoAction": "open metrics",
                    "trapToAvoid": "Do not oversell.",
                },
                {
                    "objection": "integration",
                    "shortAnswer": "contract",
                    "evidenceEndpoints": ["/integration/contract"],
                    "demoAction": "open contract",
                    "trapToAvoid": "Do not claim replacement.",
                },
                {
                    "objection": "innovation",
                    "shortAnswer": "controls",
                    "evidenceEndpoints": ["/innovation/differentiation"],
                    "demoAction": "open differentiation",
                    "trapToAvoid": "Do not claim LLM novelty.",
                },
                {
                    "objection": "procurement",
                    "shortAnswer": "pilot economics are not a production claim",
                    "evidenceEndpoints": ["/pilot/adoption-plan"],
                    "demoAction": "open pilot economics",
                    "trapToAvoid": "Do not promise instant contract.",
                },
                {
                    "objection": "live reliability",
                    "shortAnswer": "readiness",
                    "evidenceEndpoints": ["/readiness/summary"],
                    "demoAction": "open readiness",
                    "trapToAvoid": "Do not rely on README.",
                },
            ],
            "closingLine": "Evidence, controls, limits.",
        },
        "heroDefenseCase": {
            "alertId": "HERO-002",
            "decisionContext": {},
            "evidence": {
                "matchedTypology": {},
                "indicatorCoverage": {},
                "citedTransactionIds": [],
                "strAnchoring": {},
            },
            "controls": {
                "autoClearPolicy": {"reasons": ["AI recommendation is escalate."]},
                "verifier": {},
                "strFiling": {
                    "requiresEscalateSignoff": True,
                    "blocksUnanchoredGrounds": True,
                    "xsdValidatedOnExport": True,
                },
            },
            "audit": [],
        },
    })

    assert "bundle.readiness.status must be pass" in errors
    assert "bundle claims must cite /governance/validation-dossier" in errors
    assert "bundle claims must cite /readiness/summary" in errors
    assert "bundle claims must cite /innovation/differentiation" in errors
    assert "bundle claims must cite /finals/qna-defense" in errors
    assert "bundle claims must frame pilot economics as not a production claim" in errors


def test_validate_pilot_adoption_plan_requires_procurement_realism():
    errors = readiness.validate_pilot_adoption_plan_payload({
        "mode": "bankPilot",
        "buyerStakeholders": ["AML operations"],
        "pilotEconomics": {
            "monthlyAlerts": 5000,
            "estimatedMonthlyHoursSaved": 0,
            "caveat": "Trust us.",
        },
        "phases": [{"name": "quick pilot"}],
        "successCriteria": ["review volume reduction"],
        "validationEvidence": [],
        "procurementRisks": ["Legal review required."],
        "nonClaims": ["No auto-filing."],
    })

    assert "pilot-adoption-plan must name Model risk stakeholder" in errors
    assert "pilot-adoption-plan missing historical replay phase" in errors
    assert "pilot-adoption-plan.pilotEconomics missing currentReviewMinutesPerAlert" in errors
    assert "pilot-adoption-plan.pilotEconomics must show positive hours saved" in errors
    assert "pilot-adoption-plan.pilotEconomics caveat must reject production claim" in errors
    assert "pilot-adoption-plan success criteria must include leakage" in errors
    assert "pilot-adoption-plan must state procurement can take months" in errors
    assert "pilot-adoption-plan must reject immediate annual contract claim" in errors


def test_validate_innovation_differentiation_requires_proof_and_non_claims():
    errors = readiness.validate_innovation_differentiation_payload({
        "mode": "evidenceBackedDifferentiation",
        "thesis": "We use LLMs.",
        "capabilities": [
            {
                "name": "LLM triage",
                "genericAlternative": "manual review",
                "verdictamlImplementation": "prompt",
                "proofEndpoints": [],
                "defenseValue": "faster",
                "limitation": "unknown",
            }
        ],
        "nonClaims": ["No auto-filing."],
    })

    assert "innovation-differentiation must list at least five built capabilities" in errors
    assert "innovation-differentiation missing verifier capability" in errors
    assert "innovation-differentiation missing goaml capability" in errors
    assert "innovation-differentiation proof endpoints must include /alerts/HERO-002/defense-case" in errors
    assert "innovation-differentiation must reject LLM-usage-only novelty" in errors


def test_validate_qna_defense_requires_objection_coverage_and_evidence():
    errors = readiness.validate_qna_defense_payload({
        "mode": "judgeDefense",
        "primaryPosition": "We can answer questions.",
        "answers": [
            {
                "objection": "auto-clear",
                "shortAnswer": "safe",
                "evidenceEndpoints": [],
                "demoAction": "talk",
                "trapToAvoid": "Avoid mistakes.",
            }
        ],
        "closingLine": "Trust us.",
    })

    assert "qna-defense must cover at least six likely judge objections" in errors
    assert "qna-defense missing metrics objection" in errors
    assert "qna-defense missing innovation objection" in errors
    assert "qna-defense evidence endpoints must include /metrics" in errors
    assert "qna-defense evidence endpoints must include /readiness/summary" in errors
    assert "qna-defense must answer commercial viability with pilot economics caveat" in errors
    assert "qna-defense traps must include explicit do-not-claim guidance" in errors


def test_local_artifacts_catches_fixture_drift(tmp_path):
    data = tmp_path / "backend" / "data"
    fixtures = tmp_path / "frontend" / "src" / "fixtures"

    write_json(data / "metrics.json", valid_metrics())
    write_json(fixtures / "metrics.json", {**valid_metrics(), "recall": 0.1})
    write_json(data / "results.json", [{"alertId": "A"}])
    write_json(fixtures / "alerts.json", [{"alertId": "A"}])
    write_json(data / "typologies" / "typologies.json", [{"code": "PT-01"}])
    write_json(fixtures / "typologies.json", [{"code": "PT-01"}])
    write_json(data / "evaluation.json", {"n": 1})
    write_json(fixtures / "evaluation.json", {"n": 1})

    checks = readiness.check_local_artifacts(tmp_path)
    drift = next(c for c in checks if c.name == "fixture sync metrics.json")
    assert drift.ok is False
    assert "drifted" in drift.detail
