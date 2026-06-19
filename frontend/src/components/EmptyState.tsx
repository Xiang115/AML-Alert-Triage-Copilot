export function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center p-8">
      <div className="relative flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-900 border border-slate-850 shadow-md mb-4 text-teal-400/90">
        <svg className="h-6 w-6 text-teal-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.2} d="M9.663 17h4.673M12 3v1m6.364.364l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
        </svg>
      </div>
      <h3 className="font-bold text-slate-300 text-2xs uppercase tracking-wider">Triage Analyst Desk</h3>
      <p className="mt-1.5 text-3xs text-slate-500 max-w-xs leading-relaxed">
        Select an account alert from the queue to start. The Copilot will analyze transaction patterns and provide structured regulatory explanations.
      </p>
    </div>
  )
}
