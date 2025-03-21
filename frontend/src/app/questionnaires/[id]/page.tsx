'use client'

import { useEffect, useState, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '@/components/ui/card'
import { DashboardHeader } from '@/components/dashboard/dashboard-header'
import { QuestionnaireForm } from '@/components/questionnaire/questionnaire-form'
import { QuestionList } from '@/components/questionnaire/question-list'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ChevronLeft, FileText, Pencil, Trash, PlusIcon } from 'lucide-react'
import { toast } from 'sonner'
import api from '@/lib/api-client'
import { ScrollArea } from '@/components/ui/scroll-area'
import { InterviewStatus } from '@/types/interview'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'

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

type Interview = {
  id: string
  title: string
  interviewee_name: string
  date: string
  status?: string
}

type PaginatedResponse<T> = {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
}

export default function QuestionnairePage() {
  const { id } = useParams()
  const [questionnaire, setQuestionnaire] = useState<Questionnaire | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isEditing, setIsEditing] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [relatedInterviews, setRelatedInterviews] = useState<Interview[]>([])
  const [isLoadingInterviews, setIsLoadingInterviews] = useState(false)
  const [availableInterviews, setAvailableInterviews] = useState<Interview[]>([])
  const [selectedInterviewId, setSelectedInterviewId] = useState<string>("")
  const [isLinkingDialogOpen, setIsLinkingDialogOpen] = useState(false)
  const [isLinkingInterview, setIsLinkingInterview] = useState(false)
  const router = useRouter()

  useEffect(() => {
    const fetchQuestionnaire = async () => {
      try {
        setIsLoading(true)
        const data = await api.get<Questionnaire>(`/questionnaires/${id}`)
        setQuestionnaire(data)
      } catch (error) {
        toast.error('Failed to fetch questionnaire')
      } finally {
        setIsLoading(false)
      }
    }

    fetchQuestionnaire()
  }, [id])

  const fetchRelatedInterviews = useCallback(async () => {
    if (!id) return

    try {
      setIsLoadingInterviews(true)
      const data = await api.get<PaginatedResponse<Interview>>(`/interviews/questionnaires/${id}/interviews`)
      if (data?.items) {
        setRelatedInterviews(data.items)
      }
    } catch (error) {
      console.error('Failed to fetch related interviews:', error)
    } finally {
      setIsLoadingInterviews(false)
    }
  }, [id])

  useEffect(() => {
    if (id && !isLoading) {
      fetchRelatedInterviews()
    }
  }, [id, isLoading, fetchRelatedInterviews])

  const handleDelete = async () => {
    try {
      setIsDeleting(true)
      await api.delete(`/questionnaires/${id}`)
      toast.success('Questionnaire deleted successfully')
      router.push('/questionnaires')
    } catch (error) {
      toast.error('Failed to delete questionnaire')
    } finally {
      setIsDeleting(false)
    }
  }

  const fetchAvailableInterviews = useCallback(async () => {
    if (!id) return
    
    try {
      setIsLinkingInterview(false)
      console.log('Fetching available interviews...')
      const response = await api.get<PaginatedResponse<Interview>>('/interviews')
      console.log('Received interviews data:', response)
      
      if (response?.items) {
        const availableOnes = response.items.filter(interview => {
          const isTranscribed = interview.status === InterviewStatus.TRANSCRIBED
          const isNotAlreadyLinked = !relatedInterviews.some(ri => ri.id === interview.id)
          console.log(`Interview ${interview.id}: transcribed=${isTranscribed}, notLinked=${isNotAlreadyLinked}`)
          return isTranscribed && isNotAlreadyLinked
        })
        console.log('Filtered available interviews:', availableOnes)
        setAvailableInterviews(availableOnes)
      }
    } catch (error) {
      console.error('Failed to fetch available interviews:', error)
    }
  }, [id, relatedInterviews])

  useEffect(() => {
    if (id && !isLoading) {
      fetchAvailableInterviews()
    }
  }, [id, isLoading, fetchAvailableInterviews])

  const linkInterview = async () => {
    if (!selectedInterviewId) {
      toast.error('Please select an interview to link')
      return
    }

    try {
      setIsLinkingInterview(true)
      const formData = new FormData()
      formData.append('questionnaire_id', id as string)
      
      await api.upload(`/interviews/${selectedInterviewId}/attach-questionnaire`, formData)
      toast.success('Interview linked successfully')
      
      await fetchRelatedInterviews()
      await fetchAvailableInterviews()
      
      setSelectedInterviewId("")
      setIsLinkingDialogOpen(false)
    } catch (error) {
      toast.error('Failed to link interview')
    } finally {
      setIsLinkingInterview(false)
    }
  }

  useEffect(() => {
    if (isLinkingDialogOpen) {
      fetchAvailableInterviews()
    }
  }, [isLinkingDialogOpen, fetchAvailableInterviews])

  if (isLoading) {
    return (
      <div className="flex min-h-screen flex-col">
        <DashboardHeader />
        <main className="flex-1 p-8 pt-6">
          <div className="flex justify-center p-8">
            <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" />
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
            <Button asChild>
              <Link href="/questionnaires">
                <ChevronLeft className="mr-2 h-4 w-4" />
                Back to Questionnaires
              </Link>
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
            <QuestionnaireForm 
              initialData={questionnaire} 
              onSuccess={() => setIsEditing(false)}
              onUpdate={(updatedData) => {
                setQuestionnaire(prev => prev ? { ...prev, ...updatedData } : null)
              }}
            />
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
                <ChevronLeft className="mr-2 h-4 w-4" />
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
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle>Related Interviews</CardTitle>
                  <CardDescription>
                    Interviews using this questionnaire
                  </CardDescription>
                </div>
                <Dialog open={isLinkingDialogOpen} onOpenChange={setIsLinkingDialogOpen}>
                  <DialogTrigger asChild>
                    <Button>
                      <PlusIcon className="mr-2 h-4 w-4" />
                      Link Interview
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Link an Existing Interview</DialogTitle>
                      <DialogDescription>
                        Select a transcribed interview to use this questionnaire for analysis.
                      </DialogDescription>
                    </DialogHeader>
                    
                    {availableInterviews.length > 0 ? (
                      <>
                        <Select
                          value={selectedInterviewId}
                          onValueChange={setSelectedInterviewId}
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="Select an interview" />
                          </SelectTrigger>
                          <SelectContent>
                            <ScrollArea className="h-60">
                              {availableInterviews.map((interview) => (
                                <SelectItem key={interview.id} value={interview.id}>
                                  {interview.title} - {interview.interviewee_name}
                                </SelectItem>
                              ))}
                            </ScrollArea>
                          </SelectContent>
                        </Select>
                        
                        <DialogFooter>
                          <Button
                            onClick={linkInterview}
                            disabled={!selectedInterviewId || isLinkingInterview}
                          >
                            {isLinkingInterview ? (
                              <>
                                <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-background border-t-transparent" />
                                Linking...
                              </>
                            ) : (
                              "Link Interview"
                            )}
                          </Button>
                        </DialogFooter>
                      </>
                    ) : (
                      <div className="py-4 text-center">
                        <p className="text-muted-foreground mb-2">
                          No available transcribed interviews found to link.
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Only transcribed interviews that are not already using this questionnaire can be linked.
                        </p>
                      </div>
                    )}
                  </DialogContent>
                </Dialog>
              </CardHeader>
              <CardContent>
                {isLoadingInterviews ? (
                  <div className="flex justify-center py-4">
                    <div className="animate-spin h-6 w-6 border-4 border-primary border-t-transparent rounded-full" />
                  </div>
                ) : relatedInterviews.length > 0 ? (
                  <div className="space-y-4">
                    <p className="text-muted-foreground mb-2">
                      This questionnaire is used in {relatedInterviews.length} {relatedInterviews.length === 1 ? 'interview' : 'interviews'}.
                    </p>
                    <div className="border rounded-md divide-y">
                      {relatedInterviews.map((interview) => (
                        <div key={interview.id} className="p-3 hover:bg-muted flex justify-between items-center">
                          <div>
                            <h4 className="font-medium">{interview.title}</h4>
                            <p className="text-sm text-muted-foreground">
                              Interview with {interview.interviewee_name} on {new Date(interview.date).toLocaleDateString()}
                            </p>
                          </div>
                          <Button variant="outline" size="sm" asChild>
                            <Link href={`/interviews/${interview.id}`}>
                              View
                            </Link>
                          </Button>
                        </div>
                      ))}
                    </div>
                  </div>
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