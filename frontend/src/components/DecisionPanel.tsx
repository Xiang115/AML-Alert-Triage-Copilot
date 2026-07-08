import { useState } from 'react'
import { finalDispositionFor } from '../decision'
import type { Recommendation } from '../types'

interface DecisionPanelProps {
  recommendation: Recommendation
  onApprove: (note: string) => void
  onOverride: (note: string) => void
}

const labelFor = (value: Recommendation) => (value === 'escalate' ? 'Escalate' : 'Dismiss')

export function DecisionPanel({ recommendation, onApprove, onOverride }: DecisionPanelProps) {
  const [note, setNote] = useState('')
  const [needNote, setNeedNote] = useState(false)
  const approvedDisposition = finalDispositionFor(recommendation, 'approve')
  const overrideDisposition = finalDispositionFor(recommendation, 'override')

  // Overriding the AI must be justified — that reason is the audit trail's reason-for-record.
  const override = () => {
    if (!note.trim()) { setNeedNote(true); return }
    onOverride(note.trim())
  }

  return (
    <section className="shrink-0 rounded-lg border border-line bg-surface p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="label">Analyst decision</h3>
          <p className="mt-1 text-[12px] leading-relaxed text-ink-soft">
            Accepting keeps the AI recommendation; overriding flips it and requires a reason.
          </p>
        </div>
        <span className="shrink-0 rounded border border-line bg-paper px-2 py-1 font-mono text-[11px] text-ink-soft">
          AI: {labelFor(recommendation)}
        </span>
      </div>
      <textarea
        value={note}
        onChange={(e) => { setNote(e.target.value); if (e.target.value.trim()) setNeedNote(false) }}
        rows={2}
        placeholder="Reason / note (required to override the AI)…"
        className="mt-3 w-full resize-none rounded-md border border-line bg-surface p-2.5 text-[13px] text-ink outline-none placeholder:text-ink-faint focus:border-ink"
      />
      {needNote && (
        <p className="mt-1 text-[11px] text-escalate">Add a reason to override the AI's recommendation.</p>
      )}
      <div className="mt-3 grid grid-cols-2 gap-2.5">
        <button
          onClick={() => onApprove(note.trim())}
          className="rounded-md bg-ink px-3 py-2.5 text-left text-[13px] font-medium text-surface transition-opacity hover:opacity-90"
        >
          <span className="block">Accept AI</span>
          <span className="block font-mono text-[11px] font-normal opacity-80">{labelFor(approvedDisposition)}</span>
        </button>
        <button
          onClick={override}
          className="rounded-md border border-line px-3 py-2.5 text-left text-[13px] font-medium text-ink-soft transition-colors hover:border-ink hover:text-ink"
        >
          <span className="block">Override AI</span>
          <span className="block font-mono text-[11px] font-normal">{labelFor(overrideDisposition)}</span>
        </button>
      </div>
    </section>
  )
}
