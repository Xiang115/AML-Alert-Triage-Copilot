# AML Alert-Triage Copilot

NexHack 2026 — Track 2: FinTech & Cyber-Defense Engineering

The AML Alert-Triage Copilot is a multi-agent system designed to assist banking anti-money laundering (AML) compliance analysts in triaging suspicious transaction alerts. Leveraging DeepSeek-v4 language models, the copilot analyzes transaction typologies, runs an adversarial verifier to challenge false-positive escalations, drafts structured Suspicious Activity Reports (STR), and reports workload-reduction metrics on a held-out synthetic transaction dataset.

---

## Architecture and Workflow

The system is split into a React-based analyst console and a Python FastAPI backend orchestrating the multi-agent pipeline. 

![System Architecture](docs/architecture.png)


### Multi-Agent Pipeline Mechanics
1. **Knowledge Retrieval**: Fetches relevant typology guidance (e.g., pass-through, structuring, dormant accounts) from a curated local knowledge base.
2. **Triage Agent (DeepSeek-v4-pro)**: Evaluates the alert history and account profiles to recommend escalation or dismissal, calculating a confidence metric based on indicator coverage.
3. **Verifier Agent (DeepSeek-v4-flash)**: Acts as an adversarial challenger. It tests the triage recommendation against specific typology distinguishing tests (e.g., distinguishing a benign business sweep from a pass-through laundering flow) to prevent false-positive escalations.
4. **STR Draft Generator (DeepSeek-v4-pro)**: Generates a structured Suspicious Activity Report narrative including the activity summary and grounds for suspicion.

---

## Key Features

* **Adversarial QA Pushback**: The Verifier Agent challenges triage recommendations, flagging borderline cases (e.g., `HERO-001` Aisyah binti Kamal) for human review rather than automatic escalation, reducing compliance workload.
* **Slate & Mint (Cyber-Defense) Console**: A modern, clean, dark-themed interface built specifically for security and financial audit contexts. Includes left-border highlighting of cited transactions and adversarial warning banners.
* **Demo-First Resilience**: Backend pre-loads 12 optimized demo/hero cases from `results.json` and serves them from memory. The live `/triage` route runs the real pipeline (Q&A only) and falls back to the precomputed result if the provider errors, so the filmed demo never breaks on camera (ADR-0003); it never mutates the precomputed source.
* **Offline Evaluation Suite**: Measures `accuracyVsLabels` for real by running the live triage agent over a stratified **held-out** sample (default 60) of SynthAML alerts and comparing its recommendation to the Report/Dismiss labels (ADR-0004) — not a rule-based classifier. `falsePositiveReduction` is the share of recommended-dismiss alerts that are truly benign.

---

## Directory Structure

```text
/
├── backend/
│   ├── agents/          # Triage, Verifier, STR Drafter, and Confidence logic
│   ├── data/            # results.json precomputes, CSV loaders, and metrics
│   │   ├── fixtures/    # Pytest seed datasets
│   │   └── typologies/  # Curated FATF/BNM typology context cards
│   ├── eval/            # evaluate.py offline validation script
│   ├── tests/           # 50 passing backend unit and integration tests
│   ├── main.py          # FastAPI application entrypoint
│   └── config.py        # Environment variables and runtime thresholds
├── frontend/
│   ├── src/             # React console source code
│   └── package.json     # Vite and UI dependencies
└── docs/                # Product Requirement Documents and ADRs
```

---

## API Contract

All endpoints exchange camelCase JSON payloads. Internal Python models map to snake_case.

* **`GET /alerts`**: Retrieves the queue list. Transactions are omitted to optimize payload size.
* **`GET /alerts/{alertId}`**: Retrieves the detailed alert object, embedding transactions and precomputed triage.
* **`POST /alerts/{alertId}/triage`**: Triggers a live multi-agent pipeline execution (Q&A only). Returns a fresh result without mutating the demo source; falls back to the precomputed triage on provider failure.
* **`POST /alerts/{alertId}/decision`**: Persists the analyst's disposition (`approve` or `override`) and STR edits in-memory.
* **`GET /metrics`**: Serves measured system accuracy and workload-reduction statistics (404 `METRICS_NOT_READY` until the eval suite has run).
* **`POST /reset`**: Reloads the initial dataset state to clear in-memory decision edits.

---

## Getting Started

### Prerequisites
- Python 3.14+
- Node.js 18+

### Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # On Windows:
   .venv\Scripts\activate
   # On Unix/macOS:
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure your `.env` file using `.env.example` as a template:
   ```env
   DEEPSEEK_API_KEY=your_api_key_here
   DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
   ```
5. Run the FastAPI server:
   ```bash
   uvicorn main:app --reload
   ```

### Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd ../frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Set your environment configuration in a `.env` file:
   ```env
   VITE_MOCK=false
   VITE_API_BASE=http://localhost:8000
   ```
4. Start the development server:
   ```bash
   npm run dev
   ```

### Running the Evaluation Suite
Compute system performance metrics locally on holdout splits:
```bash
cd backend
python -m eval.evaluate
```

### Running Backend Unit Tests
Execute the unit tests verifying model logic, API routes, and schema formats:
```bash
cd backend
pytest
```
