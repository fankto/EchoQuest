'use client'

import { useEffect, useState, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { toast } from 'sonner'
import { DashboardHeader } from '@/components/dashboard/dashboard-header'
import { ChatInterface } from '@/components/interview/chat-interface'
import { TranscriptViewer } from '@/components/interview/transcript-viewer'
import { ChevronLeft, PlayCircle, Cog, MessageSquare, FileText, ListIcon } from 'lucide-react'
import { Interview, InterviewStatus } from '@/types/interview'
import Link from 'next/link'
import api from '@/lib/api-client'
import { AudioPlayer } from '@/components/interview/audio-player'
import type { TranscriptSegment } from '@/components/interview/transcript-viewer'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

export default function InterviewDetailPage() {
  const { id } = useParams()
  const [interview, setInterview] = useState<Interview | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isProcessing, setIsProcessing] = useState(false)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const [selectedSegmentIndex, setSelectedSegmentIndex] = useState<number | undefined>(undefined)
  const [selectedSegment, setSelectedSegment] = useState<TranscriptSegment | null>(null)
  const [audioUrl, setAudioUrl] = useState<string | undefined>(undefined)
  const [currentTime, setCurrentTime] = useState(0)
  const router = useRouter()
  const [questionnaires, setQuestionnaires] = useState<Array<{id: string, title: string}>>([])
  const [selectedQuestionnaireId, setSelectedQuestionnaireId] = useState<string>("")
  const [isQuestionnaireDialogOpen, setIsQuestionnaireDialogOpen] = useState(false)
  const [isAttachingQuestionnaire, setIsAttachingQuestionnaire] = useState(false)

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
      
      // Get audio URL if available - for any interview with uploaded files
      if (data.status !== InterviewStatus.CREATED) {
        try {
          const audioData = await api.get<{audio_url: string, is_processed: boolean}>(`/api/interviews/${id}/audio`)
          if (audioData && audioData.audio_url) {
            // Ensure the URL is absolute and points to the backend
            let url = audioData.audio_url;
            // Make sure to use the backend URL as base
            const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
            if (url.startsWith('/')) {
              url = `${baseUrl}${url}`;
            }
            console.log("Setting audio URL:", url);
            setAudioUrl(url);
          }
        } catch (error) {
          console.error('Failed to fetch audio URL:', error)
        }
      }
    } catch (error) {
      toast.error('Failed to fetch interview details')
    } finally {
      setIsLoading(false)
    }
  }, [id])

  const fetchQuestionnaires = useCallback(async () => {
    try {
      const data = await api.get('/api/questionnaires')
      if (data && data.items) {
        setQuestionnaires(data.items)
      }
    } catch (error) {
      console.error('Failed to fetch questionnaires:', error)
    }
  }, [])

  useEffect(() => {
    fetchInterview()
    fetchQuestionnaires()
  }, [id, fetchInterview, fetchQuestionnaires])

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

  const attachQuestionnaire = async () => {
    if (!selectedQuestionnaireId) {
      toast.error('Please select a questionnaire')
      return
    }

    try {
      setIsAttachingQuestionnaire(true)
      const formData = new FormData()
      formData.append('questionnaire_id', selectedQuestionnaireId)
      
      await api.upload(`/api/interviews/${id}/attach-questionnaire`, formData)
      toast.success('Questionnaire attached successfully')
      
      // Refresh interview data
      await fetchInterview()
      
      // Close dialog
      setIsQuestionnaireDialogOpen(false)
    } catch (error) {
      toast.error('Failed to attach questionnaire')
    } finally {
      setIsAttachingQuestionnaire(false)
    }
  }

  const handleSegmentClick = (segment: TranscriptSegment, index: number) => {
    // Check if this is a clear segment request (from switching to full transcript)
    if (index === -1 && segment.text === '' && segment.words?.length === 0) {
      console.log('Clearing segment selection');
      setSelectedSegmentIndex(undefined);
      setSelectedSegment(null);
      return;
    }
    
    console.log(`Interview page: Segment ${index} clicked:`, segment);
    
    // Create a copy of the segment to preserve the original data
    const updatedSegment = { ...segment };
    
    // Ensure we have valid start_time - critical for proper audio sync
    if (updatedSegment.start_time === undefined) {
      console.warn("Missing start_time in segment, defaulting to 0");
      updatedSegment.start_time = 0;
    }
    
    // IMPORTANT: We want to use the original transcript timing
    // Don't modify the segment times - use them exactly as provided
    console.log(`Using original segment timestamps: ${updatedSegment.start_time.toFixed(3)} - ${updatedSegment.end_time.toFixed(3)}`);
    console.log(`Segment duration: ${(updatedSegment.end_time - updatedSegment.start_time).toFixed(3)}s, Text: "${updatedSegment.text}"`);
    
    // Only extend very short segments to ensure minimal playback time
    const minDuration = 0.5; // Half a second minimum
    if (updatedSegment.end_time - updatedSegment.start_time < minDuration) {
      console.log(`Segment too short, extending to minimum duration of ${minDuration}s`);
      updatedSegment.end_time = updatedSegment.start_time + minDuration;
    }
    
    // Update the UI state - critical to do BOTH of these
    setSelectedSegmentIndex(index);
    setSelectedSegment(updatedSegment);
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
            <Button asChild>
              <Link href="/interviews">
                <ChevronLeft className="mr-2 h-4 w-4" />
                Back to Interviews
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
                disabled={isProcessing}
              >
                {isProcessing ? (
                  <>
                    <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"></div>
                    Processing
                  </>
                ) : (
                  <>
                    <PlayCircle className="mr-2 h-4 w-4" />
                    Process Audio
                  </>
                )}
              </Button>
            )}
            
            {interview.status === InterviewStatus.PROCESSED && (
              <Button 
                onClick={transcribeAudio} 
                disabled={isTranscribing}
              >
                {isTranscribing ? (
                  <>
                    <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"></div>
                    Transcribing
                  </>
                ) : (
                  <>
                    <FileText className="mr-2 h-4 w-4" />
                    Transcribe
                  </>
                )}
              </Button>
            )}

            {interview.status === InterviewStatus.TRANSCRIBED && (
              <>
                <Dialog open={isQuestionnaireDialogOpen} onOpenChange={setIsQuestionnaireDialogOpen}>
                  <DialogTrigger asChild>
                    <Button variant="outline">
                      <ListIcon className="mr-2 h-4 w-4" />
                      {interview.questionnaire ? 'Change Questionnaire' : 'Add Questionnaire'}
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>{interview.questionnaire ? 'Change Questionnaire' : 'Add Questionnaire'}</DialogTitle>
                      <DialogDescription>
                        {interview.questionnaire 
                          ? 'Select a different questionnaire for this interview' 
                          : 'Select a questionnaire to analyze this interview'}
                      </DialogDescription>
                    </DialogHeader>
                    
                    <div className="space-y-4 py-4">
                      <div className="space-y-2">
                        <Select 
                          onValueChange={(value) => setSelectedQuestionnaireId(value)}
                          defaultValue={interview.questionnaire_id || ""}
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="Select a questionnaire" />
                          </SelectTrigger>
                          <SelectContent>
                            {questionnaires.map((q) => (
                              <SelectItem key={q.id} value={q.id}>{q.title}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      
                      <div className="flex justify-end">
                        <Button 
                          onClick={attachQuestionnaire} 
                          disabled={isAttachingQuestionnaire}
                        >
                          {isAttachingQuestionnaire ? (
                            <>
                              <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"></div>
                              Saving...
                            </>
                          ) : (
                            'Save'
                          )}
                        </Button>
                      </div>
                    </div>
                  </DialogContent>
                </Dialog>
                
                {interview.questionnaire && !interview.generated_answers && (
                  <Button 
                    onClick={generateAnswers}
                  >
                    Generate Answers
                  </Button>
                )}
              </>
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
              {audioUrl && (
                <div className="flex flex-col">
                  <h3 className="text-lg font-medium mb-2">Audio</h3>
                  <AudioPlayer 
                    src={audioUrl}
                    title={interview.title}
                    onTimeUpdate={setCurrentTime}
                    currentSegment={selectedSegment || undefined}
                    className="w-full"
                  />
                </div>
              )}
              
              <TranscriptViewer 
                interviewId={id as string}
                transcriptText={(interview?.transcription) || ''}
                segments={interview?.transcript_segments || []}
                highlightedSegmentIndex={selectedSegmentIndex}
                audioUrl={audioUrl}
                onSegmentClick={handleSegmentClick}
                currentTime={currentTime}
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
                    <h3 className="text-lg font-semibold">{interview.questionnaire ? 'No Answers Generated Yet' : 'No Questionnaire Selected'}</h3>
                    <p className="text-center text-muted-foreground mt-2 max-w-md">
                      {interview.questionnaire 
                        ? 'Click "Generate Answers" to analyze the transcript with your questionnaire.'
                        : 'Add a questionnaire to generate answers based on the transcript.'}
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
                transcriptText={interview?.transcription || ''}
                segments={interview?.transcript_segments || []}
                highlightedSegmentIndex={selectedSegmentIndex}
                audioUrl={audioUrl}
                className="h-[calc(100vh-280px)]"
              />
              
              <ChatInterface 
                interviewId={id as string} 
                interviewTitle={interview.title}
                transcriptHighlights={{
                  highlightedText: interview?.transcript_segments?.map(s => s.text.substring(0, 60) + '...'),
                  onHighlightClick: (index: number) => {
                    if (interview?.transcript_segments?.[index]) {
                      handleSegmentClick(interview.transcript_segments[index], index);
                    }
                  }
                }}
              />
            </div>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}