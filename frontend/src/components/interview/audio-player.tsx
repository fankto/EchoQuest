'use client'

import { useState, useRef, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Slider } from '@/components/ui/slider'
import { Play, Pause, SkipBack, SkipForward, Volume2, VolumeX } from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatDuration } from '@/lib/format'
import { toast } from 'sonner'

interface AudioPlayerProps {
  src: string
  title?: string
  onTimeUpdate?: (currentTime: number) => void
  className?: string
  initialTime?: number
  currentSegment?: {
    start_time: number,
    end_time: number,
    text: string,
    speaker: string
  }
}

export function AudioPlayer({
  src,
  title,
  onTimeUpdate,
  className,
  initialTime = 0,
  currentSegment,
}: AudioPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [duration, setDuration] = useState(0)
  const [currentTime, setCurrentTime] = useState(0)
  const [volume, setVolume] = useState(1)
  const [isMuted, setIsMuted] = useState(false)
  const [isLoaded, setIsLoaded] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  const audioRef = useRef<HTMLAudioElement>(null)
  
  // Log the source when it changes for debugging
  useEffect(() => {
    console.log("Audio source:", src);
    if (src) {
      setError(null);
    }
  }, [src]);
  
  // Set initial time when the component mounts
  useEffect(() => {
    if (audioRef.current && initialTime > 0) {
      audioRef.current.currentTime = initialTime
      setCurrentTime(initialTime)
    }
  }, [initialTime])
  
  // Handle play/pause
  const togglePlay = () => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause()
      } else {
        audioRef.current.play().catch(e => {
          console.error("Error playing audio:", e);
          setError(`Unable to play audio: ${e.message}`);
          toast.error("Audio playback failed", {
            description: e.message,
          });
        })
      }
    }
  }
  
  // Handle audio events
  const handleLoadedMetadata = () => {
    if (audioRef.current) {
      console.log("Audio loaded, duration:", audioRef.current.duration);
      setDuration(audioRef.current.duration)
      setIsLoaded(true)
      setError(null)
    }
  }
  
  const handleTimeUpdate = () => {
    if (audioRef.current) {
      const time = audioRef.current.currentTime
      setCurrentTime(time)
      onTimeUpdate?.(time)
    }
  }
  
  const handleSliderChange = (value: number[]) => {
    if (audioRef.current) {
      const time = value[0]
      audioRef.current.currentTime = time
      setCurrentTime(time)
      onTimeUpdate?.(time)
    }
  }
  
  // Handle volume
  const toggleMute = () => {
    if (audioRef.current) {
      audioRef.current.muted = !isMuted
      setIsMuted(!isMuted)
    }
  }
  
  const handleVolumeChange = (value: number[]) => {
    if (audioRef.current) {
      const vol = value[0]
      audioRef.current.volume = vol
      setVolume(vol)
      
      if (vol === 0) {
        setIsMuted(true)
        audioRef.current.muted = true
      } else if (isMuted) {
        setIsMuted(false)
        audioRef.current.muted = false
      }
    }
  }
  
  // Skip forward/backward
  const skipForward = () => {
    if (audioRef.current) {
      const newTime = Math.min(audioRef.current.currentTime + 10, duration)
      audioRef.current.currentTime = newTime
      setCurrentTime(newTime)
      onTimeUpdate?.(newTime)
    }
  }
  
  const skipBackward = () => {
    if (audioRef.current) {
      const newTime = Math.max(audioRef.current.currentTime - 10, 0)
      audioRef.current.currentTime = newTime
      setCurrentTime(newTime)
      onTimeUpdate?.(newTime)
    }
  }
  
  // Handle errors
  const handleError = (e: React.SyntheticEvent<HTMLAudioElement, Event>) => {
    const errorMessage = (e.currentTarget.error?.message || "Unknown audio error");
    console.error("Audio error:", errorMessage);
    setError(`Audio error: ${errorMessage}`);
    setIsLoaded(false);
    toast.error("Audio playback error", {
      description: errorMessage,
    });
  }
  
  // Play segment when currentSegment changes
  useEffect(() => {
    if (audioRef.current && currentSegment) {
      console.log("Playing segment:", currentSegment);
      audioRef.current.currentTime = currentSegment.start_time;
      audioRef.current.play().catch(e => {
        console.error("Error playing segment:", e);
        setError(`Unable to play segment: ${e.message}`);
      });
    }
  }, [currentSegment]);
  
  // Cleanup
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause()
      }
    }
  }, [])
  
  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardContent className="p-4">
        {error && (
          <div className="mb-2 p-2 bg-red-50 text-red-600 rounded-md text-sm">
            {error}
          </div>
        )}
        
        <audio
          ref={audioRef}
          src={src}
          onLoadedMetadata={handleLoadedMetadata}
          onTimeUpdate={handleTimeUpdate}
          onEnded={() => setIsPlaying(false)}
          onPause={() => setIsPlaying(false)}
          onPlay={() => setIsPlaying(true)}
          onError={handleError}
          crossOrigin="anonymous"
        >
          <track kind="captions" src="" label="English captions" />
        </audio>
        
        {title && (
          <div className="mb-2 text-sm font-medium truncate">{title}</div>
        )}
        
        <div className="space-y-2">
          {/* Time slider */}
          <div className="flex items-center gap-2">
            <span className="text-xs w-12 text-muted-foreground">
              {formatDuration(currentTime)}
            </span>
            <Slider
              value={[currentTime]}
              min={0}
              max={duration || 100}
              step={0.1}
              onValueChange={handleSliderChange}
              disabled={!isLoaded}
              className="flex-1"
            />
            <span className="text-xs w-12 text-right text-muted-foreground">
              {formatDuration(duration)}
            </span>
          </div>
          
          {/* Controls */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                onClick={skipBackward}
                disabled={!isLoaded}
              >
                <SkipBack className="h-4 w-4" />
              </Button>
              
              <Button
                variant={isPlaying ? "default" : "outline"}
                size="icon"
                onClick={togglePlay}
                disabled={!isLoaded}
              >
                {isPlaying ? (
                  <Pause className="h-4 w-4" />
                ) : (
                  <Play className="h-4 w-4" />
                )}
              </Button>
              
              <Button
                variant="ghost"
                size="icon"
                onClick={skipForward}
                disabled={!isLoaded}
              >
                <SkipForward className="h-4 w-4" />
              </Button>
            </div>
            
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                onClick={toggleMute}
                disabled={!isLoaded}
              >
                {isMuted ? (
                  <VolumeX className="h-4 w-4" />
                ) : (
                  <Volume2 className="h-4 w-4" />
                )}
              </Button>
              
              <Slider
                value={[isMuted ? 0 : volume]}
                min={0}
                max={1}
                step={0.01}
                onValueChange={handleVolumeChange}
                disabled={!isLoaded}
                className="w-24"
              />
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}