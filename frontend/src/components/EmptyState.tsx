export function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center p-8 text-center">
      <h3 className="text-[15px] font-semibold text-ink">No alert selected</h3>
      <p className="mt-2 max-w-sm text-[13px] leading-relaxed text-ink-soft">
        Choose an alert from the queue to review the Copilot's triage call, the verifier's challenge, and the drafted report.
      </p>
    </div>
  )
}
