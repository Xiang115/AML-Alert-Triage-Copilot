import type { ReactNode } from 'react'

export function Badge({ children, tone }: { children: ReactNode; tone: string }) {
  return (
    <span className={`rounded px-1.5 py-0.5 text-3xs font-extrabold tracking-wider uppercase ${tone}`}>
      {children}
    </span>
  )
}
