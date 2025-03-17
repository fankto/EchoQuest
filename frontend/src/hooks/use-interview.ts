import { useState, useCallback, useEffect } from 'react'
import { Interview, InterviewStatus, TaskResponse } from '@/types/interview'
import { toast } from 'sonner'
import api from '@/lib/api-client'

interface UseInterviewOptions {
  id?: string
  autoFetch?: boolean
  pollStatus?: boolean
}

export function useInterview({ id, autoFetch = true, pollStatus = false }: UseInterviewOptions = {}) {
  const [interview, setInterview] = useState<Interview | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  // Fetch interview data
  const fetchInterview = useCallback(async (interviewId: string = id!) => {
    if (!interviewId) return

    try {
      setIsLoading(true)
      const data = await api.get<Interview>(`/api/interviews/${interviewId}`)
      setInterview(data)
      
      // Check if currently processing or transcribing
      if (data.status === InterviewStatus.PROCESSING) {
        setIsProcessing(true)
      } else if (data.status === InterviewStatus.TRANSCRIBING) {
        setIsTranscribing(true)
      } else {
        setIsProcessing(false)
        setIsTranscribing(false)
      }
      
      return data
    } catch (error: any) {
      setError(error)
      toast.error('Failed to fetch interview')
      return null
    } finally {
      setIsLoading(false)
    }
  }, [id])

  // Create new interview
  const createInterview = useCallback(async (data: any) => {
    try {
      setIsLoading(true)
      const response = await api.post<Interview>('/api/interviews', data)
      return response
    } catch (error: any) {
      setError(error)
      toast.error('Failed to create interview')
      throw error
    } finally {
      setIsLoading(false)
    }
  }, [])

  // Update interview
  const updateInterview = useCallback(async (interviewId: string, data: any) => {
    try {
      setIsLoading(true)
      const response = await api.patch<Interview>(`/api/interviews/${interviewId}`, data)
      
      if (id === interviewId) {
        setInterview(response)
      }
      
      return response
    } catch (error: any) {
      setError(error)
      toast.error('Failed to update interview')
      throw error
    } finally {
      setIsLoading(false)
    }
  }, [id])

  // Upload audio files
  const uploadAudio = useCallback(async (interviewId: string, files: File[]) => {
    try {
      setIsLoading(true)
      
      console.log('Preparing to upload files:', files.map(f => ({ name: f.name, type: f.type, size: f.size })))
      
      const formData = new FormData()
      for (const file of files) {
        formData.append('files', file)
      }
      
      console.log('FormData created with', files.length, 'files')
      
      const response = await api.upload(`/api/interviews/${interviewId}/upload`, formData)
      
      if (id === interviewId) {
        setInterview(response)
      }
      
      return response
    } catch (error: any) {
      console.error('Error details:', error)
      setError(error)
      toast.error('Failed to upload audio files')
      throw error
    } finally {
      setIsLoading(false)
    }
  }, [id])

  // Process audio
  const processAudio = useCallback(async (interviewId: string = id!) => {
    if (!interviewId) return null
    
    try {
      setIsProcessing(true)
      const response = await api.post<TaskResponse>(`/api/interviews/${interviewId}/process`)
      toast.success('Audio processing started')
      return response
    } catch (error: any) {
      setIsProcessing(false)
      setError(error)
      toast.error('Failed to start audio processing')
      throw error
    }
  }, [id])

  // Transcribe audio
  const transcribeAudio = useCallback(async (interviewId: string = id!, language?: string) => {
    if (!interviewId) return null
    
    try {
      setIsTranscribing(true)
      
      const data = language ? { language } : {}
      const response = await api.post<TaskResponse>(`/api/interviews/${interviewId}/transcribe`, data)
      
      toast.success('Transcription started')
      return response
    } catch (error: any) {
      setIsTranscribing(false)
      setError(error)
      toast.error('Failed to start transcription')
      throw error
    }
  }, [id])

  // Generate answers
  const generateAnswers = useCallback(async (interviewId: string = id!) => {
    if (!interviewId) return null
    
    try {
      setIsLoading(true)
      const response = await api.post<TaskResponse>(`/api/interviews/${interviewId}/generate-answers`)
      
      toast.success('Answer generation started')
      return response
    } catch (error: any) {
      setError(error)
      toast.error('Failed to generate answers')
      throw error
    } finally {
      setIsLoading(false)
    }
  }, [id])

  // Delete interview
  const deleteInterview = useCallback(async (interviewId: string) => {
    try {
      setIsLoading(true)
      await api.delete(`/api/interviews/${interviewId}`)
      toast.success('Interview deleted')
      return true
    } catch (error: any) {
      setError(error)
      toast.error('Failed to delete interview')
      throw error
    } finally {
      setIsLoading(false)
    }
  }, [])

  // Poll for status updates
  useEffect(() => {
    if (!pollStatus || !id) return
    
    let pollInterval: NodeJS.Timeout | null = null
    
    if (isProcessing || isTranscribing) {
      pollInterval = setInterval(async () => {
        try {
          const data = await api.get<Interview>(`/api/interviews/${id}`)
          
          if ((isProcessing && data.status !== InterviewStatus.PROCESSING) ||
              (isTranscribing && data.status !== InterviewStatus.TRANSCRIBING)) {
            // Status changed
            setIsProcessing(data.status === InterviewStatus.PROCESSING)
            setIsTranscribing(data.status === InterviewStatus.TRANSCRIBING)
            setInterview(data)
            
            if (data.status === InterviewStatus.PROCESSED) {
              toast.success('Audio processing complete')
            } else if (data.status === InterviewStatus.TRANSCRIBED) {
              toast.success('Transcription complete')
            } else if (data.status === InterviewStatus.ERROR) {
              toast.error('Process failed')
            }
            
            if (pollInterval && 
                data.status !== InterviewStatus.PROCESSING && 
                data.status !== InterviewStatus.TRANSCRIBING) {
              clearInterval(pollInterval)
            }
          }
        } catch (error) {
          console.error('Error polling interview status:', error)
        }
      }, 5000) // Poll every 5 seconds
    }
    
    return () => {
      if (pollInterval) {
        clearInterval(pollInterval)
      }
    }
  }, [id, isProcessing, isTranscribing, pollStatus])

  // Fetch interview on mount if autoFetch is true
  useEffect(() => {
    if (autoFetch && id) {
      fetchInterview()
    }
  }, [autoFetch, fetchInterview, id])

  return {
    interview,
    isLoading,
    isProcessing,
    isTranscribing,
    error,
    fetchInterview,
    createInterview,
    updateInterview,
    uploadAudio,
    processAudio,
    transcribeAudio,
    generateAnswers,
    deleteInterview
  }
}