'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { DashboardHeader } from '@/components/dashboard/dashboard-header'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ChatInterface } from '@/components/interview/chat-interface'
import { TranscriptViewer } from '@/components/interview/transcript-viewer'
import { ChevronLeft, MessageSquare, Loader2, Search } from 'lucide-react'
import { toast } from 'sonner'
import { useChat } from '@/hooks/use-chat'
import { useInterview } from '@/hooks/use-interview'
import { formatTokens } from '@/lib/format'

export default function InterviewChatPage() {
  const { id } = useParams()
  const [selectedSegmentIndex, setSelectedSegmentIndex] = useState<number | undefined>(undefined)
  const router = useRouter()
  
  const { interview, isLoading } = useInterview({ id: id as string })
  const { messages, transcriptMatches, searchTranscript, remainingTokens } = useChat({ 
    interviewId: id as string,
    onError: (error) => {
      if (error.response?.status === 402) {
        toast.error('You have run out of chat tokens for this interview', {
          action: {
            label: 'Buy Tokens',
            onClick: () => router.push('/credits')
          }
        })
      }
    }
  })

  useEffect(() => {
    // Check if transcript is available
    if (interview && !interview.transcription) {
      toast.error('This interview has not been transcribed yet', {
        action: {
          label: 'Go Back',
          onClick: () => router.push(`/interviews/${id}`)
        }
      })
    }
  }, [interview, id, router])

  if (isLoading) {
    return (
      <div className="flex min-h-screen flex-col">
        <DashboardHeader />
        <main className="flex-1 p-8 pt-6">
          <div className="flex justify-center p-8">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        </main>
      </div>
    )
  }

  if (!interview || !interview.transcription) {
    return (
      <div className="flex min-h-screen flex-col">
        <DashboardHeader />
        <main className="flex-1 p-8 pt-6">
          <div className="flex flex-col items-center justify-center p-8">
            <div className="rounded-full bg-muted p-3 mb-4">
              <MessageSquare className="h-10 w-10 text-muted-foreground" />
            </div>
            <h2 className="text-xl font-semibold mb-2">Interview Not Ready for Chat</h2>
            <p className="text-center text-muted-foreground mb-6 max-w-md">
              This interview hasn't been transcribed yet or couldn't be found.
              Please transcribe the interview before using the chat feature.
            </p>
            <Button asChild>
              <Link href={`/interviews/${id}`}>
                Go to Interview
              </Link>
            </Button>
          </div>
        </main>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen flex-col">
      <DashboardHeader />
      
      <main className="flex-1 p-8 pt-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <Button variant="outline" size="sm" asChild className="mb-2">
              <Link href={`/interviews/${id}`}>
                <ChevronLeft className="mr-1 h-4 w-4" />
                Back to Interview
              </Link>
            </Button>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold">{interview.title}</h1>
              <Badge variant="outline" className="ml-2">
                {formatTokens(interview.remaining_chat_tokens || 0)} tokens
              </Badge>
            </div>
            <p className="text-muted-foreground">
              Chat with the interview transcript to extract insights
            </p>
          </div>
        </div>
        
        <div className="grid gap-4 lg:grid-cols-2">
          <TranscriptViewer 
            interviewId={id as string}
            transcriptText={interview.transcription}
            segments={interview.transcript_segments}
            highlightedSegmentIndex={selectedSegmentIndex}
            onSegmentClick={(segment, index) => {
              setSelectedSegmentIndex(index)
              searchTranscript(segment.text, 3)
            }}
            className="h-[calc(100vh-220px)]"
          />
          
          <ChatInterface 
            interviewId={id as string} 
            interviewTitle={interview.title}
            transcriptHighlights={{
              highlightedText: transcriptMatches?.map(m => m.text.substring(0, 60) + '...') || [],
              onHighlightClick: (index) => {
                // Find corresponding segment index in full transcript
                const matchText = transcriptMatches?.[index]?.text
                const segmentIndex = interview.transcript_segments?.findIndex(s => s.text.includes(matchText || ''))
                setSelectedSegmentIndex(segmentIndex)
              }
            }}
          />
        </div>
      </main>
    </div>
  )
}