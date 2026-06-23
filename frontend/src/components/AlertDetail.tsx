import { useState } from 'react'
import { exportGoamlStr, postDecision, submitGoamlStr } from '../api'
import { finalDispositionFor } from '../decision'
import type { Alert, STRDraft, SubmissionAck } from '../types'
import { useReasoningPlayback } from '../hooks/useReasoningPlayback'
import { useReasoningStream } from '../hooks/useReasoningStream'
import { TriageCard } from './TriageCard'
import { VerifierPanel } from './VerifierPanel'
import { TransactionTable } from './TransactionTable'
import { StrEditor } from './StrEditor'
import { DecisionPanel } from './DecisionPanel'

interface AlertDetailProps {
  alert: Alert
  setAlert: (alert: Alert) => void
  onReloadList: () => void
}

export function AlertDetail({ alert, setAlert, onReloadList }: AlertDetailProps) {
  // Seeded from the draft; App remounts this component per alert (key=alertId),
  // so opening a different alert resets these without an effect.
  const [editedSummary, setEditedSummary] = useState(alert.triage.strDraft?.activitySummary ?? '')
  const [editedGrounds, setEditedGrounds] = useState<string[]>(
    alert.triage.strDraft ? [...alert.triage.strDraft.groundsForSuspicion] : [],
  )
  const [ack, setAck] = useState<SubmissionAck | null>(null)

  // Two sources for the reasoning timeline: a precomputed replay (demo, no API) and the
  // live SSE stream (real pipeline). Both feed the same TriageCard; live takes precedence
  // while active. Both hooks reset on remount (App keys this component by alertId).
  const replay = useReasoningPlayback()
  const stream = useReasoningStream()
  const liveActive = stream.streaming || stream.events.length > 0
  const timeline = liveActive
    ? { events: stream.events, revealed: stream.events.length, playing: stream.streaming }
    : { events: replay.events, revealed: replay.revealed, playing: replay.playing }
  const busy = stream.streaming || replay.playing

  const applyFreshTriage = (triage: Alert['triage']) => {
    setAlert({ ...alert, triage })
    if (triage.strDraft) {
      setEditedSummary(triage.strDraft.activitySummary)
      setEditedGrounds([...triage.strDraft.groundsForSuspicion])
    }
    onReloadList()
  }

  // Live triage (Q&A): stream the real pipeline's reasoning step-by-step over SSE.
  const handleLiveTriage = () => {
    replay.reset()
    stream.start(alert.alertId, {
      onResult: applyFreshTriage,
      onError: (m) => console.warn('Live triage stream:', m),
    })
  }

  // Demo replay: reveal the precomputed reasoning without any backend call.
  const handleReplayReasoning = () => {
    stream.stop()
    replay.play(alert.triage)
  }

  // Handle analyst decision (Approve / Override)
  const handleDecision = async (action: 'approve' | 'override', note: string) => {
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
      const updatedAlert = await postDecision(alert.alertId, action, finalDisposition, updatedStr, note)
      setAck(null)  // a new decision supersedes any prior filing acknowledgement
      setAlert(updatedAlert)
      onReloadList()
    } catch (err) {
      console.error(err)
      window.alert('Failed to save decision.')
    }
  }

  // Export the regulator-ready goAML STR and file it: download the XML for the
  // analyst's records, then submit to goAML and surface the FIU acknowledgement.
  const handleExport = async () => {
    try {
      await exportGoamlStr(alert.alertId)
      setAck(await submitGoamlStr(alert.alertId))
    } catch (err) {
      console.error(err)
      window.alert('goAML export failed. The export hits the live backend — ensure it is running and the alert was approved to escalate.')
    }
  }

  const showStrEditor = alert.triage.recommendation === 'escalate' && alert.triage.strDraft
  // Mirrors the backend gate: a filed STR exists only after an escalate sign-off
  // (status leaves "pending" and the disposition kept the draft).
  const canExport = alert.status !== 'pending' && !!alert.triage.strDraft

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
            timeline={timeline}
            onRunLive={handleLiveTriage}
            onReplayReasoning={handleReplayReasoning}
            busy={busy}
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
              canExport={canExport}
              onExport={handleExport}
              ack={ack}
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
            onApprove={(note) => handleDecision('approve', note)}
            onOverride={(note) => handleDecision('override', note)}
          />
        </div>
      </div>
    </div>
  )
}
