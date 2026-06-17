# Verifier is an adversarial QA agent, not a polite double-check

The demo's differentiator (beat 3) is the Verifier catching a wrong triage call. A second LLM fed
the same evidence and asked "do you agree?" is sycophantic and almost always agrees, so the wow
would not fire. We decided the Verifier takes an **adversarial role**: it assumes the Triage call may
be wrong and tests the evidence against the matched Typology Card's `distinguishingTest` and
`benignLookalike`, emitting `agreed` or `flagged` (also flags on confidence below threshold).

This also reads as a genuine second-line-of-defense, which is more regulator-defensible than a
re-check. Trade-off: it is the least deterministic option, which is why the live `/triage` run needs
a reproducibility strategy (see the demo determinism decision) and why we keep the option of a
rules-based floor under the LLM verifier if reproducibility proves flaky.

Rejected: same-prompt "double-check" (unreliable), different-model-only (doesn't direct disagreement),
pure rules-based verifier (reproducible but kills the agentic/typology-reasoning story).
