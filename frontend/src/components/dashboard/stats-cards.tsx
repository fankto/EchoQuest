'use client'

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Icons } from '@/components/ui/icons'

// Mock data for stats
const mockStats = {
  totalInterviews: 12,
  processedInterviews: 10,
  totalQuestionnaires: 5,
  availableCredits: 8
}

export function StatsCards() {
  const [stats, setStats] = useState(mockStats)
  const [isLoading, setIsLoading] = useState(false)

  // In a real app, you would fetch stats from the API
  // useEffect(() => {
  //   const fetchStats = async () => {
  //     setIsLoading(true)
  //     try {
  //       const response = await api.get('/api/stats')
  //       setStats(response)
  //     } catch (error) {
  //       console.error('Failed to fetch stats:', error)
  //     } finally {
  //       setIsLoading(false)
  //     }
  //   }
  //   fetchStats()
  // }, [])

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">
            Total Interviews
          </CardTitle>
          <Icons.fileText className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">
            {isLoading ? (
              <Icons.spinner className="h-4 w-4 animate-spin" />
            ) : (
              stats.totalInterviews
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            {stats.processedInterviews} processed
          </p>
        </CardContent>
      </Card>
      
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">
            Questionnaires
          </CardTitle>
          <Icons.file className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">
            {isLoading ? (
              <Icons.spinner className="h-4 w-4 animate-spin" />
            ) : (
              stats.totalQuestionnaires
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            Templates for interviews
          </p>
        </CardContent>
      </Card>
      
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">
            Available Credits
          </CardTitle>
          <Icons.creditCard className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">
            {isLoading ? (
              <Icons.spinner className="h-4 w-4 animate-spin" />
            ) : (
              stats.availableCredits
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            For new interviews
          </p>
        </CardContent>
      </Card>
      
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">
            Chat Tokens
          </CardTitle>
          <Icons.messageSquare className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">
            {isLoading ? (
              <Icons.spinner className="h-4 w-4 animate-spin" />
            ) : (
              '50K'
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            For interview chat
          </p>
        </CardContent>
      </Card>
    </div>
  )
}