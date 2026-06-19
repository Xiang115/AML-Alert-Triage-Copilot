export type Tab = 'queue' | 'metrics'

interface TabNavProps {
  activeTab: Tab
  onTabChange: (tab: Tab) => void
}

export function TabNav({ activeTab, onTabChange }: TabNavProps) {
  return (
    <nav className="grid grid-cols-2 gap-1 p-2 bg-slate-950/60 border-b border-slate-900">
      <button
        onClick={() => onTabChange('queue')}
        className={`flex items-center justify-center gap-2 rounded-md py-1.5 text-2xs font-semibold tracking-wide transition-all ${
          activeTab === 'queue'
            ? 'bg-slate-900 text-teal-400 shadow-sm border border-slate-800'
            : 'text-slate-500 hover:text-slate-300'
        }`}
      >
        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
        </svg>
        Alert Queue
      </button>
      <button
        onClick={() => onTabChange('metrics')}
        className={`flex items-center justify-center gap-2 rounded-md py-1.5 text-2xs font-semibold tracking-wide transition-all ${
          activeTab === 'metrics'
            ? 'bg-slate-900 text-teal-400 shadow-sm border border-slate-800'
            : 'text-slate-500 hover:text-slate-300'
        }`}
      >
        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 002 2h2a2 2 0 002-2z" />
        </svg>
        System Performance
      </button>
    </nav>
  )
}
