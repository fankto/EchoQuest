import { useState, useRef, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Pencil, Save, X, Search, PlayCircle, Check } from 'lucide-react'
import { cn } from '@/lib/utils'
import { secondsToTimestamp } from '@/lib/format'
import api from '@/lib/api-client'
import { Input } from '@/components/ui/input'
import { Textarea } from '../ui/textarea'

export type TranscriptSegment = {
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
  
  // New state for segment editing
  const [editingSegmentIndex, setEditingSegmentIndex] = useState<number | null>(null)
  const [editedSegments, setEditedSegments] = useState<TranscriptSegment[]>(segments)
  const [editedSegmentText, setEditedSegmentText] = useState('')
  const [editedSegmentSpeaker, setEditedSegmentSpeaker] = useState('')

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
      // Update current segment index
      setCurrentSegmentIndex(highlightedSegmentIndex);
      
      // Scroll to the segment if it's offscreen
      const segmentElement = segmentRefs.current.get(highlightedSegmentIndex);
      if (segmentElement) {
        segmentElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
      
      // NOTE: We're no longer attempting to play audio here.
      // Audio playback is handled exclusively by the AudioPlayer component via onSegmentClick
    }
  }, [highlightedSegmentIndex, segments]);

  // Update edited segments when segments prop changes
  useEffect(() => {
    // Make sure the segment timestamps are accurate based on the text content
    if (segments && segments.length > 0) {
      // First, sort segments by start_time to ensure proper ordering
      const sortedSegments = [...segments].sort((a, b) => a.start_time - b.start_time);
      
      // Process each segment to fix timestamps
      const updatedSegments = sortedSegments.map((segment, index) => {
        // Default to keeping the original segment
        let updatedSegment = { ...segment };
        
        // If segment has word-level data, use it for precise timestamps
        if (segment.words && segment.words.length > 0) {
          const firstWord = segment.words[0];
          const lastWord = segment.words[segment.words.length - 1];
          
          updatedSegment = {
            ...updatedSegment,
            // Use the precise word timestamps for accuracy
            start_time: firstWord.start,
            end_time: lastWord.end
          };
        } else {
          // Without word data, make a reasonable estimate based on text length
          const textLength = segment.text.length;
          
          // Estimate speaking rate (chars per second) - typically 10-15 chars/sec
          // Adjust this based on your content (slower for technical, faster for casual)
          const avgSpeakingRate = 12;
          
          // Minimum duration based on text length
          const minimumDuration = Math.max(0.5, textLength / avgSpeakingRate);
          const currentDuration = segment.end_time - segment.start_time;
          
          // Only extend if current duration is unreasonably short
          if (currentDuration < minimumDuration) {
            updatedSegment = {
              ...updatedSegment,
              end_time: segment.start_time + minimumDuration
            };
          }
        }
        
        // Prevent overlaps with next segment
        if (index < sortedSegments.length - 1) {
          const nextSegment = sortedSegments[index + 1];
          
          // If this segment's end time overlaps with the next segment's start time
          if (updatedSegment.end_time > nextSegment.start_time) {
            // Set a gap of 0.01 seconds to prevent overlap
            const gap = 0.01;
            
            // Adjust end time to avoid overlap
            updatedSegment = {
              ...updatedSegment,
              end_time: Math.max(updatedSegment.start_time + 0.1, nextSegment.start_time - gap)
            };
          }
        }
        
        return updatedSegment;
      });
      
      console.log("Updated segments with corrected timestamps:", updatedSegments);
      setEditedSegments(updatedSegments);
    } else {
      setEditedSegments(segments);
    }
  }, [segments]);

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

  // New function to save edited segments
  const handleSaveSegments = async () => {
    try {
      await api.put(`/api/interviews/${interviewId}/update-segments`, {
        segments: editedSegments
      })
      
      toast("Segments updated successfully", {
        description: "Your changes have been saved",
      })
    } catch (error) {
      toast("Error updating segments", {
        description: "Failed to update segments",
      })
    }
  }

  // New function to handle segment edit start
  const handleEditSegment = (segment: TranscriptSegment, index: number, e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation() // Prevent audio playback
    setEditingSegmentIndex(index)
    setEditedSegmentText(segment.text)
    setEditedSegmentSpeaker(segment.speaker)
  }

  // Add keyboard event handler for accessibility
  const handleEditSegmentKeyPress = (segment: TranscriptSegment, index: number, e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      setEditingSegmentIndex(index)
      setEditedSegmentText(segment.text)
      setEditedSegmentSpeaker(segment.speaker)
    }
  }

  // New function to save segment edit
  const handleSaveSegmentEdit = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation() // Prevent audio playback
    
    if (editingSegmentIndex !== null) {
      const updatedSegments = [...editedSegments]
      updatedSegments[editingSegmentIndex] = {
        ...updatedSegments[editingSegmentIndex],
        text: editedSegmentText,
        speaker: editedSegmentSpeaker
      }
      
      setEditedSegments(updatedSegments)
      setEditingSegmentIndex(null)
      
      // Save changes to backend
      handleSaveSegments()
    }
  }

  // Add keyboard event handler for save
  const handleSaveSegmentEditKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      
      if (editingSegmentIndex !== null) {
        const updatedSegments = [...editedSegments]
        updatedSegments[editingSegmentIndex] = {
          ...updatedSegments[editingSegmentIndex],
          text: editedSegmentText,
          speaker: editedSegmentSpeaker
        }
        
        setEditedSegments(updatedSegments)
        setEditingSegmentIndex(null)
        
        // Save changes to backend
        handleSaveSegments()
      }
    }
  }

  // New function to cancel segment edit
  const handleCancelSegmentEdit = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation() // Prevent audio playback
    setEditingSegmentIndex(null)
  }

  // Add keyboard event handler for cancel
  const handleCancelSegmentEditKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      setEditingSegmentIndex(null)
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

  const playSegmentAudio = (segment: TranscriptSegment, index: number, e?: React.MouseEvent<HTMLButtonElement>) => {
    if (e) {
      e.stopPropagation();
    }
    
    // Don't play audio if we're editing
    if (editingSegmentIndex !== null) {
      return;
    }
    
    console.log(`Transcript viewer playSegmentAudio: segment ${index} clicked`);
    
    // Always update our local current segment index first
    setCurrentSegmentIndex(index);
    
    // Notify parent via callback (most important part - this triggers the AudioPlayer)
    if (onSegmentClick) {
      // This will trigger the AudioPlayer component to play this segment
      console.log(`Calling onSegmentClick for segment ${index}`);
      
      // Delay slightly to ensure the UI updates first
      setTimeout(() => {
        onSegmentClick(segment, index);
      }, 10);
    } else if (audioRef.current && segment.start_time !== undefined) {
      // Direct playback is a fallback case only
      console.log(`Direct audio playback for segment ${index} with local audio element`);
      
      // First completely stop any currently playing audio
      audioRef.current.pause();
      
      // Set current time exactly to segment start for local player
      audioRef.current.currentTime = segment.start_time;
      
      // Play directly if no parent handler (fallback case)
      audioRef.current.play().catch(error => {
        console.error("Failed to play segment:", error);
        toast.error("Failed to play segment audio");
      });
    }
  };

  // Handle keyboard interaction consistently with click behavior
  const handlePlaySegmentKeyDown = (segment: TranscriptSegment, index: number, e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      
      // Use the same implementation as the click handler
      playSegmentAudio(segment, index);
    }
  };
  
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
                  {editedSegments.map((segment, index) => (
                    <button 
                      key={segment.start_time ? `segment-${segment.start_time}-${index}` : `segment-${index}`}
                      ref={el => {
                        if (el) segmentRefs.current.set(index, el)
                      }}
                      className={`${getSegmentClassName(index)} w-full text-left`}
                      onClick={() => playSegmentAudio(segment, index)}
                      onKeyDown={(e) => handlePlaySegmentKeyDown(segment, index, e)}
                      aria-label={`Play segment ${index + 1}`}
                      type="button"
                    >
                      {editingSegmentIndex === index ? (
                        <div 
                          onClick={(e: React.MouseEvent<HTMLDivElement>) => e.stopPropagation()}
                          onKeyDown={(e: React.KeyboardEvent<HTMLDivElement>) => {
                            // Prevent event propagation for keyboard events
                            e.stopPropagation();
                          }}
                          role="presentation"
                        >
                          <div className="flex items-center justify-between gap-2 mb-2">
                            <Input 
                              value={editedSegmentSpeaker}
                              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEditedSegmentSpeaker(e.target.value)}
                              className="w-32"
                              placeholder="Speaker"
                            />
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-muted-foreground">
                                {secondsToTimestamp(segment.start_time)} - {secondsToTimestamp(segment.end_time)}
                              </span>
                              <Button 
                                variant="ghost" 
                                size="icon" 
                                className="h-6 w-6" 
                                onClick={handleSaveSegmentEdit}
                                onKeyDown={handleSaveSegmentEditKeyDown}
                                title="Save changes"
                              >
                                <Check className="h-4 w-4" />
                              </Button>
                              <Button 
                                variant="ghost" 
                                size="icon" 
                                className="h-6 w-6" 
                                onClick={handleCancelSegmentEdit}
                                onKeyDown={handleCancelSegmentEditKeyDown}
                                title="Cancel"
                              >
                                <X className="h-4 w-4" />
                              </Button>
                            </div>
                          </div>
                          <Textarea 
                            value={editedSegmentText}
                            onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setEditedSegmentText(e.target.value)}
                            className="w-full"
                            rows={3}
                          />
                        </div>
                      ) : (
                        <>
                          <div className="flex items-center justify-between gap-2 mb-2">
                            <Badge variant="outline" className="font-mono">
                              {segment.speaker || `Speaker ${Math.floor(index/3) + 1}`}
                            </Badge>
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-muted-foreground">
                                {secondsToTimestamp(segment.start_time)} - {secondsToTimestamp(segment.end_time)}
                              </span>
                              {audioUrl && (
                                <>
                                  <Button 
                                    variant="ghost" 
                                    size="icon" 
                                    className="h-6 w-6" 
                                    onClick={(e: React.MouseEvent<HTMLButtonElement>) => playSegmentAudio(segment, index, e)}
                                    onKeyDown={(e: React.KeyboardEvent<HTMLButtonElement>) => handlePlaySegmentKeyDown(segment, index, e)}
                                    title="Play segment"
                                  >
                                    <PlayCircle className="h-4 w-4" />
                                  </Button>
                                  <Button 
                                    variant="ghost" 
                                    size="icon" 
                                    className="h-6 w-6" 
                                    onClick={(e: React.MouseEvent<HTMLButtonElement>) => handleEditSegment(segment, index, e)}
                                    onKeyDown={(e: React.KeyboardEvent<HTMLButtonElement>) => handleEditSegmentKeyPress(segment, index, e)}
                                    title="Edit segment"
                                  >
                                    <Pencil className="h-4 w-4" />
                                  </Button>
                                </>
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
                        </>
                      )}
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