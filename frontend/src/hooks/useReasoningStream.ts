import { useCallback, useRef, useState } from 'react'
import { getAlert } from '../api'
import type { TriageResult } from '../types'
import { buildReasoningEvents, type ReasoningEvent } from './useReasoningPlayback'

const MOCK = import.meta.env.VITE_MOCK !== 'false'
const BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'
const MOCK_STEP_MS = 500

type StreamMsg =
  | { type: 'stage'; id: string; label: string; detail: string; tone?: 'escalate' | 'flag' | 'verified' }
  | { type: 'indicator'; text: string; fired: boolean }
  | { type: 'result'; triage: TriageResult }
  | { type: 'error'; message: string }

interface StartHandlers {
  onResult: (triage: TriageResult) => void
  onError?: (message: string) => void
}

export interface ReasoningStream {
  events: ReasoningEvent[]
  streaming: boolean
  start: (alertId: string, handlers: StartHandlers) => void
  stop: () => void
}

/**
 * Live "thinking" stream: opens an SSE connection to the backend, which runs the real
 * pipeline and emits a stage event as each step completes — so the reasoning appears in
 * real time, not after the call. In MOCK mode (no backend) it replays the precomputed
 * reasoning on a timer so the view still demos.
 */
export function useReasoningStream(): ReasoningStream {
  const [events, setEvents] = useState<ReasoningEvent[]>([])
  const [streaming, setStreaming] = useState(false)
  const esRef = useRef<EventSource | null>(null)
  const timers = useRef<ReturnType<typeof setTimeout>[]>([])

  const cleanup = () => {
    esRef.current?.close()
    esRef.current = null
    timers.current.forEach(clearTimeout)
    timers.current = []
  }

  const stop = useCallback(() => {
    cleanup()
    setStreaming(false)
    setEvents([])
  }, [])

  const start = useCallback((alertId: string, { onResult, onError }: StartHandlers) => {
    cleanup()
    setEvents([])
    setStreaming(true)

    if (MOCK) {
      getAlert(alertId)
        .then((alert) => {
          const evs = buildReasoningEvents(alert.triage)
          evs.forEach((e, i) => {
            const t = setTimeout(() => {
              setEvents((prev) => [...prev, e])
              if (i === evs.length - 1) {
                setStreaming(false)
                onResult(alert.triage)
              }
            }, (i + 1) * MOCK_STEP_MS)
            timers.current.push(t)
          })
        })
        .catch((err) => {
          setStreaming(false)
          onError?.(String(err))
        })
      return
    }

    const es = new EventSource(new URL(`/alerts/${alertId}/triage/stream`, BASE).toString())
    esRef.current = es
    es.onmessage = (e) => {
      const msg = JSON.parse(e.data) as StreamMsg
      if (msg.type === 'result') {
        setStreaming(false)
        cleanup()
        onResult(msg.triage)
      } else if (msg.type === 'error') {
        onError?.(msg.message)
      } else if (msg.type === 'stage') {
        setEvents((prev) => [...prev, { kind: 'stage', id: msg.id, label: msg.label, detail: msg.detail, tone: msg.tone }])
      } else {
        setEvents((prev) => [...prev, { kind: 'indicator', text: msg.text, fired: msg.fired }])
      }
    }
    es.onerror = () => {
      setStreaming(false)
      cleanup()
      onError?.('Live stream connection failed.')
    }
  }, [])

  return { events, streaming, start, stop }
}
