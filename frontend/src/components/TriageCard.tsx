import type { TriageResult } from '../types'

interface TriageCardProps {
  triage: TriageResult
  isTriaging: boolean
  triageStep: string
  onRunLive: () => void
}

export function TriageCard({ triage, isTriaging, triageStep, onRunLive }: TriageCardProps) {
  return (
    <section className="rounded-xl border border-slate-900 bg-slate-950/20 p-4 space-y-3.5">
      <div className="flex items-center justify-between border-b border-slate-900 pb-2">
        <div className="flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-teal-500 animate-pulse"></span>
          <h3 className="text-2xs font-black uppercase tracking-wider text-teal-400">Copilot Triage Recommendation</h3>
        </div>
        {/* Live Triage trigger */}
        <button
          onClick={onRunLive}
          disabled={isTriaging}
          className={`flex items-center gap-1.5 rounded border border-teal-800/40 px-2 py-0.5 text-3xs font-bold text-teal-400 transition-all ${
            isTriaging
              ? 'bg-teal-950/20 cursor-not-allowed opacity-80'
              : 'hover:bg-teal-950/60 hover:text-white cursor-pointer'
          }`}
        >
          <svg className={`h-2.5 w-2.5 ${isTriaging ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 7.89M9 11l3 3L22 4" />
          </svg>
          {isTriaging ? 'Running...' : 'Run Live'}
        </button>
      </div>

      {isTriaging ? (
        <div className="flex flex-col items-center justify-center py-6 text-center">
          <div className="relative flex h-8 w-8 items-center justify-center rounded-full bg-slate-900 border border-teal-500/20 mb-2">
            <div className="absolute inset-0 rounded-full border border-teal-500/10 border-t-teal-500 animate-spin"></div>
          </div>
          <span className="text-2xs font-semibold text-slate-300">{triageStep}</span>
          <span className="text-3xs font-mono text-slate-500 mt-1 uppercase tracking-widest">Deepseek Live Session</span>
        </div>
      ) : (
        <div className="space-y-3">
          {/* Recommendation Banner */}
          <div className="flex items-center gap-4">
            <div className={`flex items-center gap-2 rounded border px-2.5 py-1 text-2xs font-black tracking-widest uppercase ${
              triage.recommendation === 'escalate'
                ? 'bg-rose-950/15 border-rose-900/50 text-rose-400'
                : 'bg-emerald-950/15 border-emerald-900/50 text-emerald-400'
            }`}>
              {triage.recommendation}
            </div>

            <div className="flex-grow">
              <div className="flex justify-between items-center text-3xs font-bold uppercase tracking-wider text-slate-500 mb-0.5">
                <span>Confidence Indicator</span>
                <span className="text-teal-400 font-mono font-bold">{Math.round(triage.confidence * 100)}%</span>
              </div>
              <div className="h-1 w-full rounded-full bg-slate-900 overflow-hidden border border-slate-900">
                <div
                  className="h-full rounded-full bg-teal-500 transition-all duration-300"
                  style={{ width: `${triage.confidence * 100}%` }}
                ></div>
              </div>
            </div>
          </div>

          {/* Typology Reference */}
          <div className="rounded-lg bg-slate-950/45 border border-slate-900 p-2.5 flex items-center justify-between gap-3 text-2xs">
            <div>
              <span className="block text-3xs font-bold uppercase tracking-wider text-slate-500">Matched Typology</span>
              <span className="font-bold text-slate-300 mt-0.5">
                {triage.matchedTypology.code} &mdash; {triage.matchedTypology.name}
              </span>
            </div>
            <span className="rounded bg-slate-900 border border-slate-800 px-1.5 py-0.5 font-mono text-3xs text-slate-500 font-semibold">
              {triage.matchedTypology.source}
            </span>
          </div>

          {/* Narrative Explanation */}
          <div>
            <span className="block text-3xs font-bold uppercase tracking-wider text-slate-500 mb-1">Evidence Summary</span>
            <p className="text-2xs leading-relaxed text-slate-400 bg-slate-950/10 border border-slate-900 rounded-lg p-3 font-medium">
              {triage.explanation}
            </p>
          </div>
        </div>
      )}
    </section>
  )
}
