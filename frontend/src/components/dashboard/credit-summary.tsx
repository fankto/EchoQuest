'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Icons } from '@/components/ui/icons'
import api from '@/lib/api-client'
import { toast } from 'sonner'

type UserResponse = {
  id: string
  email: string
  full_name: string
  role: string
  available_interview_credits: number
  available_chat_tokens: number
}

type CreditData = {
  available_interview_credits: number
  available_chat_tokens: number
}

export function CreditSummary() {
  const [credits, setCredits] = useState<CreditData>({
    available_interview_credits: 0,
    available_chat_tokens: 0
  })
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchCredits = async () => {
      try {
        setIsLoading(true)
        const response = await api.get<UserResponse>('/api/auth/me')
        setCredits({
          available_interview_credits: response.available_interview_credits,
          available_chat_tokens: response.available_chat_tokens
        })
      } catch (error) {
        console.error('Failed to fetch credits:', error)
        toast.error('Failed to load credit information')
      } finally {
        setIsLoading(false)
      }
    }
    
    fetchCredits()
  }, [])

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-40">
        <Icons.spinner className="h-8 w-8 animate-spin" />
      </div>
    )
  }

  // Format chat tokens for display (in K)
  const formatTokens = (tokens: number) => {
    return `${(tokens / 1000).toFixed(0)}K`
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="flex justify-between text-sm">
          <span>Interview Credits</span>
          <span className="font-medium">
            {credits.available_interview_credits} available
          </span>
        </div>
        <Progress value={100} className="h-2" />
        <p className="text-xs text-muted-foreground">
          Used for processing new interviews
        </p>
      </div>

      <div className="space-y-2">
        <div className="flex justify-between text-sm">
          <span>Chat Tokens</span>
          <span className="font-medium">
            {formatTokens(credits.available_chat_tokens)} available
          </span>
        </div>
        <Progress value={100} className="h-2" />
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
            Purchase Credits
          </Button>
        </Link>
      </div>
    </div>
  )
}