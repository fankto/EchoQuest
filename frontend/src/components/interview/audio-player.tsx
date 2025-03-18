'use client'

import { useState, useRef, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Slider } from '@/components/ui/slider'
import { Play, Pause, SkipBack, SkipForward, Volume2, VolumeX } from 'lucide-react'
import { cn } from '@/lib/utils'
import { formatDuration, secondsToTimestamp } from '@/lib/format'
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
      
      // Reset state when source changes
      setIsLoaded(false);
      setIsPlaying(false);
      
      // This forces the audio element to reload its source
      if (audioRef.current) {
        audioRef.current.load();
      }
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
    if (!audioRef.current) return;
    
    if (isPlaying) {
      // Pause playback
      audioRef.current.pause();
    } else {
      // Start playback, but respect segment boundaries
      if (currentSegment) {
        // If we're at or past segment end, reset to segment start
        if (audioRef.current.currentTime >= currentSegment.end_time) {
          audioRef.current.currentTime = currentSegment.start_time;
        }
        
        // If we're before segment start, set to segment start
        if (audioRef.current.currentTime < currentSegment.start_time) {
          audioRef.current.currentTime = currentSegment.start_time;
        }
      }
      
      // Start playback
      audioRef.current.play().catch(e => {
        console.error("Error playing audio:", e);
        setError(`Unable to play audio: ${e.message}`);
        toast.error("Audio playback failed", {
          description: e.message,
        });
      });
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
    if (!audioRef.current) return;
    
    const time = audioRef.current.currentTime;
    
    // Only update current time if within segment bounds
    if (currentSegment) {
      // If we've gone past segment end, force it to stop and stay at end
      if (time > currentSegment.end_time) {
        console.log(`Time update beyond segment end: ${time.toFixed(2)} > ${currentSegment.end_time.toFixed(2)}`);
        
        // Force audio to stop
        audioRef.current.pause();
        
        // Fix the time to segment end
        const endTime = currentSegment.end_time;
        audioRef.current.currentTime = endTime;
        
        // Update UI
        setCurrentTime(endTime);
        setIsPlaying(false);
        onTimeUpdate?.(endTime);
        return;
      }
      
      // Normal update within segment bounds
      setCurrentTime(time);
      onTimeUpdate?.(time);
    } else {
      // No segment constraints
      setCurrentTime(time);
      onTimeUpdate?.(time);
    }
  };
  
  // Override slider change to properly respect segment boundaries
  const handleSliderChange = (value: number[]) => {
    if (!audioRef.current) return;
    
    const requestedTime = value[0];
    let targetTime = requestedTime;
    
    console.log(`Slider change requested: ${requestedTime.toFixed(2)}`);
    
    // If within a segment, strictly enforce segment boundaries
    if (currentSegment) {
      // Constrain to segment boundaries
      targetTime = Math.max(
        currentSegment.start_time, 
        Math.min(requestedTime, currentSegment.end_time)
      );
      
      console.log(`Slider change: requested=${requestedTime.toFixed(2)}, constrained=${targetTime.toFixed(2)} (segment: ${currentSegment.start_time.toFixed(2)}-${currentSegment.end_time.toFixed(2)})`);
      
      // First pause playback to ensure clean seeking
      const wasPlaying = !audioRef.current.paused;
      audioRef.current.pause();
      
      // Apply the constrained time with direct imperative update to ensure it works
      audioRef.current.currentTime = targetTime;
      
      // Force UI updates immediately
      setCurrentTime(targetTime);
      onTimeUpdate?.(targetTime);
      
      // If trying to seek beyond segment end, keep paused
      if (requestedTime >= currentSegment.end_time && isPlaying) {
        setIsPlaying(false);
      } 
      // Otherwise, resume playback if it was playing before
      else if (wasPlaying) {
        // Resume after a small delay to ensure the time update has been processed
        setTimeout(() => {
          if (audioRef.current) {
            // Double-check we're at the right position
            if (Math.abs(audioRef.current.currentTime - targetTime) > 0.1) {
              console.warn(`Time not set correctly, fixing: ${audioRef.current.currentTime.toFixed(2)} → ${targetTime.toFixed(2)}`);
              audioRef.current.currentTime = targetTime;
            }
            audioRef.current.play().catch(e => console.error("Error resuming playback:", e));
          }
        }, 50);
        
        // Update state to reflect that we're playing
        setIsPlaying(true);
      }
    } else {
      // No constraints when not in a segment
      console.log(`Setting time to ${targetTime.toFixed(2)} (unconstrained)`);
      
      // First pause to ensure clean seeking
      const wasPlaying = !audioRef.current.paused;
      audioRef.current.pause();
      
      // Set the time
      audioRef.current.currentTime = targetTime;
      
      // Update UI
      setCurrentTime(targetTime);
      onTimeUpdate?.(targetTime);
      
      // Resume if it was playing
      if (wasPlaying) {
        audioRef.current.play().catch(e => console.error("Error resuming after seek:", e));
      }
    }
  };
  
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
    if (!audioRef.current || !currentSegment) return;
    
    // Debug the currentSegment to help identify any issues
    console.log("===== AudioPlayer: Segment Change Debug =====");
    console.log("Current Segment Speaker:", currentSegment.speaker);
    console.log("Current Segment Text:", currentSegment.text.substring(0, 30) + "...");
    console.log("Current Segment Time Range:", 
      `${currentSegment.start_time.toFixed(3)} - ${currentSegment.end_time.toFixed(3)}`);
    
    // Log for debugging
    console.log("AudioPlayer: New segment selected with bounds:", 
      `${currentSegment.start_time.toFixed(2)} - ${currentSegment.end_time.toFixed(2)}`,
      "Duration:", (currentSegment.end_time - currentSegment.start_time).toFixed(2),
      "Text length:", currentSegment.text.length);
    
    // CRITICAL: Stop any current playback immediately before changing times
    audioRef.current.pause();
    
    // Directly set current time before the setTimeout to ensure it's applied immediately
    console.log(`Setting current time to segment start: ${currentSegment.start_time.toFixed(3)}`);
    audioRef.current.currentTime = currentSegment.start_time;
    
    // Force UI update
    setCurrentTime(currentSegment.start_time);
    
    // Small delay to ensure previous playback is fully stopped
    setTimeout(() => {
      if (!audioRef.current || !currentSegment) return;
      
      // Double-check current time to make sure it was set correctly
      console.log(`Current audio time before playing: ${audioRef.current.currentTime.toFixed(3)}`);
      if (Math.abs(audioRef.current.currentTime - currentSegment.start_time) > 0.1) {
        console.warn(`Audio time doesn't match segment start time! Trying to set it again.`);
        // Try setting the time again
        audioRef.current.currentTime = currentSegment.start_time;
        console.log(`Retry set time: ${audioRef.current.currentTime.toFixed(3)}`);
      }
      
      // We need to track if this segment is still active to prevent stale handlers
      let isSegmentActive = true;
      
      // More aggressive segment boundary monitoring
      const monitorSegmentBoundary = () => {
        if (!audioRef.current || !isSegmentActive) return;
        
        const currentPos = audioRef.current.currentTime;
        
        // Debug info to see what's happening
        if (currentPos > currentSegment.end_time - 0.3) {
          console.log(`Approaching segment end: ${currentPos.toFixed(2)}/${currentSegment.end_time.toFixed(2)}`);
        }
        
        // Check if we've reached or exceeded segment end
        if (currentPos >= currentSegment.end_time) {
          console.log(`✓ STOPPING at segment boundary: ${currentPos.toFixed(2)} >= ${currentSegment.end_time.toFixed(2)}`);
          
          // Force a hard stop at the boundary
          audioRef.current.pause();
          
          // Force UI state update
          setIsPlaying(false);
          
          // Set current time to end of segment to prevent overrun
          audioRef.current.currentTime = currentSegment.end_time;
          
          // Force a UI update to ensure time display is correct
          setCurrentTime(currentSegment.end_time);
          
          // Ensure the parent component knows the time has updated
          onTimeUpdate?.(currentSegment.end_time);
          
          // Reset tracking flag to prevent double-stopping
          isSegmentActive = false;
        }
      };
      
      // Add aggressive monitoring with very frequent checks
      const monitoringInterval = setInterval(monitorSegmentBoundary, 50);
      
      // Also watch timeupdate for additional safety
      audioRef.current.addEventListener('timeupdate', monitorSegmentBoundary);
      
      // Force play state to true before starting playback
      setIsPlaying(true);
      
      // Start playback from segment start
      const playPromise = audioRef.current.play();
      if (playPromise !== undefined) {
        playPromise.catch(e => {
          console.error("Error playing segment:", e);
          setError(`Unable to play segment: ${e.message}`);
          setIsPlaying(false);
        });
      }
      
      // Comprehensive cleanup to ensure everything stops
      return () => {
        // Mark this segment as inactive to prevent stale handlers
        isSegmentActive = false;
        
        // Stop the monitoring interval
        clearInterval(monitoringInterval);
        
        if (audioRef.current) {
          // Remove event listener
          audioRef.current.removeEventListener('timeupdate', monitorSegmentBoundary);
          
          // Force audio to stop when unmounting or changing segments
          audioRef.current.pause();
          
          console.log("Cleaned up segment playback - all audio stopped");
        }
      };
    }, 50); // Small delay to ensure clean state transition
    
    // Cleanup for the main effect
    return () => {
      // This outer cleanup runs when the segment changes or component unmounts
      if (audioRef.current) {
        audioRef.current.pause();
      }
    };
  }, [currentSegment, onTimeUpdate]);
  
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
          preload="auto"
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
              {/* Show appropriate time value */}
              {currentSegment
                // Within segment: Show time relative to segment start 
                ? formatDuration(Math.max(0, Math.min(currentTime, currentSegment.end_time) - currentSegment.start_time))
                // Full audio: Show absolute time 
                : formatDuration(currentTime)
              }
            </span>
            <div 
              className="relative flex-1" 
              onClick={(e) => {
                if (!isLoaded || !audioRef.current) return;
                
                // Calculate click position as percentage of width
                const rect = e.currentTarget.getBoundingClientRect();
                const clickPositionPercent = (e.clientX - rect.left) / rect.width;
                
                // Convert to time based on min/max
                const min = currentSegment ? currentSegment.start_time : 0;
                const max = currentSegment ? currentSegment.end_time : (duration || 100);
                const clickedTime = min + clickPositionPercent * (max - min);
                
                console.log(`Slider direct click: ${clickedTime.toFixed(2)}`);
                
                // Use existing logic for handling time changes
                handleSliderChange([clickedTime]);
              }}
            >
              <Slider
                // Constrain value to segment bounds if in a segment
                value={[currentSegment
                  // In segment: Keep time within segment bounds
                  ? Math.min(Math.max(currentSegment.start_time, currentTime), currentSegment.end_time)
                  // Full audio: Use actual time
                  : currentTime
                ]}
                // Set appropriate min/max
                min={currentSegment ? currentSegment.start_time : 0}
                max={currentSegment ? currentSegment.end_time : (duration || 100)}
                step={0.1}
                onValueChange={handleSliderChange}
                disabled={!isLoaded}
                aria-label="Audio progress"
                className={cn(
                  "flex-1 cursor-pointer absolute w-full z-10",
                  currentSegment && "bg-primary/20" // Highlight when in segment mode
                )}
                data-testid="audio-slider"
              />
              {/* Visual progress bar underneath for better visibility */}
              <div className="h-2 rounded-full bg-muted overflow-hidden">
                <div 
                  className="h-full bg-primary transition-all" 
                  style={{ 
                    width: `${currentSegment 
                      ? ((currentTime - currentSegment.start_time) / (currentSegment.end_time - currentSegment.start_time)) * 100
                      : (currentTime / (duration || 100)) * 100}%` 
                  }}
                />
              </div>
            </div>
            <span className="text-xs w-12 text-right text-muted-foreground">
              {/* Show appropriate duration */}
              {currentSegment
                // Within segment: Show segment duration
                ? formatDuration(currentSegment.end_time - currentSegment.start_time)
                // Full audio: Show total duration
                : formatDuration(duration)
              }
            </span>
          </div>
          
          {/* Segment info indicator - shows when a segment is active */}
          {currentSegment && (
            <div className="text-xs text-muted-foreground bg-muted px-2 py-1 rounded flex items-center mb-1">
              <span className="font-medium">
                Playing segment: {currentSegment.speaker} 
              </span>
              <span className="ml-auto">
                {secondsToTimestamp(currentSegment.start_time)} - {secondsToTimestamp(currentSegment.end_time)}
              </span>
            </div>
          )}
          
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