# Demo determinism: pin the demo path, free-run the rest

The filmed demo runs off precomputed `results.json`, but the live `POST /alerts/{id}/triage` endpoint
exists so judges can see a real run. With an adversarial LLM verifier (ADR-0001), a live run on the
hero case could agree this time and collapse the wow. We decided: run the whole pipeline at
**temperature 0**, and **engineer the hero case with enough margin** that the typology's
distinguishing test clearly fails — so the Verifier flags it on essentially every run. The hero
`/triage` is therefore a *genuine* live run, with replay-of-the-precomputed-result-behind-the-spinner
as an on-camera fallback if the API/network hiccups. The other alerts run genuinely live to prove the
pipeline is real.

Trade-off: temp 0 + an engineered case is slightly less "honest live AI" than free-running, but the
filmed/judged moment cannot flake. A rules-based floor under the Verifier (ADR-0001) is kept as an
optional belt-and-suspenders, built only if time allows.
