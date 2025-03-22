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
import { PlusIcon, FileCog, FileAudio, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { DashboardHeader } from '@/components/dashboard/dashboard-header'
import { formatDistanceToNow } from 'date-fns'
import { Interview, InterviewStatus } from '@/types/interview'
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

export default function InterviewsPage() {
  const [interviews, setInterviews] = useState<Interview[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const router = useRouter()

  const fetchInterviews = useCallback(async () => {
    try {
      setIsLoading(true)
      const data = await api.get<{items: Interview[]}>('/interviews/')
      setInterviews(data.items || [])
    } catch (error) {
      toast.error('Failed to fetch interviews')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchInterviews()
  }, [fetchInterviews])

  const handleDelete = async (id: string) => {
    if (!id) return;

    try {
      console.log(`Attempting to delete interview with ID: ${id}`);
      setIsDeleting(true);
      
      // Make the delete request
      const response = await api.delete(`/interviews/${id}`);
      console.log('Delete interview response:', response);
      
      toast.success('Interview deleted successfully');
      
      // Remove the deleted interview from the state
      setInterviews(interviews.filter(interview => interview.id !== id));
      setDeleteTarget(null);
    } catch (error) {
      console.error('Delete interview error:', error);
      let errorMessage = 'Unknown error occurred';
      
      if (error instanceof Error) {
        errorMessage = error.message;
      }
      
      toast.error(`Failed to delete interview: ${errorMessage}`);
    } finally {
      setIsDeleting(false);
    }
  }

  const getStatusBadge = (status: InterviewStatus) => {
    const baseClasses = "inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset";
    
    switch (status) {
      case InterviewStatus.CREATED:
        return <span className={`${baseClasses} bg-gray-50 text-gray-600 ring-gray-500/10`}>Created</span>;
      case InterviewStatus.UPLOADED:
        return <span className={`${baseClasses} bg-blue-50 text-blue-700 ring-blue-700/10`}>Uploaded</span>;
      case InterviewStatus.PROCESSING:
        return <span className={`${baseClasses} bg-yellow-50 text-yellow-800 ring-yellow-600/20`}>Processing</span>;
      case InterviewStatus.PROCESSED:
        return <span className={`${baseClasses} bg-indigo-50 text-indigo-700 ring-indigo-700/10`}>Processed</span>;
      case InterviewStatus.TRANSCRIBING:
        return <span className={`${baseClasses} bg-purple-50 text-purple-700 ring-purple-700/10`}>Transcribing</span>;
      case InterviewStatus.TRANSCRIBED:
        return <span className={`${baseClasses} bg-green-50 text-green-700 ring-green-600/20`}>Transcribed</span>;
      case InterviewStatus.ERROR:
        return <span className={`${baseClasses} bg-red-50 text-red-700 ring-red-600/10`}>Error</span>;
      default:
        return <span className={`${baseClasses} bg-gray-50 text-gray-600 ring-gray-500/10`}>{status}</span>;
    }
  };

  return (
    <div className="flex min-h-screen flex-col">
      <DashboardHeader />
      
      <main className="flex-1 space-y-4 p-8 pt-6">
        <div className="flex items-center justify-between">
          <h2 className="text-3xl font-bold tracking-tight">Interviews</h2>
          <Link href="/interviews/new">
            <Button>
              <PlusIcon className="mr-2 h-4 w-4" />
              New Interview
            </Button>
          </Link>
        </div>
        
        {isLoading ? (
          <div className="flex justify-center p-8">
            <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" />
          </div>
        ) : interviews.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <div className="rounded-full bg-muted p-3">
                <FileAudio className="h-10 w-10 text-muted-foreground" />
              </div>
              <h3 className="mt-4 text-lg font-semibold">No interviews found</h3>
              <p className="mt-2 text-center text-sm text-muted-foreground max-w-sm">
                You haven't created any interviews yet. Get started by creating your first interview.
              </p>
              <Link href="/interviews/new" className="mt-4">
                <Button>
                  <PlusIcon className="mr-2 h-4 w-4" />
                  Create your first interview
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
                  <TableHead>Interviewee</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last Updated</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {interviews.map((interview) => (
                  <TableRow key={interview.id} className="cursor-pointer hover:bg-muted/50">
                    <TableCell className="font-medium" onClick={() => router.push(`/interviews/${interview.id}`)}>
                      {interview.title}
                    </TableCell>
                    <TableCell onClick={() => router.push(`/interviews/${interview.id}`)}>
                      {interview.interviewee_name}
                    </TableCell>
                    <TableCell onClick={() => router.push(`/interviews/${interview.id}`)}>
                      {new Date(interview.date).toLocaleDateString()}
                    </TableCell>
                    <TableCell onClick={() => router.push(`/interviews/${interview.id}`)}>
                      {getStatusBadge(interview.status)}
                    </TableCell>
                    <TableCell onClick={() => router.push(`/interviews/${interview.id}`)}>
                      {interview.updated_at 
                        ? formatDistanceToNow(new Date(interview.updated_at), { addSuffix: true })
                        : formatDistanceToNow(new Date(interview.created_at), { addSuffix: true })}
                    </TableCell>
                    <TableCell className="text-right flex justify-end space-x-1">
                      <Button 
                        variant="ghost" 
                        size="icon"
                        onClick={() => router.push(`/interviews/${interview.id}`)}
                      >
                        <FileCog className="h-4 w-4" />
                        <span className="sr-only">Open</span>
                      </Button>
                      <Dialog>
                        <DialogTrigger asChild>
                          <Button 
                            variant="ghost" 
                            size="icon"
                            onClick={(e) => {
                              e.stopPropagation();
                              setDeleteTarget(interview.id);
                            }}
                            className="hover:bg-red-100 hover:text-red-500"
                          >
                            <Trash2 className="h-4 w-4" />
                            <span className="sr-only">Delete</span>
                          </Button>
                        </DialogTrigger>
                        <DialogContent className="sm:max-w-md">
                          <DialogHeader>
                            <DialogTitle>Delete Interview</DialogTitle>
                            <DialogDescription>
                              Are you sure you want to delete this interview? This action cannot be undone.
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
                              onClick={() => handleDelete(interview.id)}
                              disabled={isDeleting}
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