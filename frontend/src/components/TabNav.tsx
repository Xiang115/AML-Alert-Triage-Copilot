export type Tab = 'queue' | 'learnedPatterns' | 'metrics' | 'governance' | 'audit'

interface TabNavProps {
  activeTab: Tab
  onTabChange: (tab: Tab) => void
}

const TABS: { id: Tab; label: string }[] = [
  { id: 'queue', label: 'Alert Queue' },
  { id: 'learnedPatterns', label: 'Learned Patterns' },
  { id: 'metrics', label: 'System Performance' },
  { id: 'governance', label: 'Governance' },
  { id: 'audit', label: 'Audit Trail' },
]

// Lives in the full-width top bar; scrolls horizontally only as a last resort on a very small screen.
export function TabNav({ activeTab, onTabChange }: TabNavProps) {
  return (
    <nav className="flex gap-6 overflow-x-auto px-5">
      {TABS.map((tab) => {
        const active = activeTab === tab.id
        return (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`shrink-0 whitespace-nowrap border-b-2 py-4 text-[13px] font-medium transition-colors ${
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
