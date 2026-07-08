import { useEffect, useState } from 'react'
import { getHandbook } from '../api'
import type { CoachingHandbook, TriageResult, TypologyCard } from '../types'
import typologiesFixture from '../fixtures/typologies.json'

// Single source: the curated typology cards (synced from backend/data/typologies via
// sync_fixtures; test_fixture_sync guards against drift). Keyed by code for O(1) lookup.
const BY_CODE = new Map(
  (typologiesFixture as { typologies: TypologyCard[] }).typologies.map((c) => [c.code, c]),
)

// Junior-analyst coaching (Slice B): the playbook for the matched typology. The distinguishing
// test, benign look-alike and regulator red flags come from the curated card; the "what to check"
// checklist is fetched from the live DeepSeek RAG endpoint when a backend is present (each check
// cited to a real KB page), and falls back to the card's curated checks in mock mode.
export function CoachingPanel({ triage }: { triage: TriageResult }) {
  const code = triage.matchedTypology.code
  const card = BY_CODE.get(code)
  const [handbook, setHandbook] = useState<CoachingHandbook | null>(null)

  useEffect(() => {
    let active = true
    getHandbook(code).then((h) => { if (active) setHandbook(h) }).catch(() => {})
    return () => { active = false }
  }, [code])

  if (!card) return null
  const ragChecks = handbook?.whatToCheck?.length ? handbook.whatToCheck : null

  return (
    <section className="rounded-lg border border-line bg-surface p-5">
      <h3 className="label">Analyst playbook — {card.name}</h3>

      <p className="mt-3 text-[13px] leading-relaxed text-ink-soft">
        <b className="text-ink">Distinguishing test:</b> {card.distinguishingTest}
      </p>
      <p className="mt-2 text-[13px] leading-relaxed text-ink-soft">
        <b className="text-ink">Benign look-alike:</b> {card.benignLookalike}
      </p>

      {card.redFlags?.length ? (
        <div className="mt-3">
          <div className="text-[12px] font-semibold uppercase tracking-wide text-ink-soft">
            Regulator red flags <span className="font-normal normal-case text-ink-faint">· BNM AML/CFT PD App. 4 / FATF</span>
          </div>
          <ul className="mt-1.5 space-y-1.5 text-[13px] text-ink-soft">
            {card.redFlags.map((f, i) => (
              <li key={i} className="border-l-2 border-line pl-3">{f}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {ragChecks ? (
        <div className="mt-3">
          <div className="text-[12px] font-semibold uppercase tracking-wide text-ink-soft">
            What to check <span className="font-normal normal-case text-ink-faint">· generated from the knowledge base (RAG)</span>
          </div>
          <ul className="mt-1.5 space-y-1.5 text-[13px] text-ink-soft">
            {ragChecks.map((c, i) => (
              <li key={i} className="border-l-2 border-line pl-3">
                {c.check} <span className="font-mono text-[11px] text-ink-faint">— {c.source}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : card.whatToCheck?.length ? (
        <div className="mt-3">
          <div className="text-[12px] font-semibold uppercase tracking-wide text-ink-soft">What to check</div>
          <ul className="mt-1.5 list-disc space-y-1 pl-5 text-[13px] text-ink-soft">
            {card.whatToCheck.map((q, i) => <li key={i}>{q}</li>)}
          </ul>
        </div>
      ) : null}

      {card.citation ? (
        <div className="mt-3 font-mono text-[11px] text-ink-faint">Policy: {card.citation}</div>
      ) : null}
    </section>
  )
}
