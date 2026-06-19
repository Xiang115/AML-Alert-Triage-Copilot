import { useEffect, useState } from 'react'
import type { AlertStatus } from './types'
import { useAlerts } from './hooks/useAlerts'
import { useAlertDetail } from './hooks/useAlertDetail'
import { useMetrics } from './hooks/useMetrics'
import { BrandHeader } from './components/BrandHeader'
import { TabNav } from './components/TabNav'
import type { Tab } from './components/TabNav'
import { AlertQueue } from './components/AlertQueue'
import { MetricsSnapshot } from './components/MetricsSnapshot'
import { AlertDetail } from './components/AlertDetail'
import { EmptyState } from './components/EmptyState'
import { MetricsDashboard } from './components/MetricsDashboard'

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('queue')
  const [filterStatus, setFilterStatus] = useState<AlertStatus | 'all'>('all')
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null)

  const { alerts, loading: loadingList, reload: reloadList } = useAlerts(filterStatus)
  const { alert: selectedAlert, loading: loadingDetail, setAlert } = useAlertDetail(selectedAlertId)
  const metrics = useMetrics(activeTab)

  // Drop the selection if it falls out of the active filter (e.g. after a decision
  // re-filters the queue). Reacting to the fetched list is the point here.
  useEffect(() => {
    if (selectedAlertId && !alerts.find((a) => a.alertId === selectedAlertId)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSelectedAlertId(null)
    }
  }, [alerts, selectedAlertId])

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-950 font-sans text-slate-200 antialiased">
      {/* SIDEBAR */}
      <aside className="flex w-80 flex-col border-r border-slate-900 bg-slate-950/60 backdrop-blur-xl">
        <BrandHeader />
        <TabNav activeTab={activeTab} onTabChange={setActiveTab} />

        {activeTab === 'queue' ? (
          <AlertQueue
            alerts={alerts}
            loading={loadingList}
            filterStatus={filterStatus}
            onFilterChange={setFilterStatus}
            selectedAlertId={selectedAlertId}
            onSelect={setSelectedAlertId}
          />
        ) : (
          <MetricsSnapshot />
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
            <AlertDetail key={selectedAlert.alertId} alert={selectedAlert} setAlert={setAlert} onReloadList={reloadList} />
          ) : (
            <EmptyState />
          )
        ) : (
          <MetricsDashboard metrics={metrics} />
        )}
      </main>
    </div>
  )
}
