import type { FinalsQADefensePacket } from '../types'

export function FinalsQADefense({ packet }: { packet: FinalsQADefensePacket | null }) {
  if (!packet) {
    return (
      <section className="rounded-lg border border-line bg-surface p-5">
        <h3 className="label">Finals Q&A defense</h3>
        <div className="mt-3 text-[13px] text-ink-faint">Finals Q&A defense unavailable.</div>
      </section>
    )
  }

  return (
    <section className="rounded-lg border border-line bg-surface p-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="label">Finals Q&A defense</h3>
        <span className="rounded border border-verified bg-verified-soft px-2 py-1 text-[11px] font-medium text-verified">
          evidence answers
        </span>
      </div>

      <p className="mt-3 text-[13px] leading-relaxed text-ink-soft">{packet.primaryPosition}</p>

      <div className="mt-4 space-y-3">
        {packet.answers.map((answer) => (
          <article key={answer.objection} className="rounded-md border border-line bg-paper p-3">
            <div className="text-[13px] font-semibold text-ink">{answer.objection}</div>
            <p className="mt-2 text-[12px] leading-relaxed text-ink-soft">{answer.shortAnswer}</p>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-faint">Open live evidence</div>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {answer.evidenceEndpoints.map((endpoint) => (
                    <span key={endpoint} className="rounded border border-line bg-surface px-1.5 py-0.5 font-mono text-[11px] text-ink">
                      {endpoint}
                    </span>
                  ))}
                </div>
              </div>
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-faint">Demo action</div>
                <p className="mt-1 text-[12px] leading-relaxed text-ink-soft">{answer.demoAction}</p>
              </div>
            </div>
            <p className="mt-3 border-t border-line pt-2 text-[12px] leading-relaxed text-flag">
              {answer.trapToAvoid}
            </p>
          </article>
        ))}
      </div>

      <p className="mt-4 border-t border-line pt-3 text-[12px] leading-relaxed text-ink-soft">
        {packet.closingLine}
      </p>
    </section>
  )
}
