import type { ReactNode } from 'react'

export function Badge({ children, tone }: { children: ReactNode; tone: string }) {
  return (
    <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${tone}`}>
      {children}
    </span>
  )
}
