import type { Verifier } from '../types'
import { Badge } from './ui/Badge'

interface VerifierPanelProps {
  verifier: Verifier
}

export function VerifierPanel({ verifier }: VerifierPanelProps) {
  return (
    <section className="rounded-xl border border-slate-900 bg-slate-950/20 p-4 space-y-3">
      <div className="flex items-center justify-between border-b border-slate-900 pb-2">
        <div className="flex items-center gap-1.5">
          <svg className="h-3.5 w-3.5 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <h3 className="text-2xs font-black uppercase tracking-wider text-slate-400">Adversarial QA Verifier</h3>
        </div>
        <Badge tone={verifier.status === 'flagged' ? 'bg-amber-500/10 text-amber-500 border border-amber-500/20' : 'bg-slate-900 text-slate-500 border border-slate-800'}>
          {verifier.status}
        </Badge>
      </div>

      {verifier.status === 'flagged' ? (
        <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 space-y-2">
          <div className="flex items-start gap-2">
            <div className="rounded-full bg-amber-500/10 p-0.5 text-amber-500 flex-shrink-0 mt-0.5">
              <svg className="h-3.5 w-3.5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zm-1 9a1 1 0 01-1-1v-4a1 1 0 112 0v4a1 1 0 01-1 1z" clipRule="evenodd" />
              </svg>
            </div>
            <div>
              <span className="block text-3xs font-extrabold text-amber-500 uppercase tracking-wide">Distinguishing Test Alert</span>
              <p className="mt-0.5 text-2xs text-amber-200/90 leading-relaxed font-medium">
                {verifier.note}
              </p>
            </div>
          </div>
          <div className="text-3xs font-mono text-amber-500/60 leading-snug border-t border-amber-500/10 pt-1.5 font-medium">
            Confidence score capped below threshold (0.60). Manual override required to finalize.
          </div>
        </div>
      ) : (
        <div className="rounded-lg border border-slate-900 bg-slate-950/20 p-3 flex items-start gap-2">
          <div className="rounded-full bg-emerald-500/15 p-0.5 text-emerald-400 flex-shrink-0 mt-0.5">
            <svg className="h-3.5 w-3.5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
          </div>
          <div>
            <span className="block text-3xs font-extrabold text-slate-500 uppercase tracking-wide">Triage Call Verified</span>
            <p className="mt-0.5 text-2xs text-slate-400 leading-relaxed font-medium">
              {verifier.note}
            </p>
          </div>
        </div>
      )}
    </section>
  )
}
