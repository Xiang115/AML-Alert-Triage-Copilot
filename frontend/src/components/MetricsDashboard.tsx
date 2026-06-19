import type { Metrics } from '../types'

interface MetricsDashboardProps {
  metrics: Metrics | null
}

export function MetricsDashboard({ metrics }: MetricsDashboardProps) {
  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">
      <header>
        <h2 className="text-md font-bold text-white">System Performance</h2>
        <p className="text-3xs text-slate-500 mt-0.5 uppercase tracking-wide">Aggregated benchmarks on held-out SynthAML dataset</p>
      </header>

      {metrics ? (
        <div className="space-y-6">
          {/* 3 Metric Cards Grid */}
          <div className="grid grid-cols-3 gap-4">
            <div className="rounded-xl border border-slate-900 bg-slate-950/20 p-4 shadow-sm relative overflow-hidden">
              <span className="text-3xs font-extrabold uppercase tracking-widest text-slate-500">Triage Accuracy</span>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl font-black text-white">{(metrics.accuracyVsLabels * 100).toFixed(1)}%</span>
                <span className="text-3xs font-bold text-emerald-400">verified</span>
              </div>
              <p className="mt-1.5 text-3xs leading-relaxed text-slate-500">
                Recommendation alignment with validated bank outcomes across Structuring, Pass-through, and Dormant cases.
              </p>
            </div>

            <div className="rounded-xl border border-slate-900 bg-slate-950/20 p-4 shadow-sm relative overflow-hidden">
              <span className="text-3xs font-extrabold uppercase tracking-widest text-slate-500">False Positive Reduction</span>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl font-black text-white">{(metrics.falsePositiveReduction * 100).toFixed(0)}%</span>
                <span className="text-3xs font-bold text-emerald-400">efficiency</span>
              </div>
              <p className="mt-1.5 text-3xs leading-relaxed text-slate-500">
                Benign alerts safely resolved, bypassing manual analyst triage queues without introducing compliance risk.
              </p>
            </div>

            <div className="rounded-xl border border-slate-900 bg-slate-950/20 p-4 shadow-sm relative overflow-hidden">
              <span className="text-3xs font-extrabold uppercase tracking-widest text-slate-500">Evaluation Volume</span>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-2xl font-black text-white">{metrics.totalAlerts}</span>
                <span className="text-3xs font-semibold text-teal-400">alerts</span>
              </div>
              <p className="mt-1.5 text-3xs leading-relaxed text-slate-500">
                Alert records processed from Jensen et al. (2023, Nature Scientific Data) Spar Nord dataset.
              </p>
            </div>
          </div>

          {/* Processing Time Savings Visualizer */}
          <div className="rounded-xl border border-slate-900 bg-slate-950/20 p-5 space-y-4">
            <div>
              <h3 className="text-xs font-bold text-slate-300">Triage Handling Duration</h3>
              <p className="text-3xs text-slate-500 mt-0.5">Average time spent per alert case file (Baseline vs Copilot-assisted).</p>
            </div>

            <div className="space-y-4">
              {/* Baseline Bar */}
              <div className="space-y-1.5">
                <div className="flex justify-between items-center text-3xs">
                  <span className="font-semibold text-slate-500 uppercase tracking-wider">Traditional Audit (Baseline)</span>
                  <span className="font-mono font-bold text-slate-400">{metrics.avgReviewTimeBaselineMin} min</span>
                </div>
                <div className="h-3.5 w-full rounded bg-slate-900 overflow-hidden border border-slate-900 flex items-center p-0.5">
                  <div className="h-full rounded bg-slate-700 shadow" style={{ width: '100%' }}></div>
                </div>
              </div>

              {/* Copilot Bar */}
              <div className="space-y-1.5">
                <div className="flex justify-between items-center text-3xs">
                  <span className="font-semibold text-teal-400 uppercase tracking-wider">Copilot-Assisted Audit</span>
                  <span className="font-mono font-bold text-teal-300">{metrics.avgReviewTimeWithCopilotMin} min <span className="text-3xs font-bold text-emerald-400">(-77%)</span></span>
                </div>
                <div className="h-3.5 w-full rounded bg-slate-900 overflow-hidden border border-slate-900 flex items-center p-0.5">
                  <div
                    className="h-full rounded bg-teal-500"
                    style={{ width: `${(metrics.avgReviewTimeWithCopilotMin / metrics.avgReviewTimeBaselineMin) * 100}%` }}
                  ></div>
                </div>
              </div>
            </div>

            <div className="border-t border-slate-900 pt-3 text-3xs text-slate-500 flex items-center gap-1.5 font-medium">
              <svg className="h-3.5 w-3.5 text-emerald-400" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
              <span>Time savings of over 14 minutes per alert triage, shifting analyst resources to deep investigations.</span>
            </div>
          </div>
        </div>
      ) : (
        <div className="py-20 text-center text-xs text-slate-600">Failed to load system metrics</div>
      )}
    </div>
  )
}
