'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Button } from '@/components/ui/button'
import { Loader2, CreditCard } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { formatTokens } from '@/lib/format'
import Link from 'next/link'
import api from '@/lib/api-client'

type CreditSummaryData = {
  available_interview_credits: number
  available_chat_tokens: number
  interview_credits_used: number
  chat_tokens_used: number
}

export function CreditSummary() {
  const [isLoading, setIsLoading] = useState(true)
  const [creditData, setCreditData] = useState<CreditSummaryData | null>(null)
  const { user, refreshUser } = useAuth()

  useEffect(() => {
    const fetchCreditData = async () => {
      try {
        setIsLoading(true)
        
        // Attempt to fetch detailed credit history
        const data = await api.get<CreditSummaryData>('/api/credits/summary')
        setCreditData(data)
      } catch (error) {
        // Fallback to user object if detailed endpoint fails
        if (user) {
          setCreditData({
            available_interview_credits: user.available_interview_credits,
            available_chat_tokens: user.available_chat_tokens,
            interview_credits_used: 0, // Fallback values
            chat_tokens_used: 0,
          })
        }
      } finally {
        setIsLoading(false)
      }
    }

    fetchCreditData()
  }, [user])

  // If loading or no data available
  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-40">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!creditData && !user) {
    return (
      <div className="text-center p-4">
        <CreditCard className="h-12 w-12 mx-auto text-muted-foreground mb-2" />
        <h3 className="text-lg font-medium mb-1">Credit Information Unavailable</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Unable to retrieve your credit information.
        </p>
        <Button asChild>
          <Link href="/credits">View Credits</Link>
        </Button>
      </div>
    )
  }

  // Calculate interview credit usage percentage
  const interviewCreditsTotal = (creditData?.available_interview_credits || 0) + 
                               (creditData?.interview_credits_used || 0)
  const interviewCreditPercentage = interviewCreditsTotal > 0 
    ? ((creditData?.interview_credits_used || 0) / interviewCreditsTotal) * 100
    : 0

  // Calculate token usage percentage (if total is available)
  const tokenTotal = (creditData?.available_chat_tokens || 0) + 
                     (creditData?.chat_tokens_used || 0)
  const tokenPercentage = tokenTotal > 0
    ? ((creditData?.chat_tokens_used || 0) / tokenTotal) * 100
    : 0

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium">Interview Credits</h3>
          <span className="text-sm font-medium">
            {creditData?.available_interview_credits || user?.available_interview_credits || 0} remaining
          </span>
        </div>
        <Progress value={100 - interviewCreditPercentage} className="h-2" />
        <p className="text-xs text-muted-foreground">
          {creditData?.interview_credits_used || 0} credits used
        </p>
      </div>
      
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium">Chat Tokens</h3>
          <span className="text-sm font-medium">
            {formatTokens(creditData?.available_chat_tokens || user?.available_chat_tokens || 0)} remaining
          </span>
        </div>
        <Progress value={100 - tokenPercentage} className="h-2" />
        <p className="text-xs text-muted-foreground">
          {formatTokens(creditData?.chat_tokens_used || 0)} tokens used
        </p>
      </div>
      
      <div className="pt-2">
        <Button asChild variant="outline" className="w-full">
          <Link href="/credits">
            Buy Credits
          </Link>
        </Button>
      </div>
    </div>
  )
}