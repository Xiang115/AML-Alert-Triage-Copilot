import { useEffect, useState } from 'react'
import type { AlertStatus } from './types'
import { useAlerts } from './hooks/useAlerts'
import { useAlertDetail } from './hooks/useAlertDetail'
import { useMetrics } from './hooks/useMetrics'
import { useBriefing } from './hooks/useBriefing'
import { BrandHeader } from './components/BrandHeader'
import { TabNav } from './components/TabNav'
import type { Tab } from './components/TabNav'
import { AlertQueue } from './components/AlertQueue'
import type { Lane } from './components/ShiftBriefing'
import { MetricsSnapshot } from './components/MetricsSnapshot'
import { AlertDetail } from './components/AlertDetail'
import { EmptyState } from './components/EmptyState'
import { MetricsDashboard } from './components/MetricsDashboard'
import { AuditView } from './components/AuditView'

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('queue')
  const [filterStatus, setFilterStatus] = useState<AlertStatus | 'all'>('all')
  // The Queue Agent's lane (ADR-0010): default to the needsReview inbox — the worklist
  // the agent left for the human after auto-clearing the benign noise.
  const [laneFilter, setLaneFilter] = useState<Lane>('needsReview')
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null)

  const { alerts, loading: loadingList, reload: reloadList } = useAlerts(filterStatus)
  const { alert: selectedAlert, loading: loadingDetail, setAlert } = useAlertDetail(selectedAlertId)
  const metrics = useMetrics(activeTab)
  const briefing = useBriefing()

  // Apply the routing-lane filter on top of the status-fetched queue (a null routing —
  // a pre-Queue-Agent record — counts as needsReview, the safe lane).
  const visibleAlerts =
    laneFilter === 'all' ? alerts : alerts.filter((a) => (a.routing ?? 'needsReview') === laneFilter)

  // Drop the selection if it falls out of the active filter (e.g. after a decision
  // re-filters the queue). Reacting to the fetched list is the point here.
  useEffect(() => {
    if (selectedAlertId && !alerts.find((a) => a.alertId === selectedAlertId)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSelectedAlertId(null)
    }
  }, [alerts, selectedAlertId])

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-paper text-ink">
      {/* SIDEBAR */}
      <aside className="flex w-80 flex-col border-r border-line bg-surface">
        <BrandHeader />
        <TabNav activeTab={activeTab} onTabChange={setActiveTab} />

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
            <AlertDetail key={selectedAlert.alertId} alert={selectedAlert} setAlert={setAlert} onReloadList={reloadList} />
          ) : (
            <EmptyState />
          )
        ) : activeTab === 'metrics' ? (
          <MetricsDashboard metrics={metrics} />
        ) : (
          <AuditView />
        )}
      </main>
    </div>
  )
}
