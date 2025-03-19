'use client'

import { useEffect, useState, useCallback } from 'react'
import { useParams } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { toast } from 'sonner'
import { DashboardHeader } from '@/components/dashboard/dashboard-header'
import { ChatInterface } from '@/components/interview/chat-interface'
import { TranscriptViewer } from '@/components/interview/transcript-viewer'
import { ChevronLeft, PlayCircle, MessageSquare, FileText, ListIcon, PlusIcon, ClipboardList } from 'lucide-react'
import Link from 'next/link'
import api from '@/lib/api-client'
import { AudioPlayer } from '@/components/interview/audio-player'

// Type imports
import type { TranscriptSegment } from '@/components/interview/transcript-viewer'
import type { Interview as InterviewType } from '@/types/interview'
// Value imports
import { InterviewStatus } from '@/types/interview'
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
import { Badge } from '@/components/ui/badge'

// Helper component to only render children when needed
type LazyLoadComponentProps = {
  children: React.ReactNode;
  check: boolean;
}

function LazyLoadComponent({ children, check }: LazyLoadComponentProps) {
  if (!check) return null;
  return <>{children}</>;
}

export default function InterviewDetailPage() {
  const { id } = useParams()
  const [interview, setInterview] = useState<InterviewType | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isProcessing, setIsProcessing] = useState(false)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const [selectedSegmentIndex, setSelectedSegmentIndex] = useState<number | undefined>(undefined)
  const [selectedSegment, setSelectedSegment] = useState<TranscriptSegment | null>(null)
  const [audioUrl, setAudioUrl] = useState<string | undefined>(undefined)
  const [currentTime, setCurrentTime] = useState(0)
  const [questionnaires, setQuestionnaires] = useState<Array<{id: string, title: string}>>([])
  const [selectedQuestionnaireId, setSelectedQuestionnaireId] = useState<string>("")
  const [isQuestionnaireDialogOpen, setIsQuestionnaireDialogOpen] = useState(false)
  const [isAttachingQuestionnaire, setIsAttachingQuestionnaire] = useState(false)
  const [isGeneratingAnswers, setIsGeneratingAnswers] = useState<Record<string, boolean>>({})

  const fetchInterview = useCallback(async () => {
    try {
      setIsLoading(true)
      console.log("Fetching interview data for ID:", id)
      
      // Get the interview data
      const data = await api.get<InterviewType>(`/api/interviews/${id}`)
      console.log("Received interview data:", data)
      console.log("Questionnaire relationship:", data.questionnaire ? 'Questionnaire object present' : 'No questionnaire object')
      console.log("Questionnaire ID:", data.questionnaire_id || 'None')
      console.log("Questionnaires array:", data.questionnaires || 'Not present')
      
      // Check if questionnaire is attached
      if (data.questionnaire_id) {
        console.log("Interview has questionnaire attached with ID:", data.questionnaire_id)
        
        // If we have a new questionnaire ID selected, update it
        if (data.questionnaire_id !== selectedQuestionnaireId && data.questionnaire_id) {
          setSelectedQuestionnaireId(data.questionnaire_id)
        }
      } else {
        console.log("No questionnaire attached to this interview")
      }
      
      // Update the interview state
      setInterview(data)
      
      // Check if currently processing
      if (data.status === InterviewStatus.PROCESSING) {
        setIsProcessing(true)
        startPollingProcessingStatus(data.id)
      } else if (data.status === InterviewStatus.TRANSCRIBING) {
        setIsTranscribing(true)
        startPollingTranscriptionStatus(data.id)
      }
      
      // Get audio URL if available - for any interview with uploaded files
      if (data.status !== InterviewStatus.CREATED) {
        try {
          const audioData = await api.get<{audio_url: string, is_processed: boolean}>(`/api/interviews/${id}/audio`)
          if (audioData?.audio_url) {
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
      console.error('Failed to fetch interview details:', error)
      toast.error('Failed to fetch interview details')
    } finally {
      setIsLoading(false)
    }
  }, [id, selectedQuestionnaireId])

  const fetchQuestionnaires = useCallback(async () => {
    try {
      console.log("Fetching questionnaires...")
      const data = await api.get<Array<{id: string, title: string}>>('/api/questionnaires')
      console.log("Received questionnaires data:", data)
      if (data) {
        setQuestionnaires(data)
        console.log("Set questionnaires state to:", data)
      }
    } catch (error) {
      console.error('Failed to fetch questionnaires:', error)
    }
  }, [])

  // Function to start polling for processing status
  const startPollingProcessingStatus = useCallback((interviewId: string) => {
    const interval = setInterval(async () => {
      try {
        const data = await api.get<InterviewType>(`/api/interviews/${interviewId}`)
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
  }, [])

  // Function to start polling for transcription status
  const startPollingTranscriptionStatus = useCallback((interviewId: string) => {
    const interval = setInterval(async () => {
      try {
        const data = await api.get<InterviewType>(`/api/interviews/${interviewId}`)
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
  }, [])
  
  useEffect(() => {
    // Fetch interview data and questionnaires when component mounts
    const loadData = async () => {
      await fetchInterview()
      await fetchQuestionnaires()
    }
    
    loadData()

    // Cleanup function will be called on unmount
    return () => {
      // No cleanup needed for the initial fetch
    }
  }, [fetchInterview, fetchQuestionnaires])
  
  // Separate useEffect for polling status changes
  useEffect(() => {
    if (!interview) return
    
    let cleanup: (() => void) | undefined
    
    if (interview.status === InterviewStatus.PROCESSING) {
      cleanup = startPollingProcessingStatus(interview.id)
    } else if (interview.status === InterviewStatus.TRANSCRIBING) {
      cleanup = startPollingTranscriptionStatus(interview.id)
    }
    
    return () => {
      if (cleanup) cleanup()
    }
  }, [interview, startPollingProcessingStatus, startPollingTranscriptionStatus])

  const processAudio = async () => {
    try {
      setIsProcessing(true)
      await api.post(`/api/interviews/${id}/process`)
      toast.success('Audio processing started')
      startPollingProcessingStatus(id as string)
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
      startPollingTranscriptionStatus(id as string)
    } catch (error) {
      setIsTranscribing(false)
      toast.error('Failed to start transcription')
    }
  }

  const generateAnswers = async (questionnaireId?: string) => {
    try {
      // Use the questionnaire ID if provided, otherwise generate for all questionnaires
      const targetId = questionnaireId || undefined
      
      // Set the loading state for this questionnaire
      if (targetId) {
        setIsGeneratingAnswers(prev => ({ ...prev, [targetId]: true }))
      } else {
        setIsLoading(true)
      }
      
      // Call the API with the questionnaire ID if specified
      const endpoint = targetId 
        ? `/api/interviews/${id}/generate-answers?questionnaire_id=${targetId}`
        : `/api/interviews/${id}/generate-answers`
        
      await api.post(endpoint)
      
      toast.success('Answer generation started')
      
      // Start polling for answer generation completion with better error handling
      let pollingAttempts = 0;
      const maxPollingAttempts = 24; // 2 minutes with 5s intervals
      const pollDelay = 5000; // 5 seconds between polls
      
      // Function for a single poll attempt
      const pollOnce = async () => {
        try {
          pollingAttempts++;
          console.log(`Polling attempt ${pollingAttempts}/${maxPollingAttempts}`);
          
          const updatedData = await api.get<InterviewType>(`/api/interviews/${id}`);
          
          // Check if the generation completed
          if (updatedData) {
            const generatedAnswers = updatedData.generated_answers || {};
            let hasAnswers = false;
            
            // Check if we have answers for the specific questionnaire
            if (targetId && generatedAnswers[targetId]) {
              hasAnswers = true;
            } 
            // For bulk generation, check if we have answers for any questionnaire
            else if (!targetId && Object.keys(generatedAnswers).length > 0) {
              hasAnswers = true;
            }
            
            if (hasAnswers) {
              // Generation complete
              setInterview(updatedData);
              if (targetId) {
                setIsGeneratingAnswers(prev => ({ ...prev, [targetId]: false }));
              } else {
                setIsLoading(false);
              }
              toast.success('Answers generated successfully');
              return true;
            }
          }
          return false;
        } catch (error) {
          console.error('Error polling for answer generation:', error);
          return false;
        }
      };
      
      // Start polling
      const doPoll = async () => {
        // If we've reached the max attempts, stop polling
        if (pollingAttempts >= maxPollingAttempts) {
          if (targetId) {
            setIsGeneratingAnswers(prev => ({ ...prev, [targetId]: false }));
          } else {
            setIsLoading(false);
          }
          // Try one final fetch
          await fetchInterview();
          return;
        }
        
        // Attempt a poll
        const success = await pollOnce();
        
        // If successful, we're done
        if (success) return;
        
        // Otherwise, schedule the next poll
        setTimeout(doPoll, pollDelay);
      };
      
      // Start the polling process
      doPoll();
      
    } catch (error) {
      console.error('Failed to generate answers:', error);
      toast.error('Failed to start answer generation');
      if (questionnaireId) {
        setIsGeneratingAnswers(prev => ({ ...prev, [questionnaireId]: false }));
      } else {
        setIsLoading(false);
      }
      
      // Try to fetch the latest interview state even after error
      setTimeout(async () => {
        try {
          await fetchInterview();
        } catch (fetchError) {
          console.error('Failed to fetch interview after error:', fetchError);
        }
      }, 2000);
    }
  }

  const attachQuestionnaire = async () => {
    if (!selectedQuestionnaireId) {
      toast.error('Please select a questionnaire')
      return
    }

    try {
      setIsAttachingQuestionnaire(true)
      
      // Create FormData object
      const formData = new FormData()
      formData.append('questionnaire_id', selectedQuestionnaireId)
      
      // Log before we send the request
      console.log('Attaching questionnaire:', selectedQuestionnaireId, 'to interview:', id)
      
      // Send the request
      const response = await api.upload(`/api/interviews/${id}/attach-questionnaire`, formData)
      console.log('Attach questionnaire response:', response)
      
      toast.success('Questionnaire attached successfully')
      
      // Force a re-fetch of the interview to refresh the data
      await fetchInterview()
      
      // Add a second fetch after a short delay to ensure the relationship has been fully processed
      setTimeout(async () => {
        await fetchInterview()
        console.log('Delayed fetch completed')
      }, 1000)
      
      // Close dialog only on success
      setIsQuestionnaireDialogOpen(false)
    } catch (error) {
      console.error('Error attaching questionnaire:', error)
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

  // 1. Add a function to fetch questionnaire details by ID
  const fetchQuestionnaireById = useCallback(async (questionnaireId: string) => {
    if (!questionnaireId) return;
    
    try {
      console.log(`Fetching details for questionnaire ID: ${questionnaireId}`);
      const data = await api.get<{id: string, title: string, questions: string[]}>(`/api/questionnaires/${questionnaireId}`);
      
      // Update the interview state with the fetched questionnaire
      setInterview(prev => {
        if (!prev) return prev;
        
        // Check if we already have questionnaires array
        const existingQuestionnaires = prev.questionnaires || [];
        
        // Check if this questionnaire is already in the array
        const exists = existingQuestionnaires.some(q => q.id === data.id);
        
        // If it's not in the array, add it
        if (!exists) {
          const updatedQuestionnaires = [
            ...existingQuestionnaires,
            {
              id: data.id,
              title: data.title,
              questions: data.questions
            }
          ];
          
          return {
            ...prev,
            questionnaires: updatedQuestionnaires,
            // Also keep backward compatibility
            questionnaire: prev.questionnaire_id === data.id ? {
              id: data.id,
              title: data.title,
              questions: data.questions
            } : prev.questionnaire
          } as InterviewType;
        }
        
        return prev;
      });
      
      console.log(`Questionnaire details fetched successfully: ${data.title}`);
    } catch (error) {
      console.error(`Failed to fetch questionnaire details: ${error}`);
    }
  }, []);

  // Fetch all questionnaires attached to the interview
  const fetchAttachedQuestionnaires = useCallback(async () => {
    if (!interview?.id) return;
    
    try {
      // For backward compatibility, fetch the questionnaire from the questionnaire_id field
      if (interview.questionnaire_id && !interview.questionnaire) {
        await fetchQuestionnaireById(interview.questionnaire_id);
      }
      
      // Now, let's fetch all questionnaires from the many-to-many relationship
      // We'll use the existing fetchInterview data, but we should make sure
      // that we've properly decoded any questionnaire data that's returned
      
      if (interview.questionnaires) {
        // If we already have questionnaires in the array, make sure they all have details
        for (const q of interview.questionnaires) {
          if (!q.questions) {
            await fetchQuestionnaireById(q.id);
          }
        }
      }
      
      // In the future, we could add a specific API endpoint to fetch all attached questionnaires
      // For now we're relying on the interview API response containing the right data
    } catch (error) {
      console.error(`Failed to fetch attached questionnaires: ${error}`);
    }
  }, [interview?.id, interview?.questionnaire_id, interview?.questionnaire, interview?.questionnaires, fetchQuestionnaireById]);

  // 2. Update the useEffect to fetch questionnaire details when needed
  useEffect(() => {
    fetchAttachedQuestionnaires();
  }, [fetchAttachedQuestionnaires]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen flex-col">
        <DashboardHeader />
        <main className="flex-1 space-y-4 p-8 pt-6">
          <div className="flex justify-center p-8">
            <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full" />
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
        <div className="flex items-center justify-between mb-4">
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
        </div>

        {/* Action buttons - Always visible at the top */}
        <div className="mb-6 flex justify-end gap-2">
          {interview.status === InterviewStatus.UPLOADED && (
            <Button 
              onClick={processAudio} 
              disabled={isProcessing}
            >
              {isProcessing ? (
                <>
                  <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                  Processing Audio...
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
                  <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                  Transcribing...
                </>
              ) : (
                <>
                  <FileText className="mr-2 h-4 w-4" />
                  Transcribe Audio
                </>
              )}
            </Button>
          )}
        </div>

        {/* Simplified Interview Status Indicator - Optional and less prominent */}
        <div className="mb-6 text-sm text-muted-foreground">
          <Badge variant={interview.status === InterviewStatus.UPLOADED ? 'default' : 'outline'}>
            {interview.status === InterviewStatus.UPLOADED ? 'Audio Uploaded' : 'Uploaded'}
          </Badge>
          {' → '}
          <Badge variant={interview.status === InterviewStatus.PROCESSED ? 'default' : 'outline'}>
            {interview.status === InterviewStatus.PROCESSED ? 'Audio Processed' : 'Processed'}
          </Badge>
          {' → '}
          <Badge variant={interview.status === InterviewStatus.TRANSCRIBED ? 'default' : 'outline'}>
            {interview.status === InterviewStatus.TRANSCRIBED ? 'Transcribed' : 'Transcribe'}
          </Badge>
          {interview.questionnaire && (
            <>
              {' → '}
              <Badge variant='default' className="bg-primary">
                Questionnaire Attached
              </Badge>
            </>
          )}
          {interview.generated_answers && Object.keys(interview.generated_answers).length > 0 && (
            <>
              {' → '}
              <Badge variant='default' className="bg-green-500">
                Answers Generated
              </Badge>
            </>
          )}
        </div>

        {/* Questionnaire Section - Displays all attached questionnaires */}
        {interview.status === InterviewStatus.TRANSCRIBED && (
          <div className="mb-6 rounded-md bg-background border shadow-sm">
            <div className="px-4 py-3 border-b flex justify-between items-center">
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-medium">Attached Questionnaires</h3>
                <Badge variant="outline" className="border-primary/30 bg-primary/10">
                  <ClipboardList className="h-3 w-3 mr-1" />
                  {interview.questionnaires?.length 
                    ? `${interview.questionnaires.length} ${interview.questionnaires.length === 1 ? 'Questionnaire' : 'Questionnaires'}` 
                    : interview.questionnaire 
                      ? "1 Questionnaire" 
                      : "No Questionnaires"}
                </Badge>
              </div>
              
              <Button 
                variant="outline" 
                size="sm"
                onClick={() => setIsQuestionnaireDialogOpen(true)}
              >
                <PlusIcon className="h-4 w-4 mr-1" />
                Add Questionnaire
              </Button>
            </div>
            
            <div className="p-4">
              {!interview.questionnaire && (!interview.questionnaires || interview.questionnaires.length === 0) ? (
                <div className="text-center p-6">
                  <p className="text-muted-foreground">No questionnaires attached yet</p>
                  <Button 
                    variant="default" 
                    size="sm" 
                    className="mt-2"
                    onClick={() => setIsQuestionnaireDialogOpen(true)}
                  >
                    <PlusIcon className="h-4 w-4 mr-1" />
                    Add Questionnaire
                  </Button>
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Display all questionnaires from the questionnaires array if it exists */}
                  {interview.questionnaires && interview.questionnaires.length > 0 ? (
                    interview.questionnaires.map(questionnaire => (
                      <div key={questionnaire.id} className="rounded-md border overflow-hidden">
                        <div className="bg-muted/50 px-4 py-3 flex justify-between items-center">
                          <Link href={`/questionnaires/${questionnaire.id}`} className="font-medium hover:underline text-primary">
                            {questionnaire.title}
                          </Link>
                          
                          <div className="flex items-center gap-2">
                            <Button 
                              variant="ghost" 
                              size="sm"
                              className="text-muted-foreground hover:text-foreground"
                              onClick={() => generateAnswers(questionnaire.id)}
                              disabled={isGeneratingAnswers[questionnaire.id] || isLoading}
                            >
                              {isGeneratingAnswers[questionnaire.id] ? (
                                <>
                                  <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                                  Generating...
                                </>
                              ) : (
                                <>
                                  <ClipboardList className="h-4 w-4 mr-1" />
                                  {interview.generated_answers?.[questionnaire.id] 
                                    ? 'Regenerate Answers' 
                                    : 'Generate Answers'}
                                </>
                              )}
                            </Button>
                            
                            <Button 
                              variant="ghost" 
                              size="sm"
                              className="text-destructive hover:text-destructive hover:bg-destructive/10"
                              onClick={async () => {
                                try {
                                  console.log(`Attempting to remove questionnaire ${questionnaire.id} from interview ${id}`);
                                  
                                  // Explicitly construct the URL with query parameters
                                  const response = await api.delete(`/api/interviews/${id}/remove-questionnaire?questionnaire_id=${questionnaire.id}`);
                                  
                                  console.log('Remove questionnaire response:', response);
                                  toast.success('Questionnaire removed successfully');
                                  await fetchInterview();
                                } catch (error) {
                                  console.error('Failed to remove questionnaire:', error);
                                  toast.error(`Failed to remove questionnaire: ${error instanceof Error ? error.message : 'Unknown error'}`);
                                }
                              }}
                            >
                              <span className="sr-only">Remove</span>
                              <span className="text-sm">Remove</span>
                            </Button>
                          </div>
                        </div>
                        
                        <div className="p-4 bg-card">
                          {questionnaire.questions?.length > 0 ? (
                            <div className="grid gap-4">
                              {questionnaire.questions.map((question, index) => {
                                const hasAnswer = interview.generated_answers?.[questionnaire.id]?.[question];
                                return (
                                  <div key={`question-${questionnaire.id}-${index}`} className="border-b pb-4 last:border-b-0 last:pb-0">
                                    <div className="flex justify-between items-start gap-2 mb-2">
                                      <p className="font-medium text-card-foreground">{question}</p>
                                      <div className={`text-xs px-2 py-1 rounded-full ${hasAnswer ? 'bg-primary/20 text-primary-foreground' : 'bg-muted'} flex-shrink-0`}>
                                        {hasAnswer ? 'Answered' : 'Pending'}
                                      </div>
                                    </div>
                                    {hasAnswer && (
                                      <div className="mt-2 ml-4 pl-2 border-l-2 border-primary/30">
                                        <p className="text-sm text-muted-foreground whitespace-pre-line">{interview.generated_answers?.[questionnaire.id]?.[question]}</p>
                                      </div>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          ) : (
                            <p className="text-sm text-muted-foreground">No questions found in this questionnaire</p>
                          )}
                        </div>
                      </div>
                    ))
                  ) : interview.questionnaire ? (
                    // Fallback to the single questionnaire if questionnaires array is not populated
                    <div className="rounded-md border overflow-hidden">
                      <div className="bg-muted/50 px-4 py-3 flex justify-between items-center">
                        <Link href={`/questionnaires/${interview.questionnaire.id}`} className="font-medium hover:underline text-primary">
                          {interview.questionnaire.title}
                        </Link>
                        
                        <div className="flex items-center gap-2">
                          <Button 
                            variant="ghost" 
                            size="sm"
                            className="text-muted-foreground hover:text-foreground"
                            onClick={() => generateAnswers(interview.questionnaire?.id)}
                            disabled={isGeneratingAnswers[interview.questionnaire?.id || ''] || isLoading}
                          >
                            {isGeneratingAnswers[interview.questionnaire?.id || ''] ? (
                              <>
                                <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                                Generating...
                              </>
                            ) : (
                              <>
                                <ClipboardList className="h-4 w-4 mr-1" />
                                {interview.generated_answers?.[interview.questionnaire?.id || ''] 
                                  ? 'Regenerate Answers' 
                                  : 'Generate Answers'}
                              </>
                            )}
                          </Button>
                          
                          <Button 
                            variant="ghost" 
                            size="sm"
                            className="text-destructive hover:text-destructive hover:bg-destructive/10"
                            onClick={async () => {
                              if (!interview.questionnaire?.id) return;
                              
                              try {
                                console.log(`Attempting to remove questionnaire ${interview.questionnaire.id} from interview ${id}`);
                                
                                // Explicitly construct the URL with query parameters
                                const response = await api.delete(`/api/interviews/${id}/remove-questionnaire?questionnaire_id=${interview.questionnaire.id}`);
                                
                                console.log('Remove questionnaire response:', response);
                                toast.success('Questionnaire removed successfully');
                                await fetchInterview();
                              } catch (error) {
                                console.error('Failed to remove questionnaire:', error);
                                toast.error(`Failed to remove questionnaire: ${error instanceof Error ? error.message : 'Unknown error'}`);
                              }
                            }}
                          >
                            <span className="sr-only">Remove</span>
                            <span className="text-sm">Remove</span>
                          </Button>
                        </div>
                      </div>
                      
                      <div className="p-4 bg-card">
                        {interview.questionnaire?.questions ? (
                          <div className="grid gap-4">
                            {interview.questionnaire.questions.map((question, index) => {
                              const hasAnswer = interview.generated_answers?.[interview.questionnaire?.id || '']?.[question];
                              return (
                                <div key={`question-${interview.questionnaire?.id}-${index}`} className="border-b pb-4 last:border-b-0 last:pb-0">
                                  <div className="flex justify-between items-start gap-2 mb-2">
                                    <p className="font-medium text-card-foreground">{question}</p>
                                    <div className={`text-xs px-2 py-1 rounded-full ${hasAnswer ? 'bg-primary/20 text-primary-foreground' : 'bg-muted'} flex-shrink-0`}>
                                      {hasAnswer ? 'Answered' : 'Pending'}
                                    </div>
                                  </div>
                                  {hasAnswer && (
                                    <div className="mt-2 ml-4 pl-2 border-l-2 border-primary/30">
                                      <p className="text-sm text-muted-foreground whitespace-pre-line">{interview.generated_answers?.[interview.questionnaire?.id || '']?.[question]}</p>
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          <p className="text-sm text-muted-foreground">No questions found in this questionnaire</p>
                        )}
                      </div>
                    </div>
                  ) : null}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Simplified Questionnaire Dialog */}
        <Dialog open={isQuestionnaireDialogOpen} onOpenChange={setIsQuestionnaireDialogOpen}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Add Questionnaire</DialogTitle>
              <DialogDescription>
                Select a questionnaire to analyze this interview
              </DialogDescription>
            </DialogHeader>
            
            <div className="py-4">
              {questionnaires.length === 0 ? (
                <div className="text-center p-4 border rounded-md bg-muted">
                  <p className="text-muted-foreground mb-2">No questionnaires found</p>
                  <Button variant="outline" onClick={fetchQuestionnaires} className="mr-2">
                    Refresh List
                  </Button>
                  <Button variant="default" asChild>
                    <Link href="/questionnaires/new" target="_blank">
                      <PlusIcon className="h-4 w-4 mr-1" />
                      Create New
                    </Link>
                  </Button>
                </div>
              ) : (
                <div>
                  <label htmlFor="questionnaire-select" className="text-sm font-medium block mb-2">
                    Select a questionnaire:
                  </label>
                  <Select 
                    onValueChange={(value) => setSelectedQuestionnaireId(value)}
                    defaultValue={interview.questionnaire_id || ""}
                    name="questionnaire-select"
                  >
                    <SelectTrigger className="w-full" id="questionnaire-select">
                      <SelectValue placeholder="Choose a questionnaire" />
                    </SelectTrigger>
                    <SelectContent>
                      {questionnaires.map((q) => (
                        <SelectItem key={q.id} value={q.id}>
                          {q.title}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
            
            <div className="flex justify-end gap-2 pt-2">
              <Button 
                variant="secondary" 
                onClick={() => setIsQuestionnaireDialogOpen(false)}
              >
                Cancel
              </Button>
              <Button 
                onClick={attachQuestionnaire} 
                disabled={isAttachingQuestionnaire || !selectedQuestionnaireId}
              >
                {isAttachingQuestionnaire ? (
                  <>
                    <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                    Attaching...
                  </>
                ) : (
                  'Attach Questionnaire'
                )}
              </Button>
            </div>
          </DialogContent>
        </Dialog>

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
              
              {/* We need a separate element with an effect to conditionally render ChatInterface */}
              <LazyLoadComponent check={!!interview.transcription}>
                <ChatInterface 
                  interviewId={id as string} 
                  interviewTitle={interview.title}
                  transcriptHighlights={{
                    highlightedText: interview?.transcript_segments?.map(s => `${s.text.substring(0, 60)}...`),
                    onHighlightClick: (index: number) => {
                      if (interview?.transcript_segments?.[index]) {
                        handleSegmentClick(interview.transcript_segments[index], index);
                      }
                    }
                  }}
                />
              </LazyLoadComponent>
            </div>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}