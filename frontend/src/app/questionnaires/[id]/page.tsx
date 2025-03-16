'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { DashboardHeader } from '@/components/dashboard/dashboard-header'
import { QuestionnaireForm } from '@/components/questionnaire/questionnaire-form'
import { QuestionList } from '@/components/questionnaire/question-list'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ChevronLeft, FileText, Pencil, Trash } from 'lucide-react'
import { toast } from 'sonner'
import api from '@/lib/api-client'

type Questionnaire = {
  id: string
  title: string
  description?: string
  content: string
  questions: string[]
  creator_id: string
  organization_id?: string
  created_at: string
  updated_at?: string
  interview_count: number
}

export default function QuestionnairePage() {
  const { id } = useParams()
  const [questionnaire, setQuestionnaire] = useState<Questionnaire | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isEditing, setIsEditing] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const router = useRouter()

  useEffect(() => {
    const fetchQuestionnaire = async () => {
      try {
        setIsLoading(true)
        const data = await api.get<Questionnaire>(`/api/questionnaires/${id}`)
        setQuestionnaire(data)
      } catch (error) {
        toast.error('Failed to fetch questionnaire')
      } finally {
        setIsLoading(false)
      }
    }

    fetchQuestionnaire()
  }, [id])

  const handleDelete = async () => {
    try {
      setIsDeleting(true)
      await api.delete(`/api/questionnaires/${id}`)
      toast.success('Questionnaire deleted successfully')
      router.push('/questionnaires')
    } catch (error) {
      toast.error('Failed to delete questionnaire')
    } finally {
      setIsDeleting(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex min-h-screen flex-col">
        <DashboardHeader />
        <main className="flex-1 p-8 pt-6">
          <div className="flex justify-center p-8">
            <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full"></div>
          </div>
        </main>
      </div>
    )
  }

  if (!questionnaire) {
    return (
      <div className="flex min-h-screen flex-col">
        <DashboardHeader />
        <main className="flex-1 p-8 pt-6">
          <div className="flex flex-col items-center justify-center p-8">
            <FileText className="h-16 w-16 text-muted-foreground mb-4" />
            <h2 className="text-xl font-semibold mb-4">Questionnaire not found</h2>
            <Button as={Link} href="/questionnaires">
              <ChevronLeft className="mr-2 h-4 w-4" />
              Back to Questionnaires
            </Button>
          </div>
        </main>
      </div>
    )
  }

  if (isEditing) {
    return (
      <div className="flex min-h-screen flex-col">
        <DashboardHeader />
        <main className="flex-1 space-y-4 p-8 pt-6">
          <div className="flex items-center justify-between">
            <div>
              <Button 
                variant="outline" 
                size="sm" 
                onClick={() => setIsEditing(false)}
                className="mb-4"
              >
                <ChevronLeft className="mr-1 h-4 w-4" />
                Cancel Editing
              </Button>
              <h2 className="text-3xl font-bold tracking-tight">Edit Questionnaire</h2>
              <p className="text-muted-foreground">
                Update questionnaire details and questions
              </p>
            </div>
          </div>
          
          <div className="mx-auto max-w-3xl">
            <QuestionnaireForm initialData={questionnaire} />
          </div>
        </main>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen flex-col">
      <DashboardHeader />
      
      <main className="flex-1 space-y-4 p-8 pt-6">
        <div className="flex items-center justify-between">
          <div>
            <Button variant="outline" size="sm" asChild className="mb-4">
              <Link href="/questionnaires">
                <ChevronLeft className="mr-1 h-4 w-4" />
                Back to Questionnaires
              </Link>
            </Button>
            <h2 className="text-3xl font-bold tracking-tight">{questionnaire.title}</h2>
            {questionnaire.description && (
              <p className="text-muted-foreground">
                {questionnaire.description}
              </p>
            )}
          </div>
          
          <div className="flex items-center gap-2">
            <Button 
              variant="outline" 
              onClick={() => setIsEditing(true)}
            >
              <Pencil className="mr-2 h-4 w-4" />
              Edit
            </Button>
            
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="destructive">
                  <Trash className="mr-2 h-4 w-4" />
                  Delete
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
                  <AlertDialogDescription>
                    This action cannot be undone. This will permanently delete this questionnaire
                    {questionnaire.interview_count > 0 && 
                      ` and remove it from ${questionnaire.interview_count} interviews`}.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction 
                    onClick={handleDelete}
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  >
                    {isDeleting ? "Deleting..." : "Delete"}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </div>
        
        <Tabs defaultValue="questions" className="space-y-4">
          <TabsList>
            <TabsTrigger value="questions">Questions</TabsTrigger>
            <TabsTrigger value="content">Content</TabsTrigger>
            <TabsTrigger value="interviews">Interviews</TabsTrigger>
          </TabsList>
          
          <TabsContent value="questions" className="space-y-4">
            <QuestionList questions={questionnaire.questions} readOnly />
          </TabsContent>
          
          <TabsContent value="content" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Questionnaire Content</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="whitespace-pre-wrap bg-muted p-4 rounded-md max-h-[500px] overflow-y-auto">
                  {questionnaire.content}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
          
          <TabsContent value="interviews" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Related Interviews</CardTitle>
              </CardHeader>
              <CardContent>
                {questionnaire.interview_count > 0 ? (
                  <p>This questionnaire is used in {questionnaire.interview_count} interviews.</p>
                ) : (
                  <div className="text-center py-8">
                    <p className="text-muted-foreground mb-4">
                      This questionnaire hasn't been used in any interviews yet.
                    </p>
                    <Button asChild>
                      <Link href="/interviews/new">
                        Create Interview
                      </Link>
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}

// Fallback components to avoid errors
function AlertDialog({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

function AlertDialogTrigger({ asChild, children }: { asChild?: boolean, children: React.ReactNode }) {
  return <>{children}</>;
}

function AlertDialogContent({ children }: { children: React.ReactNode }) {
  return <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center">
    <div className="fixed inset-0 bg-background/80 backdrop-blur-sm" />
    <div className="fixed z-50 grid w-full gap-4 rounded-b-lg border bg-background p-6 shadow-lg animate-in fade-in-90 sm:max-w-lg sm:rounded-lg sm:zoom-in-90">
      {children}
    </div>
  </div>;
}

function AlertDialogHeader({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-col space-y-2 text-center sm:text-left">{children}</div>;
}

function AlertDialogFooter({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2">{children}</div>;
}

function AlertDialogTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="text-lg font-semibold">{children}</h2>;
}

function AlertDialogDescription({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-muted-foreground">{children}</p>;
}

function AlertDialogAction({ children, onClick, className }: { children: React.ReactNode, onClick?: () => void, className?: string }) {
  return <button className={`inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground ring-offset-background transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 ${className}`} onClick={onClick}>{children}</button>;
}

function AlertDialogCancel({ children }: { children: React.ReactNode }) {
  return <button className="mt-2 inline-flex h-10 items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium ring-offset-background transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 sm:mt-0">{children}</button>;
}