import { useEffect, useState } from 'react'
import { getLearnedPatterns, type LearnedPatternRecord } from '../api'

export type LearnedPattern = LearnedPatternRecord

export function useLearnedPatterns() {
  const [data, setData] = useState<LearnedPattern[] | null>(null)

  useEffect(() => {
    let active = true

    getLearnedPatterns()
      .then((patterns) => {
        if (active) setData(patterns)
      })
      .catch((error) => {
        console.error(error)
        if (active) setData([])
      })

    return () => {
      active = false
    }
  }, [])

  return data
}
