export function BrandHeader() {
  return (
    <div className="flex w-80 shrink-0 items-center gap-2.5 border-r border-line px-5 py-3">
      <span className="flex h-7 w-7 items-center justify-center rounded-md bg-ink font-mono text-[13px] font-semibold text-surface">
        V
      </span>
      <div className="leading-tight">
        <div className="text-[15px] font-semibold tracking-tight text-ink">VerdictAML</div>
        <div className="label">Alert triage desk</div>
      </div>
    </div>
  )
}
