import { useState } from 'react'

interface DecisionPanelProps {
  onApprove: (note: string) => void
  onOverride: (note: string) => void
}

export function DecisionPanel({ onApprove, onOverride }: DecisionPanelProps) {
  const [note, setNote] = useState('')
  const [needNote, setNeedNote] = useState(false)

  // Overriding the AI must be justified — that reason is the audit trail's reason-for-record.
  const override = () => {
    if (!note.trim()) { setNeedNote(true); return }
    onOverride(note.trim())
  }

  return (
    <section className="shrink-0 rounded-lg border border-line bg-surface p-5">
      <h3 className="label">Analyst decision</h3>
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
          className="rounded-md bg-ink py-2.5 text-[13px] font-medium text-surface transition-opacity hover:opacity-90"
        >
          Approve
        </button>
        <button
          onClick={override}
          className="rounded-md border border-line py-2.5 text-[13px] font-medium text-ink-soft transition-colors hover:border-ink hover:text-ink"
        >
          Override
        </button>
      </div>
    </section>
  )
}
