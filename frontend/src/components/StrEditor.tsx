import { useState } from 'react'
import type { STRDraft } from '../types'
import { Badge } from './ui/Badge'

interface StrEditorProps {
  strDraft: STRDraft
  summary: string
  onSummaryChange: (value: string) => void
  grounds: string[]
  onAddGround: (text: string) => void
  onRemoveGround: (idx: number) => void
}

export function StrEditor({ strDraft, summary, onSummaryChange, grounds, onAddGround, onRemoveGround }: StrEditorProps) {
  const [newGroundItem, setNewGroundItem] = useState('')

  const addGroundItem = () => {
    if (newGroundItem.trim()) {
      onAddGround(newGroundItem.trim())
      setNewGroundItem('')
    }
  }

  return (
    <section className="flex grow flex-col overflow-hidden rounded-lg border border-line bg-surface p-5">
      <div className="flex shrink-0 items-center justify-between">
        <h3 className="label">Suspicious transaction report</h3>
        <Badge tone="bg-paper text-ink-soft">Draft</Badge>
      </div>

      <div className="mt-4 grow space-y-5 overflow-y-auto pr-1">
        {/* Metadata */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="label">Institution</div>
            <div className="mt-1 text-[13px] text-ink">{strDraft.reportingInstitution}</div>
          </div>
          <div>
            <div className="label">Report date</div>
            <div className="mt-1 font-mono text-[13px] text-ink">{strDraft.reportDate.substring(0, 10)}</div>
          </div>
        </div>

        {/* Narrative */}
        <div>
          <div className="mb-1.5 flex items-baseline justify-between">
            <span className="label">Narrative</span>
            <span className="text-[11px] text-ink-faint">Drafted by AI · editable</span>
          </div>
          <textarea
            value={summary}
            onChange={(e) => onSummaryChange(e.target.value)}
            rows={4}
            className="w-full resize-none rounded-md border border-line bg-surface p-3 text-[13px] leading-relaxed text-ink outline-none focus:border-ink"
          />
        </div>

        {/* Grounds for suspicion */}
        <div>
          <div className="label mb-1.5">Grounds for suspicion</div>
          <ul className="space-y-1.5">
            {grounds.map((g, idx) => (
              <li key={idx} className="flex items-start justify-between gap-3 border-l-2 border-line py-0.5 pl-3">
                <span className="text-[13px] leading-relaxed text-ink">{g}</span>
                <button
                  onClick={() => onRemoveGround(idx)}
                  aria-label="Remove ground"
                  className="shrink-0 text-[12px] text-ink-faint hover:text-escalate"
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
          <div className="mt-2 flex gap-2">
            <input
              type="text"
              value={newGroundItem}
              onChange={(e) => setNewGroundItem(e.target.value)}
              placeholder="Add a ground…"
              onKeyDown={(e) => e.key === 'Enter' && addGroundItem()}
              className="grow rounded-md border border-line bg-surface px-3 py-1.5 text-[13px] text-ink outline-none placeholder:text-ink-faint focus:border-ink"
            />
            <button
              onClick={addGroundItem}
              className="rounded-md border border-line px-3 text-[13px] font-medium text-ink-soft hover:border-ink hover:text-ink"
            >
              Add
            </button>
          </div>
        </div>

        {/* Recommended action */}
        <div>
          <div className="label">Recommended action</div>
          <p className="mt-1 text-[13px] leading-relaxed text-ink-soft">{strDraft.recommendedAction}</p>
        </div>
      </div>
    </section>
  )
}
