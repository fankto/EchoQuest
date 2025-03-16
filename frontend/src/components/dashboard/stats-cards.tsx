'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Loader2, FileAudio, FileText, MessageSquare, Clock } from 'lucide-react'
import { toast } from 'sonner'
import api from '@/lib/api-client'
import { formatTokens } from '@/lib/format'

type StatsData = {
  total_interviews: number
  transcribed_interviews: number
  total_questionnaires: number
  available_credits: number
  available_tokens: number
  pending_interviews: number
  total_interview_duration: number
}

export function StatsCards() {
  const [stats, setStats] = useState<StatsData | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchStats = async () => {
      try {
        setIsLoading(true)
        
        // In a real app, we'd have a dedicated stats endpoint
        // Here we'll simulate it by fetching various resources
        
        const [interviewsData, questionnairesData, userProfile] = await Promise.all([
          api.get('/api/interviews/'),
          api.get('/api/questionnaires'),
          api.get('/api/auth/me')
        ])
        
        // Process the data into stats
        const interviews = interviewsData.items || []
        const transcribedInterviews = interviews.filter(i => i.status === 'transcribed').length
        const pendingInterviews = interviews.filter(i => 
          ['created', 'uploaded', 'processing', 'processed', 'transcribing'].includes(i.status)
        ).length
        
        // Calculate total duration of all interviews
        const totalDuration = interviews.reduce((total, interview) => {
          return total + (interview.duration || 0)
        }, 0)
        
        setStats({
          total_interviews: interviews.length,
          transcribed_interviews: transcribedInterviews,
          total_questionnaires: questionnairesData.length || 0,
          available_credits: userProfile.available_interview_credits || 0,
          available_tokens: userProfile.available_chat_tokens || 0,
          pending_interviews: pendingInterviews,
          total_interview_duration: totalDuration
        })
      } catch (error) {
        console.error('Failed to fetch stats:', error)
        toast.error('Failed to load dashboard statistics')
      } finally {
        setIsLoading(false)
      }
    }

    fetchStats()
  }, [])

  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i} className="h-[140px] flex items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </Card>
        ))}
      </div>
    )
  }

  if (!stats) {
    return null
  }

  // Format the total duration in hours and minutes
  const formatDuration = (seconds: number) => {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    
    if (hours > 0) {
      return `${hours}h ${minutes}m`
    }
    return `${minutes}m`
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">
            Total Interviews
          </CardTitle>
          <FileAudio className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{stats.total_interviews}</div>
          <p className="text-xs text-muted-foreground mt-1">
            {stats.transcribed_interviews} transcribed
          </p>
        </CardContent>
      </Card>
      
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">
            Interview Credits
          </CardTitle>
          <MessageSquare className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{stats.available_credits}</div>
          <p className="text-xs text-muted-foreground mt-1">
            {formatTokens(stats.available_tokens)} chat tokens
          </p>
        </CardContent>
      </Card>
      
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">
            Questionnaires
          </CardTitle>
          <FileText className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{stats.total_questionnaires}</div>
          <p className="text-xs text-muted-foreground mt-1">
            Interview templates
          </p>
        </CardContent>
      </Card>
      
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">
            Total Duration
          </CardTitle>
          <Clock className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{formatDuration(stats.total_interview_duration)}</div>
          <p className="text-xs text-muted-foreground mt-1">
            {stats.pending_interviews} pending interviews
          </p>
        </CardContent>
      </Card>
    </div>
  )
}