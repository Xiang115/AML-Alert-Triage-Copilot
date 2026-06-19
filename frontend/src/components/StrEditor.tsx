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
    <section className="flex-grow rounded-xl border border-slate-900 bg-slate-950/20 p-4 flex flex-col space-y-3 overflow-hidden">
      <div className="flex items-center gap-1.5 border-b border-slate-900 pb-2 flex-shrink-0">
        <svg className="h-3.5 w-3.5 text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <h3 className="text-2xs font-black uppercase tracking-wider text-rose-400">Draft STR</h3>
        <Badge tone="bg-rose-500/10 text-rose-400 border border-rose-500/10 ml-auto">Draft</Badge>
      </div>

      {/* Scrollable Form Body */}
      <div className="flex-grow overflow-y-auto space-y-3.5 pr-1 text-2xs">
        {/* Static Metadata */}
        <div className="grid grid-cols-2 gap-3 rounded bg-slate-950/60 p-2.5 border border-slate-900">
          <div>
            <span className="text-3xs font-bold uppercase tracking-wider text-slate-500">Institution</span>
            <div className="font-semibold text-slate-400 mt-0.5">{strDraft.reportingInstitution}</div>
          </div>
          <div>
            <span className="text-3xs font-bold uppercase tracking-wider text-slate-500">Report Date</span>
            <div className="font-semibold text-slate-400 mt-0.5">{strDraft.reportDate.substring(0, 10)}</div>
          </div>
        </div>

        {/* Activity Summary (Minimalist Writing-Desk Style) */}
        <div>
          <div className="flex justify-between items-center mb-1">
            <span className="text-3xs font-bold uppercase tracking-wider text-slate-500">Narrative Description</span>
            <span className="text-3xs text-slate-500">Drafted by AI</span>
          </div>
          <textarea
            value={summary}
            onChange={(e) => onSummaryChange(e.target.value)}
            rows={4}
            className="w-full rounded border border-slate-900 bg-slate-950/60 p-2 text-2xs leading-relaxed text-slate-300 outline-none focus:border-teal-500 transition-colors"
          />
        </div>

        {/* Grounds for Suspicion */}
        <div className="space-y-1.5">
          <span className="text-3xs font-bold uppercase tracking-wider text-slate-500">Grounds for Suspicion</span>
          <ul className="space-y-1">
            {grounds.map((g, idx) => (
              <li key={idx} className="flex items-start justify-between gap-2 rounded bg-slate-950/20 border border-slate-900 px-2.5 py-1.5">
                <span className="font-medium text-slate-400 leading-normal">{g}</span>
                <button
                  onClick={() => onRemoveGround(idx)}
                  className="text-slate-600 hover:text-rose-400 transition-colors"
                >
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </li>
            ))}
          </ul>
          {/* Add grounds item input */}
          <div className="flex gap-2">
            <input
              type="text"
              value={newGroundItem}
              onChange={(e) => setNewGroundItem(e.target.value)}
              placeholder="Add reason..."
              onKeyDown={(e) => e.key === 'Enter' && addGroundItem()}
              className="flex-grow rounded border border-slate-900 bg-slate-950/60 px-2.5 py-1 text-2xs text-slate-355 outline-none focus:border-teal-500 transition-colors"
            />
            <button
              onClick={addGroundItem}
              className="rounded border border-slate-800 bg-slate-900 hover:bg-slate-800 px-2.5 text-slate-400 text-3xs font-bold cursor-pointer transition-colors"
            >
              Add
            </button>
          </div>
        </div>

        {/* Recommended Action */}
        <div>
          <span className="text-3xs font-bold uppercase tracking-wider text-slate-500">Action Plan</span>
          <div className="mt-0.5 font-semibold text-slate-400 bg-slate-950/60 p-2.5 border border-slate-900 rounded leading-relaxed">
            {strDraft.recommendedAction}
          </div>
        </div>
      </div>
    </section>
  )
}
