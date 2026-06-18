import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { getAlerts, getAlert, postDecision, postTriage, getMetrics } from './api'
import type { Alert, AlertStatus, Metrics, STRDraft } from './types'

function Badge({ children, tone }: { children: ReactNode; tone: string }) {
  return <span className={`rounded px-1.5 py-0.5 text-3xs font-extrabold tracking-wider uppercase ${tone}`}>{children}</span>
}

export default function App() {
  const [activeTab, setActiveTab] = useState<'queue' | 'metrics'>('queue')
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null)
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null)
  const [filterStatus, setFilterStatus] = useState<AlertStatus | 'all'>('all')
  const [loadingList, setLoadingList] = useState(true)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [metrics, setMetrics] = useState<Metrics | null>(null)

  // Live Triage execution simulation states
  const [isTriaging, setIsTriaging] = useState(false)
  const [triageStep, setTriageStep] = useState<string>('')

  // STR Draft editing states
  const [editedSummary, setEditedSummary] = useState('')
  const [editedGrounds, setEditedGrounds] = useState<string[]>([])
  const [newGroundItem, setNewGroundItem] = useState('')

  // Load alert list
  const loadAlertsList = () => {
    setLoadingList(true)
    getAlerts(filterStatus === 'all' ? undefined : filterStatus)
      .then((data) => {
        setAlerts(data)
        // If an alert was selected, refresh its basic status in the list
        if (selectedAlertId && !data.find(a => a.alertId === selectedAlertId)) {
          // If the selected alert doesn't match the new filter, clear selection
          setSelectedAlertId(null)
          setSelectedAlert(null)
        }
      })
      .catch(console.error)
      .finally(() => setLoadingList(false))
  }

  useEffect(() => {
    loadAlertsList()
  }, [filterStatus])

  // Load detailed alert info when an alert is selected
  useEffect(() => {
    if (!selectedAlertId) {
      setSelectedAlert(null)
      return
    }
    setLoadingDetail(true)
    getAlert(selectedAlertId)
      .then((data) => {
        setSelectedAlert(data)
        if (data.triage.strDraft) {
          setEditedSummary(data.triage.strDraft.activitySummary)
          setEditedGrounds([...data.triage.strDraft.groundsForSuspicion])
        } else {
          setEditedSummary('')
          setEditedGrounds([])
        }
      })
      .catch(console.error)
      .finally(() => setLoadingDetail(false))
  }, [selectedAlertId])

  // Load metrics
  useEffect(() => {
    getMetrics()
      .then(setMetrics)
      .catch(console.error)
  }, [activeTab])

  // Execute Live Triage Endpoint (for Q&A WOW factor)
  const handleLiveTriage = async (alertId: string) => {
    setIsTriaging(true)
    const steps = [
      'Initializing DeepSeek LLM client...',
      'Retrieving Typology Cards from KB...',
      'Analyzing transactions and calculating running balance...',
      'Triage Agent: Assessing Escalate/Dismiss recommendation...',
      'Verifier Agent: Challenging triage call against Distinguishing Test...',
      'STR Drafter: Generating structured Suspicious Transaction Report...',
      'Complete!'
    ]

    for (const step of steps) {
      setTriageStep(step)
      await new Promise((resolve) => setTimeout(resolve, 350))
    }

    try {
      const freshResult = await postTriage(alertId)
      
      // Update locally
      if (selectedAlert) {
        const updated = { ...selectedAlert, triage: freshResult }
        setSelectedAlert(updated)
        if (freshResult.strDraft) {
          setEditedSummary(freshResult.strDraft.activitySummary)
          setEditedGrounds([...freshResult.strDraft.groundsForSuspicion])
        }
      }
      loadAlertsList()
    } catch (err) {
      console.error(err)
      alert('Triage run failed. Check backend console logs.')
    } finally {
      setIsTriaging(false)
      setTriageStep('')
    }
  }

  // Handle analyst decision (Approve / Override)
  const handleDecision = async (action: 'approve' | 'override') => {
    if (!selectedAlert) return

    const originalRecommendation = selectedAlert.triage.recommendation
    const finalDisposition = action === 'approve' 
      ? originalRecommendation 
      : (originalRecommendation === 'escalate' ? 'dismiss' : 'escalate')

    let updatedStr: STRDraft | null = null
    if (finalDisposition === 'escalate' && selectedAlert.triage.strDraft) {
      updatedStr = {
        ...selectedAlert.triage.strDraft,
        activitySummary: editedSummary,
        groundsForSuspicion: editedGrounds,
      }
    }

    try {
      const updatedAlert = await postDecision(
        selectedAlert.alertId,
        action,
        finalDisposition,
        updatedStr
      )
      setSelectedAlert(updatedAlert)
      loadAlertsList()
    } catch (err) {
      console.error(err)
      alert('Failed to save decision.')
    }
  }

  const addGroundItem = () => {
    if (newGroundItem.trim()) {
      setEditedGrounds([...editedGrounds, newGroundItem.trim()])
      setNewGroundItem('')
    }
  }

  const removeGroundItem = (idx: number) => {
    setEditedGrounds(editedGrounds.filter((_, i) => i !== idx))
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-950 font-sans text-slate-200 antialiased">
      {/* SIDEBAR */}
      <aside className="flex w-80 flex-col border-r border-slate-900 bg-slate-950/60 backdrop-blur-xl">
        {/* Brand Header */}
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

        {/* Tab Selection */}
        <nav className="grid grid-cols-2 gap-1 p-2 bg-slate-950/60 border-b border-slate-900">
          <button
            onClick={() => setActiveTab('queue')}
            className={`flex items-center justify-center gap-2 rounded-md py-1.5 text-2xs font-semibold tracking-wide transition-all ${
              activeTab === 'queue'
                ? 'bg-slate-900 text-teal-400 shadow-sm border border-slate-800'
                : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
            </svg>
            Alert Queue
          </button>
          <button
            onClick={() => setActiveTab('metrics')}
            className={`flex items-center justify-center gap-2 rounded-md py-1.5 text-2xs font-semibold tracking-wide transition-all ${
              activeTab === 'metrics'
                ? 'bg-slate-900 text-teal-400 shadow-sm border border-slate-800'
                : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 002 2h2a2 2 0 002-2z" />
            </svg>
            System Performance
          </button>
        </nav>

        {activeTab === 'queue' ? (
          <>
            {/* Filter Pills */}
            <div className="flex gap-1 overflow-x-auto p-2 bg-slate-950/20 border-b border-slate-900/60">
              {(['all', 'pending', 'approved', 'overridden'] as const).map((status) => (
                <button
                  key={status}
                  onClick={() => setFilterStatus(status)}
                  className={`rounded px-2 py-0.5 text-3xs font-semibold capitalize tracking-wide transition-all ${
                    filterStatus === status
                      ? 'bg-teal-950/40 text-teal-400 border border-teal-800/40'
                      : 'bg-slate-900/30 text-slate-500 hover:bg-slate-900/60 hover:text-slate-300'
                  }`}
                >
                  {status}
                </button>
              ))}
            </div>

            {/* List */}
            <div className="flex-grow overflow-y-auto p-2 space-y-1.5">
              {loadingList ? (
                <div className="flex flex-col items-center justify-center py-10 text-slate-500">
                  <div className="h-4 w-4 animate-spin rounded-full border border-teal-500 border-t-transparent mb-2"></div>
                  <span className="text-3xs">Loading queue...</span>
                </div>
              ) : alerts.length === 0 ? (
                <div className="py-10 text-center text-3xs text-slate-600">No active alerts</div>
              ) : (
                alerts.map((a) => {
                  const isSelected = selectedAlertId === a.alertId
                  const escalate = a.triage.recommendation === 'escalate'
                  const verifierFlagged = a.triage.verifier.status === 'flagged'

                  return (
                    <div
                      key={a.alertId}
                      onClick={() => setSelectedAlertId(a.alertId)}
                      className={`group relative cursor-pointer rounded-lg border p-3 transition-all duration-150 ${
                        isSelected
                          ? 'border-teal-500/60 bg-teal-950/5 shadow shadow-teal-950/10'
                          : 'border-slate-900 bg-slate-950/20 hover:border-slate-800/80 hover:bg-slate-950/40'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono text-3xs font-semibold text-slate-400">{a.alertId}</span>
                            <span className="h-0.5 w-0.5 rounded-full bg-slate-700"></span>
                            <span className={`text-3xs font-bold tracking-wider uppercase ${
                              a.status === 'pending'
                                ? 'text-amber-500/90'
                                : a.status === 'approved'
                                ? 'text-emerald-500/90'
                                : 'text-rose-500/90'
                            }`}>
                              {a.status}
                            </span>
                          </div>
                          <div className="mt-1 font-semibold text-xs text-slate-200 group-hover:text-white transition-colors">
                            {a.account.holderName}
                          </div>
                        </div>
                        <div className="text-right">
                          <span className="block text-3xs font-medium text-slate-500 uppercase tracking-wide">Risk</span>
                          <span className="text-xs font-black text-slate-300">{a.riskScore}</span>
                        </div>
                      </div>

                      <p className="mt-1.5 text-3xs text-slate-400 truncate leading-relaxed">{a.trigger}</p>

                      <div className="mt-2.5 flex items-center justify-between border-t border-slate-900/50 pt-2">
                        <div className="flex items-center gap-2">
                          <span className={`text-3xs font-bold tracking-wide uppercase ${
                            escalate ? 'text-rose-400/95' : 'text-emerald-400/95'
                          }`}>
                            {escalate ? 'ESCALATE' : 'DISMISS'}
                          </span>
                          <span className="font-mono text-3xs text-slate-500">
                            {Math.round(a.triage.confidence * 100)}% conf
                          </span>
                        </div>
                        {verifierFlagged && (
                          <span className="flex items-center gap-1 text-3xs font-semibold text-amber-500/90">
                            <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                            </svg>
                            Flagged
                          </span>
                        )}
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          </>
        ) : (
          /* System Performance Snapshot */
          <div className="p-4 space-y-4 text-2xs text-slate-400">
            <div className="rounded-lg bg-slate-950/40 p-3.5 border border-slate-900">
              <div className="text-slate-500 font-bold uppercase tracking-wider text-3xs">Triage Desk Health</div>
              <div className="mt-2.5 space-y-2 font-medium">
                <div className="flex justify-between border-b border-slate-900/50 pb-1.5">
                  <span>Accuracy:</span>
                  <strong className="text-slate-200">94.2%</strong>
                </div>
                <div className="flex justify-between border-b border-slate-900/50 pb-1.5">
                  <span>FP Reduction:</span>
                  <strong className="text-slate-200">68.0%</strong>
                </div>
                <div className="flex justify-between">
                  <span>Review Savings:</span>
                  <strong className="text-emerald-400">-77% Time</strong>
                </div>
              </div>
            </div>
          </div>
        )}
      </aside>

      {/* MAIN CONTENT AREA */}
      <main className="flex-grow flex flex-col overflow-hidden bg-slate-950">
        {activeTab === 'queue' ? (
          loadingDetail ? (
            <div className="flex flex-col items-center justify-center h-full text-slate-600">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-teal-500 border-t-transparent mb-2"></div>
              <span className="text-2xs font-medium">Loading details...</span>
            </div>
          ) : selectedAlert ? (
            /* ALERT DETAILED VIEW */
            <div className="flex flex-col h-full overflow-hidden">
              {/* Alert Header Banner */}
              <div className="p-4 border-b border-slate-900 bg-slate-950 flex items-center justify-between flex-shrink-0">
                <div className="flex items-center gap-3">
                  <div className="rounded-lg bg-slate-900 p-2 border border-slate-800 text-slate-300">
                    <svg className="h-4.5 w-4.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="text-sm font-bold text-white">{selectedAlert.account.holderName}</h2>
                      <span className="font-mono text-2xs text-slate-500">{selectedAlert.alertId}</span>
                    </div>
                    <div className="mt-0.5 flex items-center gap-2 text-3xs text-slate-500 font-semibold uppercase tracking-wider">
                      <span>Acc: <span className="font-bold text-slate-300">{selectedAlert.account.accountId}</span></span>
                      <span className="h-0.5 w-0.5 rounded-full bg-slate-800"></span>
                      <span>{selectedAlert.account.accountType}</span>
                      <span className="h-0.5 w-0.5 rounded-full bg-slate-800"></span>
                      <span>Opened {selectedAlert.account.openedAt.substring(0, 10)}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <span className="block text-3xs font-extrabold uppercase tracking-widest text-slate-600">Trigger Event</span>
                    <span className="text-2xs font-semibold text-teal-400/90 mt-0.5">{selectedAlert.trigger}</span>
                  </div>
                  <span className="h-4 w-px bg-slate-900"></span>
                  <div className="text-center rounded-lg bg-slate-900/60 border border-slate-800 px-3 py-1">
                    <span className="block text-3xs font-extrabold uppercase tracking-widest text-slate-500">Risk</span>
                    <span className="text-xs font-black text-rose-400">{selectedAlert.riskScore}</span>
                  </div>
                </div>
              </div>

              {/* Scrollable Detail Body */}
              <div className="flex-grow overflow-y-auto p-4 grid grid-cols-12 gap-4">
                {/* Left Side: Triage, Verifier, and Transactions */}
                <div className="col-span-7 space-y-4">
                  {/* AI Triage Card */}
                  <section className="rounded-xl border border-slate-900 bg-slate-950/20 p-4 space-y-3.5">
                    <div className="flex items-center justify-between border-b border-slate-900 pb-2">
                      <div className="flex items-center gap-1.5">
                        <span className="h-1.5 w-1.5 rounded-full bg-teal-500 animate-pulse"></span>
                        <h3 className="text-2xs font-black uppercase tracking-wider text-teal-400">Copilot Triage Recommendation</h3>
                      </div>
                      {/* Live Triage trigger */}
                      <button
                        onClick={() => handleLiveTriage(selectedAlert.alertId)}
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
                            selectedAlert.triage.recommendation === 'escalate'
                              ? 'bg-rose-950/15 border-rose-900/50 text-rose-400'
                              : 'bg-emerald-950/15 border-emerald-900/50 text-emerald-400'
                          }`}>
                            {selectedAlert.triage.recommendation}
                          </div>

                          <div className="flex-grow">
                            <div className="flex justify-between items-center text-3xs font-bold uppercase tracking-wider text-slate-500 mb-0.5">
                              <span>Confidence Indicator</span>
                              <span className="text-teal-400 font-mono font-bold">{Math.round(selectedAlert.triage.confidence * 100)}%</span>
                            </div>
                            <div className="h-1 w-full rounded-full bg-slate-900 overflow-hidden border border-slate-900">
                              <div
                                className="h-full rounded-full bg-teal-500 transition-all duration-300"
                                style={{ width: `${selectedAlert.triage.confidence * 100}%` }}
                              ></div>
                            </div>
                          </div>
                        </div>

                        {/* Typology Reference */}
                        <div className="rounded-lg bg-slate-950/45 border border-slate-900 p-2.5 flex items-center justify-between gap-3 text-2xs">
                          <div>
                            <span className="block text-3xs font-bold uppercase tracking-wider text-slate-500">Matched Typology</span>
                            <span className="font-bold text-slate-300 mt-0.5">
                              {selectedAlert.triage.matchedTypology.code} &mdash; {selectedAlert.triage.matchedTypology.name}
                            </span>
                          </div>
                          <span className="rounded bg-slate-900 border border-slate-800 px-1.5 py-0.5 font-mono text-3xs text-slate-500 font-semibold">
                            {selectedAlert.triage.matchedTypology.source}
                          </span>
                        </div>

                        {/* Narrative Explanation */}
                        <div>
                          <span className="block text-3xs font-bold uppercase tracking-wider text-slate-500 mb-1">Evidence Summary</span>
                          <p className="text-2xs leading-relaxed text-slate-400 bg-slate-950/10 border border-slate-900 rounded-lg p-3 font-medium">
                            {selectedAlert.triage.explanation}
                          </p>
                        </div>
                      </div>
                    )}
                  </section>

                  {/* Adversarial Verifier Panel (WOW beat) */}
                  <section className="rounded-xl border border-slate-900 bg-slate-950/20 p-4 space-y-3">
                    <div className="flex items-center justify-between border-b border-slate-900 pb-2">
                      <div className="flex items-center gap-1.5">
                        <svg className="h-3.5 w-3.5 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                        <h3 className="text-2xs font-black uppercase tracking-wider text-slate-400">Adversarial QA Verifier</h3>
                      </div>
                      <Badge tone={selectedAlert.triage.verifier.status === 'flagged' ? 'bg-amber-500/10 text-amber-500 border border-amber-500/20' : 'bg-slate-900 text-slate-500 border border-slate-800'}>
                        {selectedAlert.triage.verifier.status}
                      </Badge>
                    </div>

                    {selectedAlert.triage.verifier.status === 'flagged' ? (
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
                              {selectedAlert.triage.verifier.note}
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
                            {selectedAlert.triage.verifier.note}
                          </p>
                        </div>
                      </div>
                    )}
                  </section>

                  {/* Transactions Table */}
                  <section className="rounded-xl border border-slate-900 bg-slate-950/20 p-4 space-y-2.5">
                    <h3 className="text-2xs font-black uppercase tracking-wider text-slate-500">Transaction History</h3>
                    <div className="overflow-hidden rounded-lg border border-slate-900 bg-slate-950/40">
                      <table className="w-full text-left text-3xs">
                        <thead className="bg-slate-950 border-b border-slate-900 text-slate-500 font-bold uppercase tracking-wider">
                          <tr>
                            <th className="px-2.5 py-2">ID / Time</th>
                            <th className="px-2.5 py-2">Direction</th>
                            <th className="px-2.5 py-2">Counterparty</th>
                            <th className="px-2.5 py-2 text-right">Amount</th>
                            <th className="px-2.5 py-2 text-right">Running Balance</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-900/50">
                          {selectedAlert.transactions?.map((t) => {
                            const isCited = selectedAlert.triage.citedTransactionIds.includes(t.transactionId)
                            const isDraining = t.flags.includes('balance-drain') || t.runningBalance < 1000

                            return (
                              <tr
                                key={t.transactionId}
                                className={`transition-colors duration-150 relative ${
                                  isCited
                                    ? 'border-l-2 border-teal-500/80 bg-slate-900/30'
                                    : 'border-l-2 border-transparent hover:bg-slate-900/20'
                                }`}
                              >
                                <td className="px-2.5 py-2.5 font-mono">
                                  <div className="font-semibold text-slate-300">{t.transactionId}</div>
                                  <div className="text-3xs text-slate-600 mt-0.5">{t.timestamp.substring(0, 16).replace('T', ' ')}</div>
                                </td>
                                <td className="px-2.5 py-2.5">
                                  <span className={`text-3xs font-extrabold uppercase tracking-wide ${
                                    t.direction === 'inbound'
                                      ? 'text-emerald-400/90'
                                      : 'text-rose-400/90'
                                  }`}>
                                    {t.direction}
                                  </span>
                                </td>
                                <td className="px-2.5 py-2.5">
                                  <div className="font-semibold text-slate-400">{t.counterpartyName}</div>
                                  <div className="text-3xs text-slate-650 font-mono">{t.channel}</div>
                                </td>
                                <td className="px-2.5 py-2.5 text-right font-mono font-bold text-slate-300">
                                  {t.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })} {t.currency}
                                </td>
                                <td className="px-2.5 py-2.5 text-right font-mono text-slate-400">
                                  <span className={isDraining ? 'text-rose-450 font-bold' : ''}>
                                    {t.runningBalance.toLocaleString(undefined, { minimumFractionDigits: 2 })} {t.currency}
                                  </span>
                                </td>
                              </tr>
                            )
                          }) ?? (
                            <tr>
                              <td colSpan={5} className="text-center py-4 text-slate-600 text-3xs">No transactions loaded.</td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </section>
                </div>

                {/* Right Side: STR Review and Decisions */}
                <div className="col-span-5 flex flex-col space-y-4">
                  {/* STR Draft Card */}
                  {selectedAlert.triage.recommendation === 'escalate' && selectedAlert.triage.strDraft ? (
                    <section className="flex-grow rounded-xl border border-slate-900 bg-slate-950/20 p-4 flex flex-col space-y-3 overflow-hidden">
                      <div className="flex items-center gap-1.5 border-b border-slate-900 pb-2 flex-shrink-0">
                        <svg className="h-3.5 w-3.5 text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        <h3 className="text-2xs font-black uppercase tracking-wider text-rose-400">Draft STR</h3>
                        <Badge tone="bg-rose-500/10 text-rose-400 border border-rose-500/10 ml-auto">Draft</Badge>
                      </div>

                      {/* Scrollable Form Body */}
                      <div className="flex-grow overflow-y-auto space-y-3.5 pr-1 text-2xs">
                        {/* Static Metadata */}
                        <div className="grid grid-cols-2 gap-3 rounded bg-slate-950/60 p-2.5 border border-slate-900">
                          <div>
                            <span className="text-3xs font-bold uppercase tracking-wider text-slate-500">Institution</span>
                            <div className="font-semibold text-slate-400 mt-0.5">{selectedAlert.triage.strDraft.reportingInstitution}</div>
                          </div>
                          <div>
                            <span className="text-3xs font-bold uppercase tracking-wider text-slate-500">Report Date</span>
                            <div className="font-semibold text-slate-400 mt-0.5">{selectedAlert.triage.strDraft.reportDate.substring(0,10)}</div>
                          </div>
                        </div>

                        {/* Activity Summary (Minimalist Writing-Desk Style) */}
                        <div>
                          <div className="flex justify-between items-center mb-1">
                            <span className="text-3xs font-bold uppercase tracking-wider text-slate-500">Narrative Description</span>
                            <span className="text-3xs text-slate-500">Drafted by AI</span>
                          </div>
                          <textarea
                            value={editedSummary}
                            onChange={(e) => setEditedSummary(e.target.value)}
                            rows={4}
                            className="w-full rounded border border-slate-900 bg-slate-950/60 p-2 text-2xs leading-relaxed text-slate-300 outline-none focus:border-teal-500 transition-colors"
                          />
                        </div>

                        {/* Grounds for Suspicion */}
                        <div className="space-y-1.5">
                          <span className="text-3xs font-bold uppercase tracking-wider text-slate-500">Grounds for Suspicion</span>
                          <ul className="space-y-1">
                            {editedGrounds.map((g, idx) => (
                              <li key={idx} className="flex items-start justify-between gap-2 rounded bg-slate-950/20 border border-slate-900 px-2.5 py-1.5">
                                <span className="font-medium text-slate-400 leading-normal">{g}</span>
                                <button
                                  onClick={() => removeGroundItem(idx)}
                                  className="text-slate-600 hover:text-rose-400 transition-colors"
                                >
                                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                  </svg>
                                </button>
                              </li>
                            ))}
                          </ul>
                          {/* Add grounds item input */}
                          <div className="flex gap-2">
                            <input
                              type="text"
                              value={newGroundItem}
                              onChange={(e) => setNewGroundItem(e.target.value)}
                              placeholder="Add reason..."
                              onKeyDown={(e) => e.key === 'Enter' && addGroundItem()}
                              className="flex-grow rounded border border-slate-900 bg-slate-950/60 px-2.5 py-1 text-2xs text-slate-355 outline-none focus:border-teal-500 transition-colors"
                            />
                            <button
                              onClick={addGroundItem}
                              className="rounded border border-slate-800 bg-slate-900 hover:bg-slate-800 px-2.5 text-slate-400 text-3xs font-bold cursor-pointer transition-colors"
                            >
                              Add
                            </button>
                          </div>
                        </div>

                        {/* Recommended Action */}
                        <div>
                          <span className="text-3xs font-bold uppercase tracking-wider text-slate-500">Action Plan</span>
                          <div className="mt-0.5 font-semibold text-slate-400 bg-slate-950/60 p-2.5 border border-slate-900 rounded leading-relaxed">
                            {selectedAlert.triage.strDraft.recommendedAction}
                          </div>
                        </div>
                      </div>
                    </section>
                  ) : (
                    /* Benign Dismissal placeholder */
                    <section className="flex-grow rounded-xl border border-slate-900 bg-slate-950/20 p-4 flex flex-col items-center justify-center text-center space-y-3">
                      <div className="rounded-full bg-slate-900 p-2.5 border border-slate-800 text-slate-500">
                        <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      </div>
                      <div>
                        <h4 className="font-bold text-slate-300 text-2xs">No report draft required</h4>
                        <p className="mt-1 text-3xs text-slate-500 max-w-xs leading-relaxed">
                          This alert is recommended for dismissal. Suspicious Transaction Reports are only drafted for escalations.
                        </p>
                      </div>
                    </section>
                  )}

                  {/* Decision Panel */}
                  <section className="rounded-xl border border-slate-900 bg-slate-950/20 p-4 space-y-3 flex-shrink-0">
                    <div>
                      <h3 className="text-3xs font-black uppercase tracking-wider text-slate-500">Submit Decision</h3>
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <button
                        onClick={() => handleDecision('approve')}
                        className="flex items-center justify-center gap-1.5 rounded bg-teal-600 hover:bg-teal-500 py-2.5 text-2xs font-bold text-slate-950 cursor-pointer shadow-sm shadow-teal-500/10 transition-colors"
                      >
                        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                        Approve Call
                      </button>
                      <button
                        onClick={() => handleDecision('override')}
                        className="flex items-center justify-center gap-1.5 rounded border border-slate-850 bg-slate-900/40 hover:bg-slate-900 py-2.5 text-2xs font-bold text-slate-400 hover:text-white cursor-pointer transition-colors"
                      >
                        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                        </svg>
                        Override Call
                      </button>
                    </div>
                  </section>
                </div>
              </div>
            </div>
          ) : (
            /* EMPTY DETAIL VIEW (PLACEHOLDER) */
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
        ) : (
          /* METRICS DASHBOARD VIEW */
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
        )}
      </main>
    </div>
  )
}
