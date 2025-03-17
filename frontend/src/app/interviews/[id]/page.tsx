'use client'

import { useEffect, useState, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { toast } from 'sonner'
import { DashboardHeader } from '@/components/dashboard/dashboard-header'
import { ChatInterface } from '@/components/interview/chat-interface'
import { TranscriptViewer } from '@/components/interview/transcript-viewer'
import { ChevronLeft, PlayCircle, Cog, MessageSquare, FileText } from 'lucide-react'
import { Interview, InterviewStatus } from '@/types/interview'
import Link from 'next/link'
import api from '@/lib/api-client'

export default function InterviewDetailPage() {
  const { id } = useParams()
  const [interview, setInterview] = useState<Interview | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isProcessing, setIsProcessing] = useState(false)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const [selectedSegmentIndex, setSelectedSegmentIndex] = useState<number | undefined>(undefined)
  const router = useRouter()

  const fetchInterview = useCallback(async () => {
    try {
      setIsLoading(true)
      const data = await api.get<Interview>(`/api/interviews/${id}`)
      setInterview(data)
      
      // Check if currently processing
      if (data.status === InterviewStatus.PROCESSING) {
        setIsProcessing(true)
        pollProcessingStatus()
      } else if (data.status === InterviewStatus.TRANSCRIBING) {
        setIsTranscribing(true)
        pollTranscriptionStatus()
      }
    } catch (error) {
      toast.error('Failed to fetch interview details')
    } finally {
      setIsLoading(false)
    }
  }, [id])

  useEffect(() => {
    fetchInterview()
  }, [fetchInterview])

  const pollProcessingStatus = useCallback(() => {
    const interval = setInterval(async () => {
      try {
        const data = await api.get<Interview>(`/api/interviews/${id}`)
        if (data.status !== InterviewStatus.PROCESSING) {
          clearInterval(interval)
          setIsProcessing(false)
          setInterview(data)
        }
      } catch (error) {
        clearInterval(interval)
        setIsProcessing(false)
        toast.error('Error checking processing status')
      }
    }, 5000)

    return () => clearInterval(interval)
  }, [id])

  const pollTranscriptionStatus = useCallback(() => {
    const interval = setInterval(async () => {
      try {
        const data = await api.get<Interview>(`/api/interviews/${id}`)
        if (data.status !== InterviewStatus.TRANSCRIBING) {
          clearInterval(interval)
          setIsTranscribing(false)
          setInterview(data)
        }
      } catch (error) {
        clearInterval(interval)
        setIsTranscribing(false)
        toast.error('Error checking transcription status')
      }
    }, 5000)

    return () => clearInterval(interval)
  }, [id])

  const processAudio = async () => {
    try {
      setIsProcessing(true)
      await api.post(`/api/interviews/${id}/process`)
      toast.success('Audio processing started')
      pollProcessingStatus()
    } catch (error) {
      setIsProcessing(false)
      toast.error('Failed to start audio processing')
    }
  }

  const transcribeAudio = async () => {
    try {
      setIsTranscribing(true)
      await api.post(`/api/interviews/${id}/transcribe`, {
        language: null // Auto-detect language
      })
      toast.success('Transcription started')
      pollTranscriptionStatus()
    } catch (error) {
      setIsTranscribing(false)
      toast.error('Failed to start transcription')
    }
  }

  const generateAnswers = async () => {
    try {
      await api.post(`/api/interviews/${id}/generate-answers`)
      toast.success('Answer generation started')
      fetchInterview()
    } catch (error) {
      toast.error('Failed to start answer generation')
    }
  }

  const handleSegmentClick = (index: number) => {
    setSelectedSegmentIndex(index)
  }

  if (isLoading) {
    return (
      <div className="flex min-h-screen flex-col">
        <DashboardHeader />
        <main className="flex-1 space-y-4 p-8 pt-6">
          <div className="flex justify-center p-8">
            <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full"></div>
          </div>
        </main>
      </div>
    )
  }

  if (!interview) {
    return (
      <div className="flex min-h-screen flex-col">
        <DashboardHeader />
        <main className="flex-1 space-y-4 p-8 pt-6">
          <div className="flex flex-col items-center justify-center p-8">
            <h2 className="text-xl font-semibold mb-4">Interview not found</h2>
            <Button as={Link} href="/interviews">
              <ChevronLeft className="mr-2 h-4 w-4" />
              Back to Interviews
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
            <Button variant="outline" size="sm" asChild className="mb-4">
              <Link href="/interviews">
                <ChevronLeft className="mr-1 h-4 w-4" />
                Back
              </Link>
            </Button>
            <h1 className="text-3xl font-bold">{interview.title}</h1>
            <p className="text-muted-foreground">
              Interview with {interview.interviewee_name} on {new Date(interview.date).toLocaleDateString()}
            </p>
          </div>
          <div className="space-x-2">
            {interview.status === InterviewStatus.UPLOADED && (
              <Button 
                onClick={processAudio} 
                isLoading={isProcessing}
                loadingText="Processing"
              >
                <Cog className="mr-2 h-4 w-4" />
                Process Audio
              </Button>
            )}
            
            {interview.status === InterviewStatus.PROCESSED && (
              <Button 
                onClick={transcribeAudio} 
                isLoading={isTranscribing}
                loadingText="Transcribing"
              >
                <FileText className="mr-2 h-4 w-4" />
                Transcribe
              </Button>
            )}

            {interview.status === InterviewStatus.TRANSCRIBED && !interview.generated_answers && (
              <Button 
                onClick={generateAnswers}
              >
                Generate Answers
              </Button>
            )}
          </div>
        </div>

        <Tabs defaultValue="transcript" className="space-y-4">
          <TabsList>
            <TabsTrigger value="transcript">
              <FileText className="mr-2 h-4 w-4" />
              Transcript
            </TabsTrigger>
            <TabsTrigger value="chat" disabled={!interview.transcription}>
              <MessageSquare className="mr-2 h-4 w-4" />
              Chat
            </TabsTrigger>
          </TabsList>
          <TabsContent value="transcript" className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <TranscriptViewer 
                interviewId={id as string}
                transcriptText={interview.transcription || ''}
                segments={interview.transcript_segments}
                highlightedSegmentIndex={selectedSegmentIndex}
                className="h-[calc(100vh-280px)]"
              />
              
              <div className="space-y-4">
                {interview.generated_answers && Object.keys(interview.generated_answers).length > 0 ? (
                  <div className="border rounded-md p-4 h-[calc(100vh-280px)] overflow-auto">
                    <h3 className="text-lg font-semibold mb-4">Generated Answers</h3>
                    <div className="space-y-6">
                      {Object.entries(interview.generated_answers).map(([question, answer], idx) => (
                        <div key={idx} className="space-y-2">
                          <h4 className="text-md font-medium">{question}</h4>
                          <p className="text-muted-foreground whitespace-pre-line">{answer}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="border rounded-md p-4 h-[calc(100vh-280px)] flex flex-col items-center justify-center">
                    <FileText className="h-16 w-16 text-muted-foreground mb-4" />
                    <h3 className="text-lg font-semibold">No Answers Generated Yet</h3>
                    <p className="text-center text-muted-foreground mt-2 max-w-md">
                      Once you have a transcript, you can generate answers to questionnaire questions.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </TabsContent>
          
          <TabsContent value="chat">
            <div className="grid gap-4 md:grid-cols-2">
              <TranscriptViewer 
                interviewId={id as string}
                transcriptText={interview.transcription || ''}
                segments={interview.transcript_segments}
                highlightedSegmentIndex={selectedSegmentIndex}
                className="h-[calc(100vh-280px)]"
              />
              
              <ChatInterface 
                interviewId={id as string} 
                interviewTitle={interview.title}
                transcriptHighlights={{
                  highlightedText: interview.transcript_segments?.map(s => s.text.substring(0, 60) + '...'),
                  onHighlightClick: handleSegmentClick
                }}
              />
            </div>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}