interface DecisionPanelProps {
  onApprove: () => void
  onOverride: () => void
}

export function DecisionPanel({ onApprove, onOverride }: DecisionPanelProps) {
  return (
    <section className="rounded-xl border border-slate-900 bg-slate-950/20 p-4 space-y-3 flex-shrink-0">
      <div>
        <h3 className="text-3xs font-black uppercase tracking-wider text-slate-500">Submit Decision</h3>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <button
          onClick={onApprove}
          className="flex items-center justify-center gap-1.5 rounded bg-teal-600 hover:bg-teal-500 py-2.5 text-2xs font-bold text-slate-950 cursor-pointer shadow-sm shadow-teal-500/10 transition-colors"
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          Approve Call
        </button>
        <button
          onClick={onOverride}
          className="flex items-center justify-center gap-1.5 rounded border border-slate-850 bg-slate-900/40 hover:bg-slate-900 py-2.5 text-2xs font-bold text-slate-400 hover:text-white cursor-pointer transition-colors"
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
          </svg>
          Override Call
        </button>
      </div>
    </section>
  )
}
