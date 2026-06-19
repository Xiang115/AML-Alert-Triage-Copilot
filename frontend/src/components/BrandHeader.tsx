export function BrandHeader() {
  return (
    <div className="p-4 border-b border-slate-900/80 bg-slate-950/10">
      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-teal-600 to-sky-500 shadow-md shadow-teal-500/10">
          <svg className="h-4.5 w-4.5 text-slate-950" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
        </div>
        <div>
          <h1 className="text-sm font-bold tracking-tight text-white">
            AMLY <span className="text-teal-400 font-medium text-xs">Copilot</span>
          </h1>
          <span className="text-3xs font-mono uppercase tracking-wider text-slate-500">Security Desk</span>
        </div>
      </div>
    </div>
  )
}
