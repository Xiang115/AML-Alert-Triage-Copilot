import { useState } from 'react'
import { postDecision, postTriage } from '../api'
import type { Alert, STRDraft } from '../types'
import { TriageCard } from './TriageCard'
import { VerifierPanel } from './VerifierPanel'
import { TransactionTable } from './TransactionTable'
import { StrEditor } from './StrEditor'
import { DecisionPanel } from './DecisionPanel'

const LIVE_TRIAGE_STEPS = [
  'Initializing DeepSeek LLM client...',
  'Retrieving Typology Cards from KB...',
  'Analyzing transactions and calculating running balance...',
  'Triage Agent: Assessing Escalate/Dismiss recommendation...',
  'Verifier Agent: Challenging triage call against Distinguishing Test...',
  'STR Drafter: Generating structured Suspicious Transaction Report...',
  'Complete!',
]

interface AlertDetailProps {
  alert: Alert
  setAlert: (alert: Alert) => void
  onReloadList: () => void
}

export function AlertDetail({ alert, setAlert, onReloadList }: AlertDetailProps) {
  const [isTriaging, setIsTriaging] = useState(false)
  const [triageStep, setTriageStep] = useState('')
  // Seeded from the draft; App remounts this component per alert (key=alertId),
  // so opening a different alert resets these without an effect.
  const [editedSummary, setEditedSummary] = useState(alert.triage.strDraft?.activitySummary ?? '')
  const [editedGrounds, setEditedGrounds] = useState<string[]>(
    alert.triage.strDraft ? [...alert.triage.strDraft.groundsForSuspicion] : [],
  )

  // Execute Live Triage Endpoint (for Q&A WOW factor)
  const handleLiveTriage = async () => {
    setIsTriaging(true)
    for (const step of LIVE_TRIAGE_STEPS) {
      setTriageStep(step)
      await new Promise((resolve) => setTimeout(resolve, 350))
    }

    try {
      const freshResult = await postTriage(alert.alertId)
      setAlert({ ...alert, triage: freshResult })
      if (freshResult.strDraft) {
        setEditedSummary(freshResult.strDraft.activitySummary)
        setEditedGrounds([...freshResult.strDraft.groundsForSuspicion])
      }
      onReloadList()
    } catch (err) {
      console.error(err)
      window.alert('Triage run failed. Check backend console logs.')
    } finally {
      setIsTriaging(false)
      setTriageStep('')
    }
  }

  // Handle analyst decision (Approve / Override)
  const handleDecision = async (action: 'approve' | 'override') => {
    const originalRecommendation = alert.triage.recommendation
    const finalDisposition =
      action === 'approve'
        ? originalRecommendation
        : originalRecommendation === 'escalate'
        ? 'dismiss'
        : 'escalate'

    let updatedStr: STRDraft | null = null
    if (finalDisposition === 'escalate' && alert.triage.strDraft) {
      updatedStr = {
        ...alert.triage.strDraft,
        activitySummary: editedSummary,
        groundsForSuspicion: editedGrounds,
      }
    }

    try {
      const updatedAlert = await postDecision(alert.alertId, action, finalDisposition, updatedStr)
      setAlert(updatedAlert)
      onReloadList()
    } catch (err) {
      console.error(err)
      window.alert('Failed to save decision.')
    }
  }

  const showStrEditor = alert.triage.recommendation === 'escalate' && alert.triage.strDraft

  return (
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
              <h2 className="text-sm font-bold text-white">{alert.account.holderName}</h2>
              <span className="font-mono text-2xs text-slate-500">{alert.alertId}</span>
            </div>
            <div className="mt-0.5 flex items-center gap-2 text-3xs text-slate-500 font-semibold uppercase tracking-wider">
              <span>Acc: <span className="font-bold text-slate-300">{alert.account.accountId}</span></span>
              <span className="h-0.5 w-0.5 rounded-full bg-slate-800"></span>
              <span>{alert.account.accountType}</span>
              <span className="h-0.5 w-0.5 rounded-full bg-slate-800"></span>
              <span>Opened {alert.account.openedAt.substring(0, 10)}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-right">
            <span className="block text-3xs font-extrabold uppercase tracking-widest text-slate-600">Trigger Event</span>
            <span className="text-2xs font-semibold text-teal-400/90 mt-0.5">{alert.trigger}</span>
          </div>
          <span className="h-4 w-px bg-slate-900"></span>
          <div className="text-center rounded-lg bg-slate-900/60 border border-slate-800 px-3 py-1">
            <span className="block text-3xs font-extrabold uppercase tracking-widest text-slate-500">Risk</span>
            <span className="text-xs font-black text-rose-400">{alert.riskScore}</span>
          </div>
        </div>
      </div>

      {/* Scrollable Detail Body */}
      <div className="flex-grow overflow-y-auto p-4 grid grid-cols-12 gap-4">
        {/* Left Side: Triage, Verifier, and Transactions */}
        <div className="col-span-7 space-y-4">
          <TriageCard
            triage={alert.triage}
            isTriaging={isTriaging}
            triageStep={triageStep}
            onRunLive={handleLiveTriage}
          />
          <VerifierPanel verifier={alert.triage.verifier} />
          <TransactionTable
            transactions={alert.transactions}
            citedTransactionIds={alert.triage.citedTransactionIds}
          />
        </div>

        {/* Right Side: STR Review and Decisions */}
        <div className="col-span-5 flex flex-col space-y-4">
          {showStrEditor && alert.triage.strDraft ? (
            <StrEditor
              strDraft={alert.triage.strDraft}
              summary={editedSummary}
              onSummaryChange={setEditedSummary}
              grounds={editedGrounds}
              onAddGround={(text) => setEditedGrounds([...editedGrounds, text])}
              onRemoveGround={(idx) => setEditedGrounds(editedGrounds.filter((_, i) => i !== idx))}
            />
          ) : (
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

          <DecisionPanel
            onApprove={() => handleDecision('approve')}
            onOverride={() => handleDecision('override')}
          />
        </div>
      </div>
    </div>
  )
}
