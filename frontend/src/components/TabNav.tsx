export type Tab = 'queue' | 'metrics' | 'audit'

interface TabNavProps {
  activeTab: Tab
  onTabChange: (tab: Tab) => void
}

const TABS: { id: Tab; label: string }[] = [
  { id: 'queue', label: 'Alert Queue' },
  { id: 'metrics', label: 'System Performance' },
  { id: 'audit', label: 'Audit Trail' },
]

export function TabNav({ activeTab, onTabChange }: TabNavProps) {
  return (
    <nav className="flex gap-5 border-b border-line px-5">
      {TABS.map((tab) => {
        const active = activeTab === tab.id
        return (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`-mb-px border-b-2 py-3 text-[13px] font-medium transition-colors ${
              active
                ? 'border-ink text-ink'
                : 'border-transparent text-ink-faint hover:text-ink-soft'
            }`}
          >
            {tab.label}
          </button>
        )
      })}
    </nav>
  )
}
