import { useEffect, useState } from 'react'
import { exportGoamlStr, getAudit, getCaseHandoff, getCopilotRunLedger, getCopilotRuns, getDecisionTrace, postDecision, submitGoamlStr } from '../api'
import { finalDispositionFor } from '../decision'
import type { Alert, AuditEntry, CaseHandoff, CopilotRunLedger, CopilotRunSummary, DecisionTrace, GovernanceThresholds, STRDraft, SubmissionAck } from '../types'
import { useReasoningPlayback } from '../hooks/useReasoningPlayback'
import { useReasoningStream } from '../hooks/useReasoningStream'
import { TriageCard } from './TriageCard'
import { VerifierPanel } from './VerifierPanel'
import { DebatePanel } from './DebatePanel'
import { NetworkReveal } from './NetworkPanel'
import { SuppressionPanel } from './SuppressionPanel'
import { CoachingPanel } from './CoachingPanel'
import { ScreeningPanel } from './ScreeningPanel'
import { MoneyFlowTimeline } from './MoneyFlowTimeline'
import { TransactionTable } from './TransactionTable'
import { EvidenceRegister } from './EvidenceRegister'
import { AccountActivityProfile } from './AccountActivityProfile'
import { FilingSlaClock } from './FilingSlaClock'
import { StrEditor } from './StrEditor'
import { DismissalRecord } from './DismissalRecord'
import { DecisionPanel } from './DecisionPanel'
import { CaseHandoffCard } from './CaseHandoffCard'
import { DecisionTraceCard } from './DecisionTraceCard'
import { CopilotLedgerCard } from './CopilotLedgerCard'
import { CollapsibleSection } from './ui/CollapsibleSection'

interface AlertDetailProps {
  alert: Alert
  setAlert: (alert: Alert) => void
  onReloadList: () => void
  // Operating-point thresholds (ADR-0020) for the TriageCard confidence markers; null until loaded.
  thresholds: GovernanceThresholds | null
}

export function AlertDetail({ alert, setAlert, onReloadList, thresholds }: AlertDetailProps) {
  // Seeded from the draft; App remounts this component per alert (key=alertId),
  // so opening a different alert resets these without an effect.
  const [editedSummary, setEditedSummary] = useState(alert.triage.strDraft?.activitySummary ?? '')
  const [editedGrounds, setEditedGrounds] = useState<string[]>(
    alert.triage.strDraft ? [...alert.triage.strDraft.groundsForSuspicion] : [],
  )
  const [ack, setAck] = useState<SubmissionAck | null>(null)
  const [auditEntries, setAuditEntries] = useState<AuditEntry[]>([])
  const [caseHandoff, setCaseHandoff] = useState<CaseHandoff | null>(null)
  const [decisionTrace, setDecisionTrace] = useState<DecisionTrace | null>(null)
  const [copilotRuns, setCopilotRuns] = useState<CopilotRunSummary[]>([])
  const [copilotLedger, setCopilotLedger] = useState<CopilotRunLedger | null>(null)
  // The transaction the Evidence Register asked the ledger to scroll to and highlight (ADR-0013).
  const [focusedTxnId, setFocusedTxnId] = useState<string | null>(null)

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

  useEffect(() => {
    let cancelled = false
    getAudit()
      .then((entries) => {
        if (!cancelled) setAuditEntries(entries.filter((e) => e.alertId === alert.alertId))
      })
      .catch((err) => {
        console.warn('Audit replay unavailable:', err)
        if (!cancelled) setAuditEntries([])
      })
    return () => {
      cancelled = true
    }
  }, [alert.alertId])

  useEffect(() => {
    let cancelled = false
    Promise.all([getCaseHandoff(alert.alertId), getDecisionTrace(alert.alertId)])
      .then(([handoff, trace]) => {
        if (!cancelled) {
          setCaseHandoff(handoff)
          setDecisionTrace(trace)
        }
      })
      .catch((err) => {
        console.warn('Case handoff or decision trace unavailable:', err)
        if (!cancelled) {
          setCaseHandoff(null)
          setDecisionTrace(null)
        }
      })
    return () => {
      cancelled = true
    }
  }, [alert.alertId, alert.status, alert.triage.strDraft])

  useEffect(() => {
    let cancelled = false
    getCopilotRuns(alert.alertId)
      .then(async (runList) => {
        if (cancelled) return
        setCopilotRuns(runList.runs)
        const runId = runList.runs[0]?.runId ?? 'precomputed-current'
        const ledger = await getCopilotRunLedger(alert.alertId, runId)
        if (!cancelled) setCopilotLedger(ledger)
      })
      .catch((err) => {
        console.warn('Copilot run ledger unavailable:', err)
        if (!cancelled) {
          setCopilotRuns([])
          setCopilotLedger(null)
        }
      })
    return () => {
      cancelled = true
    }
  }, [alert.alertId])

  const applyFreshTriage = (triage: Alert['triage']) => {
    setAlert({ ...alert, triage })
    if (triage.strDraft) {
      setEditedSummary(triage.strDraft.activitySummary)
      setEditedGrounds([...triage.strDraft.groundsForSuspicion])
    }
    getCopilotRuns(alert.alertId)
      .then(async (runList) => {
        setCopilotRuns(runList.runs)
        const runId = runList.runs[0]?.runId ?? 'precomputed-current'
        setCopilotLedger(await getCopilotRunLedger(alert.alertId, runId))
      })
      .catch((err) => console.warn('Copilot run ledger unavailable:', err))
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
      getAudit()
        .then((entries) => setAuditEntries(entries.filter((e) => e.alertId === alert.alertId)))
        .catch((err) => console.warn('Audit replay unavailable:', err))
      getCaseHandoff(alert.alertId)
        .then(setCaseHandoff)
        .catch((err) => console.warn('Case handoff unavailable:', err))
      getDecisionTrace(alert.alertId)
        .then(setDecisionTrace)
        .catch((err) => console.warn('Decision trace unavailable:', err))
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
      getAudit()
        .then((entries) => setAuditEntries(entries.filter((e) => e.alertId === alert.alertId)))
        .catch((err) => console.warn('Audit replay unavailable:', err))
      getCaseHandoff(alert.alertId)
        .then(setCaseHandoff)
        .catch((err) => console.warn('Case handoff unavailable:', err))
      getDecisionTrace(alert.alertId)
        .then(setDecisionTrace)
        .catch((err) => console.warn('Decision trace unavailable:', err))
    } catch (err) {
      console.error(err)
      window.alert('goAML export failed. The export hits the live backend — ensure it is running and the alert was approved to escalate.')
    }
  }

  const showStrEditor = alert.triage.recommendation === 'escalate' && alert.triage.strDraft
  // The cited legs, as full transactions, so the STR's Reported-transactions table shows
  // direction/channel and matches the ledger + goAML XML (ADR-0017).
  const citedTransactions =
    alert.transactions?.filter((t) => alert.triage.citedTransactionIds.includes(t.transactionId)) ?? []
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
            borderline={alert.borderlineDismiss ?? false}
            thresholds={thresholds}
          />
          <SuppressionPanel data={alert.triage.suppression} routing={alert.routing} />
          <VerifierPanel verifier={alert.triage.verifier} />
          {alert.triage.debate && <DebatePanel debate={alert.triage.debate} />}
          {/* Related-account reveal (ADR-0009/0015): the hidden mule the network re-surfaces.
              Renders only for the crafted hero alert; a no-op for every other alert. */}
          <NetworkReveal alertId={alert.alertId} />
          <CoachingPanel triage={alert.triage} />
          <ScreeningPanel data={alert.triage.screening} />
          <MoneyFlowTimeline
            transactions={alert.transactions}
            citedTransactionIds={alert.triage.citedTransactionIds}
          />
          <TransactionTable
            transactions={alert.transactions}
            citedTransactionIds={alert.triage.citedTransactionIds}
            focusedTransactionId={focusedTxnId}
          />
          {alert.triage.strDraft && (
            <EvidenceRegister
              triage={alert.triage}
              strDraft={alert.triage.strDraft}
              onFocusTransaction={setFocusedTxnId}
            />
          )}
        </div>

        {/* Right: the working surface (activity, the record, the decision) up top; the
            governance/provenance cards collapsed below it so acting on the alert doesn't mean
            scrolling past them. */}
        <div className="col-span-5 flex flex-col space-y-5">
          {/* QA-sample notice (ADR-0019): this auto-cleared alert was risk-weighted-sampled for a
              human spot-check — the control for the measured auto-clear leakage. */}
          {alert.qaSampled && (
            <section className="shrink-0 rounded-lg border border-flag bg-flag-soft/60 p-4">
              <h3 className="text-[14px] font-semibold text-flag">QA sample — auto-cleared, pulled for spot-check</h3>
              <p className="mt-1.5 text-[13px] leading-relaxed text-ink-soft">
                The Queue Agent auto-cleared this alert; it was risk-weighted-sampled (least-sure clears
                first) for human QA — the control for the measured auto-clear leakage. Confirm the clear
                (<span className="font-medium text-ink">Approve</span>) or catch a missed report
                (<span className="font-medium text-ink">Override</span>); either way it is recorded to the
                audit trail.
              </p>
            </section>
          )}

          {/* Ledger-derived Account Activity Profile (ADR-0016): fills the rail on every alert,
              including dismiss, with real money-movement insight (never fabricated KYC). */}
          {alert.activityProfile && (
            <AccountActivityProfile
              profile={alert.activityProfile}
              screening={alert.triage.screening}
            />
          )}

          {showStrEditor && alert.triage.strDraft ? (
            <StrEditor
              strDraft={alert.triage.strDraft}
              citedTransactions={citedTransactions}
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
            /* Dismissal Record (ADR-0018): the read-only closure counterpart to the STR — why the
               alert was cleared, assembled from real triage data. Fills the slot the STR editor
               occupies on escalate. */
            <DismissalRecord triage={alert.triage} subject={alert.account} status={alert.status} />
          )}

          {/* Beat 1 (ADR-0011): when the two agents debated to a standstill (`holds`), the human
              casts the deciding vote. The DecisionPanel below is that vote — this frames it. */}
          {alert.triage.debate?.reverdict.outcome === 'holds' && (
            <section className="shrink-0 rounded-lg border border-flag bg-flag-soft/60 p-5">
              <h3 className="text-[14px] font-semibold text-flag">Agents deadlocked — you decide</h3>
              <p className="mt-1.5 text-[13px] leading-relaxed text-ink-soft">
                The triage agent and the verifier debated this call and could not agree. As the reviewing
                analyst you cast the deciding vote: <span className="font-medium text-ink">Approve</span> keeps
                the AI&rsquo;s <span className="font-medium text-ink">{alert.triage.recommendation}</span>,{' '}
                <span className="font-medium text-ink">Override</span> flips it.
              </p>
            </section>
          )}

          {/* STR filing-SLA clock (ADR-0016): BNM next-working-day deadline in the action zone. */}
          {alert.filingSla && <FilingSlaClock sla={alert.filingSla} />}

          <DecisionPanel
            recommendation={alert.triage.recommendation}
            onApprove={(note) => handleDecision('approve', note)}
            onOverride={(note) => handleDecision('override', note)}
          />

          {/* Provenance & controls: the merged decision trace (routing rationale + deterministic
              gates + audit replay), the copilot run ledger, and the bank write-back packet. The
              defensibility story, tucked below the action so triage isn't buried under it. */}
          <CollapsibleSection
            title="Provenance & controls"
            subtitle="Decision trace, copilot run ledger, and bank handoff packet."
            defaultOpen
          >
            <DecisionTraceCard
              trace={decisionTrace}
              alert={alert}
              thresholds={thresholds}
              auditEntries={auditEntries}
            />
            <CopilotLedgerCard runs={copilotRuns} ledger={copilotLedger} />
            <CaseHandoffCard handoff={caseHandoff} />
          </CollapsibleSection>
        </div>
      </div>
    </div>
  )
}
