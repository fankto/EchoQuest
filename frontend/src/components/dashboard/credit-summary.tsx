'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Icons } from '@/components/ui/icons'

// Mock data for credits
const mockCredits = {
  interviewCredits: 8,
  maxInterviewCredits: 10,
  chatTokens: 50000,
  maxChatTokens: 100000
}

export function CreditSummary() {
  const [credits, setCredits] = useState(mockCredits)
  const [isLoading, setIsLoading] = useState(false)

  // In a real app, you would fetch credits from the API
  // useEffect(() => {
  //   const fetchCredits = async () => {
  //     setIsLoading(true)
  //     try {
  //       const response = await api.get('/api/credits')
  //       setCredits(response)
  //     } catch (error) {
  //       console.error('Failed to fetch credits:', error)
  //     } finally {
  //       setIsLoading(false)
  //     }
  //   }
  //   fetchCredits()
  // }, [])

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-40">
        <Icons.spinner className="h-8 w-8 animate-spin" />
      </div>
    )
  }

  const interviewCreditPercentage = (credits.interviewCredits / credits.maxInterviewCredits) * 100
  const chatTokenPercentage = (credits.chatTokens / credits.maxChatTokens) * 100

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="flex justify-between text-sm">
          <span>Interview Credits</span>
          <span className="font-medium">{credits.interviewCredits} / {credits.maxInterviewCredits}</span>
        </div>
        <Progress value={interviewCreditPercentage} className="h-2" />
        <p className="text-xs text-muted-foreground">
          Used for processing new interviews
        </p>
      </div>

      <div className="space-y-2">
        <div className="flex justify-between text-sm">
          <span>Chat Tokens</span>
          <span className="font-medium">{(credits.chatTokens / 1000).toFixed(0)}K / {(credits.maxChatTokens / 1000).toFixed(0)}K</span>
        </div>
        <Progress value={chatTokenPercentage} className="h-2" />
        <p className="text-xs text-muted-foreground">
          Used for interview chat interactions
        </p>
      </div>

      <div className="flex justify-between gap-2 pt-2">
        <Link href="/credits/history">
          <Button variant="outline" size="sm">
            <Icons.fileText className="mr-2 h-4 w-4" />
            History
          </Button>
        </Link>
        <Link href="/credits">
          <Button size="sm">
            <Icons.add className="mr-2 h-4 w-4" />
            Buy Credits
          </Button>
        </Link>
      </div>
    </div>
  )
}