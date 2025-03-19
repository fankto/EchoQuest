'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import api from '@/lib/api-client'

type Stats = {
  totalInterviews: number
  processedInterviews: number
  totalQuestionnaires: number
  availableCredits: number
  chatTokens: number
}

type UserResponse = {
  id: string
  email: string
  full_name: string
  role: string
  available_interview_credits: number
  available_chat_tokens: number
}

type Interview = {
  id: string
  status: string
  // Add other interview properties as needed
}

type Questionnaire = {
  id: string
  title: string
  description: string
  content: string
  questions: string[]
  creator_id: string
  organization_id: string | null
  created_at: string
  updated_at: string
  interview_count: number
}

type ApiResponse<T> = {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
}

export function StatsCards() {
  const [stats, setStats] = useState<Stats>({
    totalInterviews: 0,
    processedInterviews: 0,
    totalQuestionnaires: 0,
    availableCredits: 0,
    chatTokens: 0,
  })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchStats = async () => {
      try {
        setLoading(true)
        setError(null)

        // Fetch interviews with pagination
        const interviewsResponse = await api.get<ApiResponse<Interview>>('/api/interviews')
        const interviews = interviewsResponse.items || []

        // Fetch questionnaires (non-paginated)
        const questionnairesResponse = await api.get<Questionnaire[]>('/api/questionnaires')
        const questionnaires = questionnairesResponse || []

        // Fetch user info
        const userResponse = await api.get<UserResponse>('/api/auth/me')
        const user = userResponse

        // Calculate stats
        const processedInterviews = interviews.filter(
          (interview) => interview.status === 'processed'
        ).length

        setStats({
          totalInterviews: interviews.length,
          processedInterviews,
          totalQuestionnaires: questionnaires.length,
          availableCredits: user.available_interview_credits,
          chatTokens: user.available_chat_tokens,
        })
      } catch (err) {
        console.error('Failed to fetch stats:', err)
        setError('Failed to fetch statistics')
      } finally {
        setLoading(false)
      }
    }

    fetchStats()
  }, [])

  if (loading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {['interviews', 'processed', 'questionnaires', 'credits'].map((type) => (
          <Card key={`loading-${type}`}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Loading...</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">...</div>
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Error</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-500">{error}</div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Total Interviews</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{stats.totalInterviews}</div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Processed Interviews</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{stats.processedInterviews}</div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Total Questionnaires</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{stats.totalQuestionnaires}</div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Available Credits</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{stats.availableCredits}</div>
        </CardContent>
      </Card>
    </div>
  )
}