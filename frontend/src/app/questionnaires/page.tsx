'use client'

import { useEffect, useState, useCallback } from 'react'
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
import { Card, CardContent } from '@/components/ui/card'
import { PlusIcon, FileText, Edit, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { DashboardHeader } from '@/components/dashboard/dashboard-header'
import { formatDistanceToNow } from 'date-fns'
import api from '@/lib/api-client'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"

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
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const router = useRouter()

  const fetchQuestionnaires = useCallback(async () => {
    try {
      setIsLoading(true)
      const data = await api.get<Questionnaire[]>('/questionnaires')
      setQuestionnaires(data)
    } catch (error) {
      toast.error('Failed to fetch questionnaires')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchQuestionnaires()
  }, [fetchQuestionnaires])

  const handleDelete = async () => {
    if (!deleteTarget) return

    try {
      setIsDeleting(true)
      await api.delete(`/questionnaires/${deleteTarget}`)
      toast.success('Questionnaire deleted successfully')
      
      // Remove the deleted questionnaire from the state
      setQuestionnaires(questionnaires.filter(q => q.id !== deleteTarget))
      setDeleteTarget(null)
    } catch (error: unknown) {
      if (error instanceof Error && error.message?.includes('associated interviews')) {
        toast.error('Cannot delete questionnaire with associated interviews')
      } else {
        toast.error('Failed to delete questionnaire')
      }
      console.error('Delete error:', error)
    } finally {
      setIsDeleting(false)
    }
  }

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
                    <TableCell className="text-right flex justify-end space-x-1">
                      <Button 
                        variant="ghost" 
                        size="icon"
                        onClick={() => router.push(`/questionnaires/${questionnaire.id}`)}
                      >
                        <Edit className="h-4 w-4" />
                        <span className="sr-only">Edit</span>
                      </Button>
                      <Dialog>
                        <DialogTrigger asChild>
                          <Button 
                            variant="ghost" 
                            size="icon"
                            onClick={(e) => {
                              e.stopPropagation();
                              setDeleteTarget(questionnaire.id);
                            }}
                            className="hover:bg-red-100 hover:text-red-500"
                          >
                            <Trash2 className="h-4 w-4" />
                            <span className="sr-only">Delete</span>
                          </Button>
                        </DialogTrigger>
                        <DialogContent className="sm:max-w-md">
                          <DialogHeader>
                            <DialogTitle>Delete Questionnaire</DialogTitle>
                            <DialogDescription>
                              {questionnaire.interview_count > 0 
                                ? `This questionnaire is associated with ${questionnaire.interview_count} interview(s) and cannot be deleted.` 
                                : "Are you sure you want to delete this questionnaire? This action cannot be undone."}
                            </DialogDescription>
                          </DialogHeader>
                          <DialogFooter className="mt-4 gap-2 sm:justify-start">
                            <DialogClose asChild>
                              <Button type="button" variant="secondary">
                                Cancel
                              </Button>
                            </DialogClose>
                            <Button 
                              type="button" 
                              variant="destructive" 
                              onClick={handleDelete}
                              disabled={isDeleting || questionnaire.interview_count > 0}
                            >
                              {isDeleting ? 'Deleting...' : 'Delete'}
                            </Button>
                          </DialogFooter>
                        </DialogContent>
                      </Dialog>
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