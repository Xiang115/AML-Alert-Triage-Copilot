import { useState, type ReactNode } from 'react'

interface CollapsibleSectionProps {
  title: string
  subtitle?: string
  defaultOpen?: boolean
  children: ReactNode
}

// A titled, collapsible grouping. Content is conditionally rendered (not just hidden), so a
// collapsed section keeps its heavy children out of the DOM until the analyst opts in.
export function CollapsibleSection({ title, subtitle, defaultOpen = false, children }: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div className="shrink-0">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 rounded-lg border border-line bg-surface px-5 py-3.5 text-left transition-colors hover:border-line-strong"
      >
        <span>
          <span className="label">{title}</span>
          {subtitle && <span className="mt-1 block text-[13px] leading-relaxed text-ink-soft">{subtitle}</span>}
        </span>
        <span className="shrink-0 font-mono text-[12px] text-ink-faint">{open ? 'Hide' : 'Show'}</span>
      </button>

      {open && <div className="mt-5 space-y-5">{children}</div>}
    </div>
  )
}
