import { useState } from 'react'
import type { STRDraft, SubmissionAck } from '../types'
import { Badge } from './ui/Badge'

interface StrEditorProps {
  strDraft: STRDraft
  summary: string
  onSummaryChange: (value: string) => void
  grounds: string[]
  onAddGround: (text: string) => void
  onRemoveGround: (idx: number) => void
  canExport: boolean
  onExport: () => void
  ack: SubmissionAck | null
}

export function StrEditor({ strDraft, summary, onSummaryChange, grounds, onAddGround, onRemoveGround, canExport, onExport, ack }: StrEditorProps) {
  const [newGroundItem, setNewGroundItem] = useState('')

  const addGroundItem = () => {
    if (newGroundItem.trim()) {
      onAddGround(newGroundItem.trim())
      setNewGroundItem('')
    }
  }

  return (
    <section className="flex grow flex-col overflow-hidden rounded-lg border border-line bg-surface p-5">
      <div className="flex shrink-0 items-center justify-between">
        <h3 className="label">Suspicious transaction report</h3>
        <Badge tone="bg-paper text-ink-soft">Draft</Badge>
      </div>

      <div className="mt-4 grow space-y-5 overflow-y-auto pr-1">
        {/* Metadata */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="label">Institution</div>
            <div className="mt-1 text-[13px] text-ink">{strDraft.reportingInstitution}</div>
          </div>
          <div>
            <div className="label">Report date</div>
            <div className="mt-1 font-mono text-[13px] text-ink">{strDraft.reportDate.substring(0, 10)}</div>
          </div>
        </div>

        {/* Narrative */}
        <div>
          <div className="mb-1.5 flex items-baseline justify-between">
            <span className="label">Narrative</span>
            <span className="text-[11px] text-ink-faint">Drafted by AI · editable</span>
          </div>
          <textarea
            value={summary}
            onChange={(e) => onSummaryChange(e.target.value)}
            rows={4}
            className="w-full resize-none rounded-md border border-line bg-surface p-3 text-[13px] leading-relaxed text-ink outline-none focus:border-ink"
          />
        </div>

        {/* Grounds for suspicion */}
        <div>
          <div className="label mb-1.5">Grounds for suspicion</div>
          <ul className="space-y-1.5">
            {grounds.map((g, idx) => (
              <li key={idx} className="flex items-start justify-between gap-3 border-l-2 border-line py-0.5 pl-3">
                <span className="text-[13px] leading-relaxed text-ink">{g}</span>
                <button
                  onClick={() => onRemoveGround(idx)}
                  aria-label="Remove ground"
                  className="shrink-0 text-[12px] text-ink-faint hover:text-escalate"
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
          <div className="mt-2 flex gap-2">
            <input
              type="text"
              value={newGroundItem}
              onChange={(e) => setNewGroundItem(e.target.value)}
              placeholder="Add a ground…"
              onKeyDown={(e) => e.key === 'Enter' && addGroundItem()}
              className="grow rounded-md border border-line bg-surface px-3 py-1.5 text-[13px] text-ink outline-none placeholder:text-ink-faint focus:border-ink"
            />
            <button
              onClick={addGroundItem}
              className="rounded-md border border-line px-3 text-[13px] font-medium text-ink-soft hover:border-ink hover:text-ink"
            >
              Add
            </button>
          </div>
        </div>

        {/* Recommended action */}
        <div>
          <div className="label">Recommended action</div>
          <p className="mt-1 text-[13px] leading-relaxed text-ink-soft">{strDraft.recommendedAction}</p>
        </div>
      </div>

      {/* goAML export — the integration seam. Unlocks only after an escalate sign-off. */}
      <div className="mt-4 shrink-0 border-t border-line pt-4">
        {ack ? (
          <div className="rounded-md border border-verified bg-verified-soft px-3 py-2.5">
            <div className="flex items-center gap-1.5 text-[12px] font-medium text-verified">
              <span>✓</span> Filed to goAML · accepted
            </div>
            <div className="mt-0.5 font-mono text-[11px] text-ink-soft">ref {ack.submissionRef}</div>
          </div>
        ) : canExport ? (
          <div className="flex items-center justify-between gap-3">
            <button
              onClick={onExport}
              className="rounded-md bg-ink px-4 py-2.5 text-[13px] font-medium text-surface transition-opacity hover:opacity-90"
            >
              Export &amp; file goAML STR
            </button>
            <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-ink-soft">
              <span className="text-verified">✓</span> goAML 4.x · schema-valid
            </span>
          </div>
        ) : (
          <p className="text-[12px] leading-relaxed text-ink-faint">
            Approve this escalation to file. The goAML STR exports only after analyst sign-off.
          </p>
        )}
      </div>
    </section>
  )
}
