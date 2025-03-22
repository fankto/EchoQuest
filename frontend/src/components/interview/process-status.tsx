'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Button } from '@/components/ui/button'
import { AlertTriangle, CheckCircle, Clock, FileAudio, FileText, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { InterviewStatus } from '@/types/interview'

interface ProcessStatusProps {
  status: InterviewStatus
  error?: string
  onProcess?: () => void
  onTranscribe?: () => void
  className?: string
  processingProgress?: number
  transcribingProgress?: number
}

export function ProcessStatus({
  status,
  error,
  onProcess,
  onTranscribe,
  className,
  processingProgress,
  transcribingProgress,
}: ProcessStatusProps) {
  const [progress, setProgress] = useState(0)
  
  // Simulate progress when actual progress is not provided
  useEffect(() => {
    if (status === InterviewStatus.PROCESSING && processingProgress === undefined) {
      const interval = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 95) {
            clearInterval(interval)
            return prev
          }
          return prev + 1
        })
      }, 500)
      
      return () => clearInterval(interval)
    } else if (status === InterviewStatus.TRANSCRIBING && transcribingProgress === undefined) {
      const interval = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 95) {
            clearInterval(interval)
            return prev
          }
          return prev + 1
        })
      }, 800)
      
      return () => clearInterval(interval)
    } else {
      setProgress(0)
    }
  }, [status, processingProgress, transcribingProgress])
  
  // Determine progress value based on status and provided progress
  const progressValue = () => {
    if (status === InterviewStatus.PROCESSING) {
      return processingProgress !== undefined ? processingProgress : progress
    } else if (status === InterviewStatus.TRANSCRIBING) {
      return transcribingProgress !== undefined ? transcribingProgress : progress
    } else if (status === InterviewStatus.PROCESSED || status === InterviewStatus.TRANSCRIBED) {
      return 100
    }
    return 0
  }
  
  // Render status icon based on current status
  const renderStatusIcon = () => {
    switch (status) {
      case InterviewStatus.CREATED:
        return <Clock className="h-6 w-6 text-muted-foreground" />
      case InterviewStatus.UPLOADED:
        return <FileAudio className="h-6 w-6 text-blue-500" />
      case InterviewStatus.PROCESSING:
        return <Loader2 className="h-6 w-6 text-yellow-500 animate-spin" />
      case InterviewStatus.PROCESSED:
        return <CheckCircle className="h-6 w-6 text-green-500" />
      case InterviewStatus.TRANSCRIBING:
        return <Loader2 className="h-6 w-6 text-purple-500 animate-spin" />
      case InterviewStatus.TRANSCRIBED:
        return <FileText className="h-6 w-6 text-green-500" />
      case InterviewStatus.ERROR:
        return <AlertTriangle className="h-6 w-6 text-red-500" />
      default:
        return <Clock className="h-6 w-6 text-muted-foreground" />
    }
  }
  
  // Render title based on current status
  const getStatusTitle = () => {
    switch (status) {
      case InterviewStatus.CREATED:
        return "Interview Created"
      case InterviewStatus.UPLOADED:
        return "Audio Uploaded"
      case InterviewStatus.PROCESSING:
        return "Processing Audio"
      case InterviewStatus.PROCESSED:
        return "Audio Processed"
      case InterviewStatus.TRANSCRIBING:
        return "Transcribing Audio"
      case InterviewStatus.TRANSCRIBED:
        return "Transcription Complete"
      case InterviewStatus.ERROR:
        return "Process Error"
      default:
        return "Unknown Status"
    }
  }
  
  // Render description based on current status
  const getStatusDescription = () => {
    switch (status) {
      case InterviewStatus.CREATED:
        return "Upload interview audio files to begin processing"
      case InterviewStatus.UPLOADED:
        return "Audio files have been uploaded. Ready for processing."
      case InterviewStatus.PROCESSING:
        return "Processing audio files. This may take a few minutes."
      case InterviewStatus.PROCESSED:
        return "Audio processing complete. Ready for transcription."
      case InterviewStatus.TRANSCRIBING:
        return "Transcribing audio. This may take several minutes depending on the length."
      case InterviewStatus.TRANSCRIBED:
        return "Transcription complete. Your interview is ready to explore."
      case InterviewStatus.ERROR:
        return error || "An error occurred during processing."
      default:
        return "Current status is unknown."
    }
  }
  
  return (
    <Card className={cn("", className)}>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          {renderStatusIcon()}
          <CardTitle>{getStatusTitle()}</CardTitle>
        </div>
        <CardDescription>{getStatusDescription()}</CardDescription>
      </CardHeader>
      <CardContent>
        {(status === InterviewStatus.PROCESSING || status === InterviewStatus.TRANSCRIBING) && (
          <Progress value={progressValue()} className="h-2 mb-4" />
        )}
        
        <div className="flex gap-2 justify-end">
          {status === InterviewStatus.UPLOADED && onProcess && (
            <Button onClick={onProcess}>
              Process Audio
            </Button>
          )}
          
          {status === InterviewStatus.PROCESSED && onTranscribe && (
            <Button onClick={onTranscribe}>
              Transcribe Audio
            </Button>
          )}
          
          {status === InterviewStatus.ERROR && onProcess && (
            <Button variant="outline" onClick={onProcess}>
              Retry Processing
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}