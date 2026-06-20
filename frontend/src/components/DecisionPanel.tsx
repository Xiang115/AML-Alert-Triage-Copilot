interface DecisionPanelProps {
  onApprove: () => void
  onOverride: () => void
}

export function DecisionPanel({ onApprove, onOverride }: DecisionPanelProps) {
  return (
    <section className="shrink-0 rounded-lg border border-line bg-surface p-5">
      <h3 className="label">Analyst decision</h3>
      <div className="mt-3 grid grid-cols-2 gap-2.5">
        <button
          onClick={onApprove}
          className="rounded-md bg-ink py-2.5 text-[13px] font-medium text-surface transition-opacity hover:opacity-90"
        >
          Approve
        </button>
        <button
          onClick={onOverride}
          className="rounded-md border border-line py-2.5 text-[13px] font-medium text-ink-soft transition-colors hover:border-ink hover:text-ink"
        >
          Override
        </button>
      </div>
    </section>
  )
}
