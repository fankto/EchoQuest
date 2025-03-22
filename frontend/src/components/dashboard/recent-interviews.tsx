'use client'

import { useState } from 'react'
import Link from 'next/link'
import { formatDistanceToNow } from 'date-fns'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Icons } from '@/components/ui/icons'

// Mock data for recent interviews
const mockInterviews = [
  {
    id: '1',
    title: 'Interview with John Doe',
    interviewee_name: 'John Doe',
    date: new Date(Date.now() - 1000 * 60 * 60 * 24 * 2), // 2 days ago
    status: 'processed',
  },
  {
    id: '2',
    title: 'Product Research Interview',
    interviewee_name: 'Jane Smith',
    date: new Date(Date.now() - 1000 * 60 * 60 * 24 * 5), // 5 days ago
    status: 'processed',
  },
  {
    id: '3',
    title: 'Customer Feedback Session',
    interviewee_name: 'Robert Johnson',
    date: new Date(Date.now() - 1000 * 60 * 60 * 24 * 7), // 7 days ago
    status: 'processed',
  },
]

export function RecentInterviews() {
  const [interviews, setInterviews] = useState(mockInterviews)
  const [isLoading, setIsLoading] = useState(false)

  // In a real app, you would fetch interviews from the API
  // useEffect(() => {
  //   const fetchInterviews = async () => {
  //     setIsLoading(true)
  //     try {
  //       const response = await api.get('/api/interviews?limit=5')
  //       setInterviews(response)
  //     } catch (error) {
  //       console.error('Failed to fetch interviews:', error)
  //     } finally {
  //       setIsLoading(false)
  //     }
  //   }
  //   fetchInterviews()
  // }, [])

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
                    {formatDistanceToNow(interview.date, { addSuffix: true })}
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