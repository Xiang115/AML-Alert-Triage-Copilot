export function BrandHeader() {
  return (
    <div className="flex items-center gap-2.5 border-b border-line px-5 py-4">
      <span className="flex h-7 w-7 items-center justify-center rounded-md bg-ink font-mono text-[13px] font-semibold text-surface">
        A
      </span>
      <div className="leading-tight">
        <div className="text-[15px] font-semibold tracking-tight text-ink">AMLY</div>
        <div className="label">Alert triage desk</div>
      </div>
    </div>
  )
}
