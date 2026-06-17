# NexHack 2026 Track 2 Architecture

## Core Goal

Build an AI copilot for AML analysts that helps them review suspicious transaction alerts faster, explain the reasoning, self-check the decision, and draft an STR with human approval.

## End-to-End Flow

1. Analyst opens a flagged alert from the alert queue.
2. Backend retrieves the alert details and supporting transaction context.
3. Triage agent recommends `Escalate` or `Dismiss`.
4. Explanation layer maps the decision to AML typologies and highlights supporting evidence.
5. Verifier agent reviews the first decision and either agrees or forces human review.
6. STR drafting module generates a first draft when the alert should be escalated.
7. Analyst edits, approves, or overrides the result.
8. System stores the decision, reasoning, verifier result, and final report state.

## High-Level Architecture

```text
+---------------------------+
| Analyst Console           |
| React + Vite + Tailwind   |
+------------+--------------+
             |
             v
+---------------------------+
| Backend API               |
| FastAPI                   |
+------------+--------------+
             |
             v
+---------------------------+
| Orchestration Layer       |
| Alert review workflow     |
+-----+----------+----------+
      |          |          
      v          v
+-----------+  +----------------+
| Triage    |  | Verifier Agent |
| Agent     |  | Second-pass QA |
+-----------+  +----------------+
      |
      v
+---------------------------+
| Knowledge / Retrieval     |
| FATF + BNM typologies     |
+---------------------------+
      |
      v
+---------------------------+
| STR Draft Generator       |
| Draft report for analyst  |
+---------------------------+
      |
      v
+---------------------------+
| Storage                   |
| Alerts, outputs, metrics  |
+---------------------------+
```

## Main Components

### 1. Analyst Console

Responsibilities:
- Show alert queue
- Show alert detail view
- Display AI decision and explanation
- Display verifier result
- Let analyst review and edit STR draft
- Let analyst approve or override the AI output

Suggested pages:
- Alert Queue
- Alert Detail
- STR Review
- Metrics / Demo Summary

### 2. Backend API

Responsibilities:
- Receive alert analysis requests
- Call orchestration workflow
- Return structured analysis result
- Save final analyst action
- Expose metrics for demo and judging

Suggested endpoints:
- `GET /alerts`
- `GET /alerts/{id}`
- `POST /alerts/{id}/analyze`
- `POST /alerts/{id}/verify`
- `POST /alerts/{id}/draft-str`
- `POST /alerts/{id}/finalize`
- `GET /metrics`

### 3. Orchestration Layer

Responsibilities:
- Control the end-to-end review workflow
- Keep prompts and agent calls consistent
- Pass relevant context between steps
- Normalize outputs into one stable schema

Recommended output schema:
- `decision`
- `confidence`
- `typologies`
- `reasoning`
- `supporting_transactions`
- `verifier_status`
- `verifier_reasoning`
- `str_draft`
- `human_action`

### 4. Triage Agent

Responsibilities:
- Review suspicious alert context
- Decide `Escalate` or `Dismiss`
- Explain the decision in analyst-friendly language
- Reference suspicious patterns such as structuring or rapid pass-through

Input:
- alert metadata
- transaction history
- customer context
- typology references

Output:
- recommended action
- explanation
- confidence
- cited evidence

### 5. Verifier Agent

Responsibilities:
- Re-check the triage result independently
- Detect weak reasoning or unsupported conclusions
- Force human review on disagreement or low-confidence cases

Why it matters:
- This is a strong differentiator for the hackathon demo
- It makes the system feel safer and more regulator-defensible

### 6. Knowledge / Retrieval Layer

Responsibilities:
- Provide AML typology context to the agents
- Keep explanations grounded in known fraud / AML patterns
- Support Malaysia-first positioning with BNM-aligned references

Likely sources:
- FATF typologies
- Bank Negara Malaysia guidance
- Curated internal notes for demo use

### 7. STR Draft Generator

Responsibilities:
- Turn the analysis into a first-draft Suspicious Transaction Report
- Structure the report so an analyst can quickly edit and approve it

Key rule:
- AI drafts the report, but the human analyst is always the final decision-maker

### 8. Storage Layer

Use a lightweight storage approach for the hackathon:
- JSON files or SQLite for demo state
- Store sample alerts
- Store agent outputs
- Store final analyst actions
- Store simple demo metrics

## Demo Scope

### Must Have

- Alert queue
- Alert detail page
- AI triage
- Explanation with evidence
- Verifier step
- STR draft
- Human approve / override action

### Nice to Have

- Confidence score
- Typology tags
- Audit trail
- Metrics dashboard

### Out of Scope

- Real banking integrations
- Full case management platform
- Full graph investigation across many accounts
- Model training
- Enterprise-grade auth

## Suggested Folder Structure

```text
frontend/
  src/
    pages/
    components/
    api/

backend/
  app/
    main.py
    routes/
    services/
    orchestration/
    prompts/
    retrieval/
    storage/

data/
  sample_alerts/
  typologies/

docs/
  architecture.md
  demo-script.md
```

## Why This Architecture Works For Judging

- It is practical: solves one real workflow deeply.
- It is technically clear: each module has a visible role.
- It is explainable: reasoning and evidence are surfaced.
- It is safer than a plain chatbot: verifier agent plus human approval.
- It is commercially believable: saves analyst time and improves consistency.

## One-Line Pitch

Malaysia-first AML analyst copilot that triages suspicious alerts, explains why, verifies itself, and drafts STRs with a human always in control.
