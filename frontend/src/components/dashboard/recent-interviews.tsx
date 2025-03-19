'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { formatDistanceToNow } from 'date-fns'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Icons } from '@/components/ui/icons'
import api from '@/lib/api-client'
import { toast } from 'sonner'
import type { Interview } from '@/types/interview'

type PaginatedResponse<T> = {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
}

export function RecentInterviews() {
  const [interviews, setInterviews] = useState<Interview[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchInterviews = async () => {
      try {
        setIsLoading(true)
        const response = await api.get<PaginatedResponse<Interview>>('/api/interviews?limit=5')
        setInterviews(response.items || [])
      } catch (error) {
        console.error('Failed to fetch interviews:', error)
        toast.error('Failed to load recent interviews')
      } finally {
        setIsLoading(false)
      }
    }
    
    fetchInterviews()
  }, [])

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-40">
        <Icons.spinner className="h-8 w-8 animate-spin" />
      </div>
    )
  }

  if (interviews.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-40 text-center">
        <Icons.fileText className="h-10 w-10 text-muted-foreground mb-2" />
        <h3 className="text-lg font-medium">No interviews yet</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Create your first interview to get started
        </p>
        <Link href="/interviews/new">
          <Button>
            <Icons.add className="mr-2 h-4 w-4" />
            New Interview
          </Button>
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {interviews.map((interview) => (
        <Link key={interview.id} href={`/interviews/${interview.id}`}>
          <Card className="cursor-pointer hover:bg-muted/50 transition-colors">
            <CardContent className="p-4">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-medium">{interview.title}</h3>
                  <p className="text-sm text-muted-foreground">
                    {interview.interviewee_name}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {formatDistanceToNow(new Date(interview.date), { addSuffix: true })}
                  </p>
                </div>
                <div className="flex items-center">
                  <span className="text-xs bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100 px-2 py-1 rounded-full">
                    {interview.status}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>
        </Link>
      ))}
    </div>
  )
}