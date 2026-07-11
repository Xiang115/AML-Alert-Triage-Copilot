export type Tab = 'queue' | 'learnedPatterns' | 'metrics' | 'governance' | 'audit'

interface TabNavProps {
  activeTab: Tab
  onTabChange: (tab: Tab) => void
  expertMode: boolean
  onExpertModeChange: (on: boolean) => void
}

// The analyst's day lives in the queue; everything else is reviewer/regulator depth,
// so it stays behind the Expert view toggle until asked for.
const ESSENTIAL_TABS: { id: Tab; label: string }[] = [{ id: 'queue', label: 'Alert Queue' }]

const EXPERT_TABS: { id: Tab; label: string }[] = [
  { id: 'learnedPatterns', label: 'Learned Patterns' },
  { id: 'metrics', label: 'System Performance' },
  { id: 'governance', label: 'Governance' },
  { id: 'audit', label: 'Audit Trail' },
]

// Lives in the full-width top bar; scrolls horizontally only as a last resort on a very small screen.
export function TabNav({ activeTab, onTabChange, expertMode, onExpertModeChange }: TabNavProps) {
  const tabs = expertMode ? [...ESSENTIAL_TABS, ...EXPERT_TABS] : ESSENTIAL_TABS
  return (
    <nav className="flex grow items-center gap-6 overflow-x-auto px-5">
      {tabs.map((tab) => {
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
      <button
        onClick={() => onExpertModeChange(!expertMode)}
        aria-pressed={expertMode}
        className={`ml-auto shrink-0 whitespace-nowrap rounded border px-2.5 py-1 text-[12px] font-medium transition-colors ${
          expertMode
            ? 'border-line-strong bg-surface text-ink'
            : 'border-line text-ink-faint hover:text-ink-soft'
        }`}
      >
        Expert view
      </button>
    </nav>
  )
}
