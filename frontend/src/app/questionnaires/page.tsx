'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { PlusIcon, Search, FileText, Edit } from 'lucide-react'
import { toast } from 'sonner'
import { DashboardHeader } from '@/components/dashboard/dashboard-header'
import { formatDistanceToNow } from 'date-fns'
import api from '@/lib/api-client'

type Questionnaire = {
  id: string
  title: string
  description?: string
  questions: string[]
  creator_id: string
  organization_id?: string
  created_at: string
  updated_at?: string
  interview_count: number
}

export default function QuestionnairesPage() {
  const [questionnaires, setQuestionnaires] = useState<Questionnaire[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()

  useEffect(() => {
    const fetchQuestionnaires = async () => {
      try {
        setIsLoading(true)
        const data = await api.get<Questionnaire[]>('/api/questionnaires')
        setQuestionnaires(data)
      } catch (error) {
        toast.error('Failed to fetch questionnaires')
      } finally {
        setIsLoading(false)
      }
    }

    fetchQuestionnaires()
  }, [])

  return (
    <div className="flex min-h-screen flex-col">
      <DashboardHeader />
      
      <main className="flex-1 space-y-4 p-8 pt-6">
        <div className="flex items-center justify-between">
          <h2 className="text-3xl font-bold tracking-tight">Questionnaires</h2>
          <Link href="/questionnaires/new">
            <Button>
              <PlusIcon className="mr-2 h-4 w-4" />
              New Questionnaire
            </Button>
          </Link>
        </div>
        
        {isLoading ? (
          <div className="flex justify-center p-8">
            <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" />
          </div>
        ) : questionnaires.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <div className="rounded-full bg-muted p-3">
                <FileText className="h-10 w-10 text-muted-foreground" />
              </div>
              <h3 className="mt-4 text-lg font-semibold">No questionnaires found</h3>
              <p className="mt-2 text-center text-sm text-muted-foreground max-w-sm">
                You haven't created any questionnaires yet. Create your first questionnaire to get started.
              </p>
              <Link href="/questionnaires/new" className="mt-4">
                <Button>
                  <PlusIcon className="mr-2 h-4 w-4" />
                  Create your first questionnaire
                </Button>
              </Link>
            </CardContent>
          </Card>
        ) : (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>Questions</TableHead>
                  <TableHead>Interviews</TableHead>
                  <TableHead>Last Updated</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {questionnaires.map((questionnaire) => (
                  <TableRow key={questionnaire.id} className="cursor-pointer hover:bg-muted/50">
                    <TableCell className="font-medium" onClick={() => router.push(`/questionnaires/${questionnaire.id}`)}>
                      {questionnaire.title}
                    </TableCell>
                    <TableCell onClick={() => router.push(`/questionnaires/${questionnaire.id}`)}>
                      {questionnaire.questions.length}
                    </TableCell>
                    <TableCell onClick={() => router.push(`/questionnaires/${questionnaire.id}`)}>
                      {questionnaire.interview_count}
                    </TableCell>
                    <TableCell onClick={() => router.push(`/questionnaires/${questionnaire.id}`)}>
                      {questionnaire.updated_at 
                        ? formatDistanceToNow(new Date(questionnaire.updated_at), { addSuffix: true })
                        : formatDistanceToNow(new Date(questionnaire.created_at), { addSuffix: true })}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button 
                        variant="ghost" 
                        size="icon"
                        onClick={() => router.push(`/questionnaires/${questionnaire.id}`)}
                      >
                        <Edit className="h-4 w-4" />
                        <span className="sr-only">Edit</span>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </main>
    </div>
  )
}