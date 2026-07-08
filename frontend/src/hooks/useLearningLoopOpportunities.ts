import { useEffect, useState } from 'react'
import { getLearningLoopOpportunities, type LearningLoopOpportunities } from '../api'

export function useLearningLoopOpportunities() {
  const [opportunities, setOpportunities] = useState<LearningLoopOpportunities | null>(null)

  useEffect(() => {
    let active = true
    getLearningLoopOpportunities()
      .then((data) => {
        if (active) setOpportunities(data)
      })
      .catch(() => {
        if (active) setOpportunities(null)
      })
    return () => {
      active = false
    }
  }, [])

  return opportunities
}
