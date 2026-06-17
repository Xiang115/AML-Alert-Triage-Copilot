# STR draft is a structured object, not a freeform string

We chose a fully structured `STRDraft` object (subject, typology, period, activitySummary, cited
transactions, groundsForSuspicion, recommendedAction) instead of a single freeform Markdown string.
A structured, BNM-style report reads as a real regulatory artifact and lets the analyst edit specific
fields, which is more convincing in the demo than editing one prose blob.

This **changes the locked API contract**: `strDraft` and `Decision.editedStrDraft` become objects
(camelCase, nested), null unless the recommendation is `escalate`. It also adds frontend work
(per-field / array editing) against the 23 Jun deadline. To stay demo-safe we scope the editable
surface: only `activitySummary` and `groundsForSuspicion` are richly editable on camera; `subject`
and the cited-transaction table render populated/read-only.

Trade-off: more frontend effort than a single textarea (the simpler rejected option B), accepted for
a more credible, regulator-shaped report. Rejected: freeform paragraph (reads like a chatbot blurb).
