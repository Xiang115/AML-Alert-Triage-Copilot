import { useEffect, useState } from 'react'
import type { AlertStatus } from './types'
import { useAlerts } from './hooks/useAlerts'
import { useAlertDetail } from './hooks/useAlertDetail'
import { useMetrics } from './hooks/useMetrics'
import { useBriefing } from './hooks/useBriefing'
import { useGovernance } from './hooks/useGovernance'
import { useValidationDossier } from './hooks/useValidationDossier'
import { useIntegrationContract } from './hooks/useIntegrationContract'
import { useAccessControlPosture } from './hooks/useAccessControlPosture'
import { useGovernanceChangeRequests } from './hooks/useGovernanceChangeRequests'
import { useQAOutcomes } from './hooks/useQAOutcomes'
import { useTechnicalArchitecture } from './hooks/useTechnicalArchitecture'
import { useReadinessSummary } from './hooks/useReadinessSummary'
import { usePilotAdoptionPlan } from './hooks/usePilotAdoptionPlan'
import { BrandHeader } from './components/BrandHeader'
import { TabNav } from './components/TabNav'
import type { Tab } from './components/TabNav'
import { AlertQueue } from './components/AlertQueue'
import type { Lane } from './components/ShiftBriefing'
import { MetricsSnapshot } from './components/MetricsSnapshot'
import { AlertDetail } from './components/AlertDetail'
import { EmptyState } from './components/EmptyState'
import { MetricsDashboard } from './components/MetricsDashboard'
import { Governance } from './components/Governance'
import { AuditView } from './components/AuditView'
import { LearnedPatternsView } from './components/LearnedPatternsView'

interface RouteState {
  tab: Tab
  alertId?: string | null
}

// Hash routing (Slice A): deep-linkable tabs + selected alert, so a refresh or a shared link
// restores exactly where you were (e.g. #/alerts/SD-00013, #/learned-patterns, #/settings).
function parseHash(hash: string): RouteState {
  const route = hash.startsWith('#') ? hash.slice(1) : hash

  if (route.startsWith('/alerts/')) {
    const alertId = decodeURIComponent(route.slice('/alerts/'.length))
    return { tab: 'queue', alertId: alertId || null }
  }
  if (route === '/learned-patterns') return { tab: 'learnedPatterns' }
  if (route === '/metrics') return { tab: 'metrics' }
  if (route === '/governance') return { tab: 'governance' }
  if (route === '/audit') return { tab: 'audit' }
  return { tab: 'queue', alertId: null }
}

function hashForState(tab: Tab, selectedAlertId: string | null) {
  if (tab === 'queue') {
    return selectedAlertId ? `#/alerts/${encodeURIComponent(selectedAlertId)}` : '#/queue'
  }
  if (tab === 'learnedPatterns') return '#/learned-patterns'
  if (tab === 'metrics') return '#/metrics'
  if (tab === 'governance') return '#/governance'
  return '#/audit'
}

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>(() => parseHash(window.location.hash).tab)
  const [filterStatus, setFilterStatus] = useState<AlertStatus | 'all'>('all')
  // The Queue Agent's lane (ADR-0010): default to the full population so auto-clears stay
  // visible beside the human worklist instead of being hidden behind Governance-only counts.
  const [laneFilter, setLaneFilter] = useState<Lane>('all')
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(
    () => parseHash(window.location.hash).alertId ?? null,
  )

  const { alerts, loading: loadingList, reload: reloadList } = useAlerts('all')
  const { alert: selectedAlert, loading: loadingDetail, setAlert } = useAlertDetail(selectedAlertId)
  const metrics = useMetrics(activeTab)
  const { briefing, reload: reloadBriefing } = useBriefing()
  const governance = useGovernance(activeTab)
  const validationDossier = useValidationDossier(activeTab)
  const integrationContract = useIntegrationContract(activeTab)
  const accessControl = useAccessControlPosture(activeTab)
  const governanceChangeControl = useGovernanceChangeRequests(activeTab)
  const qaOutcomes = useQAOutcomes(activeTab)
  const technicalArchitecture = useTechnicalArchitecture(activeTab)
  const readinessSummary = useReadinessSummary(activeTab)
  const pilotAdoptionPlan = usePilotAdoptionPlan(activeTab)

  // Apply the routing-lane filter on top of the status-fetched queue (a null routing —
  // a pre-Queue-Agent record — counts as needsReview, the safe lane). The qaSample lane
  // (ADR-0019) is the serve-time risk-weighted slice of the auto-cleared alerts.
  const statusFilteredAlerts =
    filterStatus === 'all' ? alerts : alerts.filter((a) => a.status === filterStatus)
  const visibleAlerts =
    laneFilter === 'all'
      ? statusFilteredAlerts
      : laneFilter === 'qaSample'
        ? statusFilteredAlerts.filter((a) => a.qaSampled)
        : statusFilteredAlerts.filter((a) => (a.routing ?? 'needsReview') === laneFilter)
  const qaSampleCount = alerts.filter((a) => a.qaSampled).length
  const learningImpactCount = alerts.filter(
    (a) => a.routing === 'autoCleared' && a.triage.suppression?.status === 'suppressed',
  ).length

  // Drop the selection if it falls out of the active filter (e.g. after a decision
  // re-filters the queue). Reacting to the fetched list is the point here.
  useEffect(() => {
    if (selectedAlertId && !alerts.find((a) => a.alertId === selectedAlertId)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSelectedAlertId(null)
    }
  }, [alerts, selectedAlertId])

  // Keep tab/selection in sync with the URL hash both ways (Slice A): react to back/forward
  // and shared links, and write the current state back without adding history entries.
  useEffect(() => {
    const syncFromHash = () => {
      const route = parseHash(window.location.hash)
      setActiveTab(route.tab)
      if ('alertId' in route) {
        setSelectedAlertId(route.alertId ?? null)
      }
    }
    window.addEventListener('hashchange', syncFromHash)
    return () => window.removeEventListener('hashchange', syncFromHash)
  }, [])

  useEffect(() => {
    const nextHash = hashForState(activeTab, selectedAlertId)
    if (window.location.hash === nextHash) return
    window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}${nextHash}`)
  }, [activeTab, selectedAlertId])

  const reloadQueueState = () => {
    reloadList()
    reloadBriefing()
  }

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-paper text-ink">
      {/* TOP BAR: brand (aligned over the sidebar) + full-width tabs */}
      <div className="flex shrink-0 items-center border-b border-line bg-surface">
        <BrandHeader />
        <TabNav activeTab={activeTab} onTabChange={setActiveTab} />
      </div>

      {/* BODY: sidebar + main content */}
      <div className="flex grow overflow-hidden">
        {/* SIDEBAR */}
        <aside className="flex w-80 shrink-0 flex-col overflow-hidden border-r border-line bg-surface">
          {activeTab === 'queue' ? (
            <AlertQueue
              alerts={visibleAlerts}
              loading={loadingList}
              filterStatus={filterStatus}
              onFilterChange={setFilterStatus}
              selectedAlertId={selectedAlertId}
              onSelect={setSelectedAlertId}
              briefing={briefing}
              lane={laneFilter}
              onLaneChange={setLaneFilter}
              qaSampleCount={qaSampleCount}
              learningImpactCount={learningImpactCount}
              metrics={metrics}
              thresholds={governance?.thresholds ?? null}
            />
          ) : (
            <MetricsSnapshot metrics={metrics} />
          )}
        </aside>

        {/* MAIN CONTENT AREA */}
        <main className="flex grow flex-col overflow-hidden">
        {activeTab === 'queue' ? (
          loadingDetail ? (
            <div className="flex h-full flex-col items-center justify-center gap-2 text-ink-faint">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-line-strong border-t-ink"></div>
              <span className="text-[13px]">Loading alert…</span>
            </div>
          ) : selectedAlert ? (
            <AlertDetail key={selectedAlert.alertId} alert={selectedAlert} setAlert={setAlert} onReloadList={reloadQueueState} thresholds={governance?.thresholds ?? null} />
          ) : (
            <EmptyState />
          )
        ) : activeTab === 'learnedPatterns' ? (
          <LearnedPatternsView alerts={alerts} />
        ) : activeTab === 'metrics' ? (
          <MetricsDashboard metrics={metrics} />
        ) : activeTab === 'governance' ? (
          <Governance data={governance} validationDossier={validationDossier} integrationContract={integrationContract} accessControl={accessControl} governanceChangeControl={governanceChangeControl} qaOutcomes={qaOutcomes} technicalArchitecture={technicalArchitecture} readinessSummary={readinessSummary} pilotAdoptionPlan={pilotAdoptionPlan} />
        ) : (
          <AuditView />
        )}
        </main>
      </div>
    </div>
  )
}
