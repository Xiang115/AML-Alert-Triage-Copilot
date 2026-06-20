import { useState } from 'react'
import { postDecision, postTriage } from '../api'
import { finalDispositionFor } from '../decision'
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
    const finalDisposition = finalDispositionFor(alert.triage.recommendation, action)

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
    <div className="flex h-full flex-col overflow-hidden">
      {/* Alert header */}
      <header className="flex shrink-0 items-start justify-between gap-4 border-b border-line bg-surface px-6 py-4">
        <div>
          <div className="flex items-baseline gap-2.5">
            <h2 className="text-xl font-semibold tracking-tight text-ink">{alert.account.holderName}</h2>
            <span className="font-mono text-[12px] text-ink-faint">{alert.alertId}</span>
          </div>
          <div className="mt-1 font-mono text-[12px] text-ink-soft">
            {alert.account.accountId} · {alert.account.accountType} · opened {alert.account.openedAt.substring(0, 10)}
          </div>
          <p className="mt-2 max-w-2xl text-[13px] leading-relaxed text-ink-soft">{alert.trigger}</p>
        </div>

        <div className="shrink-0 text-right">
          <div className="label">Risk score</div>
          <div className="mt-0.5 font-mono text-2xl font-semibold tabular-nums text-ink">{alert.riskScore}</div>
        </div>
      </header>

      {/* Body */}
      <div className="grid grow grid-cols-12 gap-5 overflow-y-auto bg-paper p-5">
        {/* Left: triage, verifier, transactions */}
        <div className="col-span-7 space-y-5">
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

        {/* Right: STR draft + decision */}
        <div className="col-span-5 flex flex-col space-y-5">
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
            <section className="flex grow flex-col items-center justify-center rounded-lg border border-line bg-surface p-8 text-center">
              <h4 className="text-[14px] font-semibold text-ink">No report required</h4>
              <p className="mt-1.5 max-w-xs text-[13px] leading-relaxed text-ink-soft">
                This alert is recommended for dismissal. A Suspicious Transaction Report is drafted only when an alert is escalated.
              </p>
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
