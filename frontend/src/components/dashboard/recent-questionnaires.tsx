'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { formatDistanceToNow } from 'date-fns'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Icons } from '@/components/ui/icons'
import api from '@/lib/api-client'
import { toast } from 'sonner'
import type { Questionnaire } from '@/types/questionnaire'

type PaginatedResponse<T> = {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
}

export function RecentQuestionnaires() {
  const [questionnaires, setQuestionnaires] = useState<Questionnaire[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchQuestionnaires = async () => {
      try {
        setIsLoading(true)
        const response = await api.get<Questionnaire[]>('/questionnaires?limit=5')
        setQuestionnaires(response || [])
      } catch (error) {
        console.error('Failed to fetch questionnaires:', error)
        toast.error('Failed to load recent questionnaires')
      } finally {
        setIsLoading(false)
      }
    }
    
    fetchQuestionnaires()
  }, [])

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-40">
        <Icons.spinner className="h-8 w-8 animate-spin" />
      </div>
    )
  }

  if (questionnaires.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-40 text-center">
        <Icons.fileText className="h-10 w-10 text-muted-foreground mb-2" />
        <h3 className="text-lg font-medium">No questionnaires yet</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Create your first questionnaire to get started
        </p>
        <Link href="/questionnaires/new">
          <Button>
            <Icons.add className="mr-2 h-4 w-4" />
            New Questionnaire
          </Button>
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {questionnaires.map((questionnaire) => (
        <Link key={questionnaire.id} href={`/questionnaires/${questionnaire.id}`}>
          <Card className="cursor-pointer hover:bg-muted/50 transition-colors">
            <CardContent className="p-4">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-medium">{questionnaire.title}</h3>
                  <p className="text-sm text-muted-foreground">
                    {questionnaire.questions.length} questions
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Updated {formatDistanceToNow(new Date(questionnaire.updated_at || questionnaire.created_at), { addSuffix: true })}
                  </p>
                </div>
                <div className="flex items-center">
                  <span className="text-xs bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-100 px-2 py-1 rounded-full">
                    {questionnaire.interview_count} interviews
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