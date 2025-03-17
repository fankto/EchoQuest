import { useState, useRef, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Pencil, Save, X, Search, PlayCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import { secondsToTimestamp } from '@/lib/format'
import api from '@/lib/api-client'

type TranscriptSegment = {
  text: string
  start_time: number
  end_time: number
  speaker: string
  words?: Array<{
    word: string;
    start: number;
    end: number;
  }>
}

type TranscriptViewerProps = {
  interviewId: string
  transcriptText: string
  segments?: TranscriptSegment[]
  audioUrl?: string
  searchQuery?: string
  highlightedSegmentIndex?: number
  onSegmentClick?: (segment: TranscriptSegment, index: number) => void
  currentTime?: number
  className?: string
}

export function TranscriptViewer({
  interviewId,
  transcriptText,
  segments = [],
  audioUrl,
  searchQuery = '',
  highlightedSegmentIndex,
  onSegmentClick,
  currentTime = 0,
  className,
}: TranscriptViewerProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [editedText, setEditedText] = useState(transcriptText)
  const [originalText] = useState(transcriptText)
  const [activeTab, setActiveTab] = useState<string>('segments')
  const segmentRefs = useRef<Map<number, HTMLElement>>(new Map())
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [currentSegmentIndex, setCurrentSegmentIndex] = useState<number | undefined>(undefined)
  
  // Automatically switch to segments tab if segments are available
  useEffect(() => {
    if (segments && segments.length > 0 && activeTab === 'transcript') {
      setActiveTab('segments')
    }
  }, [segments, activeTab])

  useEffect(() => {
    // Find the current segment based on audio playback time
    if (currentTime > 0 && segments) {
      const index = segments.findIndex(segment => 
        currentTime >= segment.start_time && currentTime <= segment.end_time
      )
      
      if (index !== -1 && index !== currentSegmentIndex) {
        setCurrentSegmentIndex(index)
        
        // Scroll to the segment in view if we're on segments tab
        if (activeTab === 'segments') {
          const segmentElement = segmentRefs.current.get(index)
          segmentElement?.scrollIntoView({ 
            behavior: 'smooth', 
            block: 'center' 
          })
        }
      }
    }
  }, [currentTime, segments, currentSegmentIndex, activeTab])

  useEffect(() => {
    // Focus highlighted segment when it changes
    if (highlightedSegmentIndex !== undefined && segments && segments[highlightedSegmentIndex]) {
      setCurrentSegmentIndex(highlightedSegmentIndex)
      
      const segmentElement = segmentRefs.current.get(highlightedSegmentIndex)
      segmentElement?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      
      // If audio is available, seek to the segment's start time
      if (audioRef.current && segments[highlightedSegmentIndex].start_time) {
        audioRef.current.currentTime = segments[highlightedSegmentIndex].start_time
        audioRef.current.play().catch(error => {
          console.error("Failed to play segment:", error)
        })
      }
    }
  }, [highlightedSegmentIndex, segments])

  const handleSave = async () => {
    try {
      await api.put(`/api/interviews/${interviewId}/update-transcription`, {
        transcription: editedText
      })
      
      toast("Transcription updated successfully", {
        description: "Your changes have been saved",
      })
      
      setIsEditing(false)
    } catch (error) {
      toast("Error updating transcription", {
        description: "Failed to update transcription",
      })
    }
  }

  const handleCancel = () => {
    setEditedText(transcriptText)
    setIsEditing(false)
  }

  const highlightSearchQuery = (text: string) => {
    if (!searchQuery) return text

    const regex = new RegExp(`(${searchQuery})`, 'gi')
    return text.replace(regex, '<mark>$1</mark>')
  }

  const playSegmentAudio = (segment: TranscriptSegment, index: number, e?: React.MouseEvent) => {
    if (e) {
      e.stopPropagation()
    }
    
    if (audioRef.current && segment.start_time) {
      audioRef.current.currentTime = segment.start_time
      audioRef.current.play().catch(error => {
        console.error("Failed to play segment:", error)
        toast.error("Failed to play segment audio")
      })
    }
    
    if (onSegmentClick) {
      onSegmentClick(segment, index)
    }
  }
  
  // Get segment class based on its state (highlighted, current playing)
  const getSegmentClassName = (index: number) => {
    return cn(
      "p-3 rounded-md border transition-colors mb-3",
      (index === highlightedSegmentIndex || index === currentSegmentIndex)
        ? "bg-muted/50 border-primary"
        : "hover:bg-muted/30"
    )
  }

  return (
    <Card className={cn("flex flex-col h-full", className)}>
      <CardHeader className="px-4 py-3 flex-col sm:flex-row gap-1 space-y-0 justify-between border-b">
        <CardTitle className="text-lg">Interview Transcript</CardTitle>
        <div className="flex items-center gap-2">
          {isEditing ? (
            <>
              <Button size="sm" variant="outline" onClick={handleCancel}>
                <X className="h-4 w-4 mr-1" /> Cancel
              </Button>
              <Button size="sm" onClick={handleSave}>
                <Save className="h-4 w-4 mr-1" /> Save
              </Button>
            </>
          ) : (
            <Button size="sm" variant="outline" onClick={() => setIsEditing(true)}>
              <Pencil className="h-4 w-4 mr-1" /> Edit
            </Button>
          )}
        </div>
      </CardHeader>
      
      {audioUrl && (
        <div className="p-2 border-b hidden">
          <audio 
            ref={audioRef} 
            src={audioUrl} 
            controls 
            className="w-full h-10"
            aria-label="Interview audio"
            onError={(e) => console.error("Audio error:", e)}
          >
            <track kind="captions" src="" label="English captions" />
          </audio>
        </div>
      )}
      
      <CardContent className="p-0 flex-1 overflow-hidden">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="flex flex-col h-full">
          <div className="border-b">
            <TabsList className="px-4 bg-transparent">
              {segments && segments.length > 0 && (
                <TabsTrigger value="segments">Segments</TabsTrigger>
              )}
              <TabsTrigger value="transcript">Full Transcript</TabsTrigger>
            </TabsList>
          </div>
          
          <TabsContent value="segments" className="flex-1 overflow-hidden m-0 data-[state=active]:h-full">
            <ScrollArea className="h-full">
              {segments && segments.length > 0 ? (
                <div className="space-y-0 p-4">
                  {segments.map((segment, index) => (
                    <button 
                      key={segment.start_time ? `segment-${segment.start_time}-${index}` : `segment-${index}`}
                      ref={el => {
                        if (el) segmentRefs.current.set(index, el)
                      }}
                      className={`${getSegmentClassName(index)} w-full text-left`}
                      onClick={() => playSegmentAudio(segment, index)}
                      aria-label={`Play segment ${index + 1}`}
                      type="button"
                    >
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <Badge variant="outline" className="font-mono">
                          {segment.speaker || `Speaker ${Math.floor(index/3) + 1}`}
                        </Badge>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-muted-foreground">
                            {secondsToTimestamp(segment.start_time)} - {secondsToTimestamp(segment.end_time)}
                          </span>
                          {audioUrl && (
                            <Button 
                              variant="ghost" 
                              size="icon" 
                              className="h-6 w-6" 
                              onClick={(e) => playSegmentAudio(segment, index, e)}
                              title="Play segment"
                            >
                              <PlayCircle className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      </div>
                      <div className="text-sm">
                        {searchQuery ? (
                          <>
                            {segment.text.split(new RegExp(`(${searchQuery})`, 'gi')).map((part, i) => 
                              part.toLowerCase() === searchQuery.toLowerCase() 
                                ? <mark key={`segment-${segment.start_time}-mark-${i}-${part.substring(0, 10)}`}>{part}</mark> 
                                : part
                            )}
                          </>
                        ) : (
                          segment.text
                        )}
                      </div>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="flex h-full flex-col items-center justify-center">
                  <div className="flex h-20 w-20 items-center justify-center rounded-full bg-muted">
                    <Search className="h-10 w-10 text-muted-foreground" />
                  </div>
                  <h3 className="mt-4 text-lg font-semibold">
                    No segments available
                  </h3>
                  <p className="mt-2 text-center text-sm text-muted-foreground max-w-sm">
                    Segment data is not available for this transcript.
                  </p>
                </div>
              )}
            </ScrollArea>
          </TabsContent>
          
          <TabsContent value="transcript" className="flex-1 overflow-hidden m-0 data-[state=active]:h-full">
            {isEditing ? (
              <textarea
                value={editedText}
                onChange={(e) => setEditedText(e.target.value)}
                className="w-full h-full p-4 resize-none focus:outline-none border-0"
                aria-label="Edit transcript"
                placeholder="Enter transcript text"
              />
            ) : (
              <ScrollArea className="h-full p-4">
                {transcriptText ? (
                  <div 
                    className="whitespace-pre-wrap"
                  >
                    {searchQuery ? (
                      <>
                        {transcriptText.split(new RegExp(`(${searchQuery})`, 'gi')).map((part, i) => 
                          part.toLowerCase() === searchQuery.toLowerCase() 
                            ? <mark key={`transcript-mark-${i}-${part.substring(0, 10)}`}>{part}</mark> 
                            : part
                        )}
                      </>
                    ) : (
                      transcriptText
                    )}
                  </div>
                ) : (
                  <div className="flex h-full flex-col items-center justify-center">
                    <div className="flex h-20 w-20 items-center justify-center rounded-full bg-muted">
                      <Search className="h-10 w-10 text-muted-foreground" />
                    </div>
                    <h3 className="mt-4 text-lg font-semibold">
                      No transcript available
                    </h3>
                    <p className="mt-2 text-center text-sm text-muted-foreground max-w-sm">
                      Process and transcribe your interview audio to view the transcript.
                    </p>
                  </div>
                )}
              </ScrollArea>
            )}
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}