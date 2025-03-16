'use client'

import { useState, useRef, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Slider } from '@/components/ui/slider'
import { Play, Pause, SkipBack, SkipForward, Volume2, VolumeX } from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatDuration } from '@/lib/format'

interface AudioPlayerProps {
  src: string
  title?: string
  onTimeUpdate?: (currentTime: number) => void
  className?: string
  initialTime?: number
}

export function AudioPlayer({
  src,
  title,
  onTimeUpdate,
  className,
  initialTime = 0,
}: AudioPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [duration, setDuration] = useState(0)
  const [currentTime, setCurrentTime] = useState(0)
  const [volume, setVolume] = useState(1)
  const [isMuted, setIsMuted] = useState(false)
  const [isLoaded, setIsLoaded] = useState(false)
  
  const audioRef = useRef<HTMLAudioElement>(null)
  
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
        audioRef.current.play()
      }
      setIsPlaying(!isPlaying)
    }
  }
  
  // Handle audio events
  const handleLoadedMetadata = () => {
    if (audioRef.current) {
      setDuration(audioRef.current.duration)
      setIsLoaded(true)
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
        <audio
          ref={audioRef}
          src={src}
          onLoadedMetadata={handleLoadedMetadata}
          onTimeUpdate={handleTimeUpdate}
          onEnded={() => setIsPlaying(false)}
          onPause={() => setIsPlaying(false)}
          onPlay={() => setIsPlaying(true)}
        />
        
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

function Slider({
  className,
  ...props
}: React.ComponentProps<typeof Slider>) {
  return (
    <div className={cn("w-full relative", className)}>
      <div className="h-2 w-full relative flex items-center">
        <div className="h-1 w-full bg-secondary rounded-md" />
        <Slider
          {...props}
          className="absolute inset-0"
        />
      </div>
    </div>
  )
}