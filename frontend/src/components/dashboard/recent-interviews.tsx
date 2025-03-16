'use client'

import { useState, useEffect } from 'react'
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
import { ArrowRight, FileText, MessageSquare, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { format, formatDistanceToNow } from 'date-fns'
import { Interview, InterviewStatus } from '@/types/interview'
import api from '@/lib/api-client'

export function RecentInterviews() {
  const [interviews, setInterviews] = useState<Interview[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()

  useEffect(() => {
    const fetchInterviews = async () => {
      try {
        setIsLoading(true)
        // Fetch the most recent 5 interviews
        const data = await api.get('/api/interviews?skip=0&limit=5')
        setInterviews(data.items || [])
      } catch (error) {
        console.error('Failed to fetch interviews:', error)
        toast.error('Failed to load recent interviews')
      } finally {
        setIsLoading(false)
      }
    }

    fetchInterviews()
  }, [])

  const getStatusBadge = (status: InterviewStatus) => {
    const baseClasses = "inline-flex items-center rounded-full px-2 py-1 text-xs font-medium";
    
    switch (status) {
      case InterviewStatus.CREATED:
        return <span className={`${baseClasses} bg-gray-100 text-gray-800`}>Created</span>;
      case InterviewStatus.UPLOADED:
        return <span className={`${baseClasses} bg-blue-100 text-blue-800`}>Uploaded</span>;
      case InterviewStatus.PROCESSING:
        return <span className={`${baseClasses} bg-yellow-100 text-yellow-800`}>Processing</span>;
      case InterviewStatus.PROCESSED:
        return <span className={`${baseClasses} bg-indigo-100 text-indigo-800`}>Processed</span>;
      case InterviewStatus.TRANSCRIBING:
        return <span className={`${baseClasses} bg-purple-100 text-purple-800`}>Transcribing</span>;
      case InterviewStatus.TRANSCRIBED:
        return <span className={`${baseClasses} bg-green-100 text-green-800`}>Transcribed</span>;
      case InterviewStatus.ERROR:
        return <span className={`${baseClasses} bg-red-100 text-red-800`}>Error</span>;
      default:
        return <span className={`${baseClasses} bg-gray-100 text-gray-800`}>{status}</span>;
    }
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-40">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (interviews.length === 0) {
    return (
      <div className="text-center py-8">
        <FileText className="h-12 w-12 mx-auto text-muted-foreground mb-3" />
        <h3 className="text-lg font-medium">No interviews yet</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Get started by creating your first interview
        </p>
        <Button asChild>
          <Link href="/interviews/new">Create Interview</Link>
        </Button>
      </div>
    )
  }

  return (
    <div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Title</TableHead>
            <TableHead>Interviewee</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Date</TableHead>
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
                {getStatusBadge(interview.status)}
              </TableCell>
              <TableCell onClick={() => router.push(`/interviews/${interview.id}`)}>
                {formatDistanceToNow(new Date(interview.date), { addSuffix: true })}
              </TableCell>
              <TableCell className="text-right">
                <div className="flex justify-end gap-2">
                  {interview.status === InterviewStatus.TRANSCRIBED && (
                    <Button variant="ghost" size="icon" onClick={() => router.push(`/interviews/${interview.id}/chat`)}>
                      <MessageSquare className="h-4 w-4" />
                      <span className="sr-only">Chat</span>
                    </Button>
                  )}
                  <Button 
                    variant="ghost" 
                    size="icon"
                    onClick={() => router.push(`/interviews/${interview.id}`)}
                  >
                    <ArrowRight className="h-4 w-4" />
                    <span className="sr-only">View</span>
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}